"""Measurement, material assignment, DMU and state-based diagnostics."""
import math

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, tool
from catia_mcp.tools.operations import OperationTools, BOOL, INTEGER, VECTOR, array, group


class AnalysisTools(OperationTools):
    def get_tool_definitions(self):
        return [
            group("catia_measure_exact", "Read geometric measurements in active Part coordinates. SI values and explicit public units. No containers or guessed topology. SAFEARRAY failures are reported, never replaced with zeros.", {
                "scalar": {"handle": HANDLE, "property": {"enum": ["length", "radius", "area", "volume"]}},
                "point": {"handle": HANDLE}, "center": {"handle": HANDLE},
                "direction": {"handle": HANDLE}, "axis": {"handle": HANDLE},
                "distance": {"first_handle": HANDLE, "second_handle": HANDLE},
                "angle": {"first_handle": HANDLE, "second_handle": HANDLE},
                "distance_points": {"first_handle": HANDLE, "second_handle": HANDLE},
                "inertia": {},
            }, readonly=True),
            tool("catia_diagnose_geometry", "Read update/constraint status for handbook diagnostics 208–218. Does not claim root cause, repair geometry, infer DOF, or use screenshots as proof.",
                 {"handle": HANDLE, "capability": {"type": "integer", "minimum": 208, "maximum": 218}}, ["capability"], readonly=True),
            group("catia_material", "List materials from an explicitly identified OPEN material catalog or apply an explicit catalog item. Catalog is read only; no document activation. Assignment changes only the bound Part/body/Product.", {
                "apply_part": {"catalog_document_id": HANDLE, "family_index": {"type": "integer", "minimum": 1}, "material_index": {"type": "integer", "minimum": 1}, "link": BOOL},
                "apply_body": {"catalog_document_id": HANDLE, "family_index": {"type": "integer", "minimum": 1}, "material_index": {"type": "integer", "minimum": 1}, "link": BOOL, "body_handle": HANDLE},
            }, {"expected_material_name": HANDLE}),
            tool("catia_material_catalog", "List actual material families/items from an already open catalog document. Indices are transient and apply must include expected material name.",
                 {"catalog_document_id": HANDLE}, ["catalog_document_id"], readonly=True),
            group("catia_dmu", "Explicit licensed DMU operations in the active Product. Creates analysis objects; does not export, save or simulate commands implicitly. Live license/API verification pending.", {
                "clash": {"clearance_mm": {"type": "number", "minimum": 0}, "interference": {"enum": [0, 1, 2, 3]}},
                "section": {"position": array(NUMBER, 12, 12), "width_mm": POSITIVE, "height_mm": POSITIVE},
                "mechanism": {"fixed_product_handle": HANDLE},
                "joint": {"mechanism_handle": HANDLE, "joint_type": HANDLE, "element_handles": array(HANDLE)},
                "command": {"mechanism_handle": HANDLE, "joint_handle": HANDLE, "command_type": HANDLE},
                "command_values": {"mechanism_handle": HANDLE, "values": array(NUMBER)},
            }),
        ]

    def execute(self, name, a):
        return {"catia_measure_exact": self.measure, "catia_diagnose_geometry": self.diagnose,
                "catia_material": self.material, "catia_material_catalog": self.catalog,
                "catia_dmu": self.dmu}[name](a)

    def measure(self, a):
        doc, mode = self.conn.active_document, a["mode"]
        if mode == "inertia":
            inertia = doc.Product.GetTechnologicalObject("Inertia")
            density = float(inertia.Density)
            return {"ok": True, "mass_kg": float(inertia.Mass), "density_kg_m3": density if density not in (-1, 1) else None,
                    "density_status": "heterogeneous" if density == -1 else "default_density" if density == 1 else "reported",
                    "cog_m": read_array(inertia.GetCOGPosition, 3), "tensor_kg_m2": read_array(inertia.GetInertiaMatrix, 9),
                    "frame": "active document Product", "warning": "Mass is only as reliable as assigned materials/densities"}
        self.conn.get_active_part()  # Assembly occurrence metrology requires a separate context contract.
        h = a.get("handle", a.get("first_handle"))
        allowed = {"point", "vertex", "line", "curve", "edge", "face", "surface", "plane", "feature", "sketch"}
        reference = self.ref(h, allowed)
        measurable = doc.GetWorkbench("SPAWorkbench").GetMeasurable(reference)
        geometry = int(measurable.GeometryName)
        result = {"ok": True, "frame": "active Part", "geometry_type": geometry}
        if mode == "scalar":
            property_name, api_unit, public_unit, scale, types = {
                "length": ("Length", "m", "mm", 1000, {8, 9, 10}),
                "radius": ("Radius", "m", "mm", 1000, {4, 5, 9}),
                "area": ("Area", "m2", "mm2", 1e6, {2, 3, 4, 5, 6, 7}),
                "volume": ("Volume", "m3", "mm3", 1e9, {2}),
            }[a["property"]]
            if geometry not in types:
                raise CADOperationError("WRONG_GEOMETRY_TYPE", "Requested property is undefined for this measurable type")
            value = float(getattr(measurable, property_name))
            result.update(api_value=value, api_unit=api_unit, value=value * scale, unit=public_unit)
        elif mode in {"point", "center", "direction", "axis"}:
            methods = {"point": ("GetPoint", {11}, "m"), "center": ("GetCenter", {5, 9}, "m"),
                       "direction": ("GetDirection", {10}, "unit_vector"), "axis": ("GetAxis", {4, 6}, "unit_vector")}
            method, types, unit = methods[mode]
            if geometry not in types:
                raise CADOperationError("WRONG_GEOMETRY_TYPE", "Getter is undefined for this measurable type")
            result.update(value=read_array(getattr(measurable, method), 3), unit=unit)
        else:
            other = self.ref(a["second_handle"], allowed)
            if mode == "distance_points":
                result.update(value=read_array(measurable.GetMinimumDistancePoints, 9, other), unit="m",
                              warning="Native nine-component CATIA output, not an invented pair-of-points layout")
            elif mode == "distance":
                result.update(value=float(measurable.GetMinimumDistance(other)) * 1000, unit="mm")
            else:
                result.update(value=float(measurable.GetAngleBetween(other)), unit="deg")
        return result

    def diagnose(self, a):
        result = {"ok": True, "capability": a["capability"], "diagnosis": "undetermined", "repair_performed": False,
                  "limitations": "No solver DOF, profile closure, minimum radius or geometric root cause is inferred from Update alone"}
        if "handle" in a:
            obj = self.state.resolve(a["handle"]).value
            result["name"] = str(obj.Name)
            try:
                result["up_to_date"] = bool(self.conn.get_active_part().IsUpToDate(obj))
            except Exception as exc:
                result["update_status_unavailable"] = str(exc)
            for attr in ("Status", "DimStatus", "NbDof", "NbCommands"):
                try:
                    result[attr] = int(getattr(obj, attr))
                except Exception:
                    pass
        if a["capability"] in (210, 211) and self.engineering.sketcher._active_sketch is not None:
            constraints = self.engineering.sketcher._active_sketch.Constraints
            result["constraints"] = [{"name": str(constraints.Item(i).Name), "status": int(constraints.Item(i).Status)} for i in range(1, constraints.Count + 1)]
        return result

    def catalog_document(self, identity):
        doc = self.state.documents.get(identity)
        docs = self.conn.app.Documents
        if doc is None or not any(same_object(doc, docs.Item(i)) for i in range(1, docs.Count + 1)):
            raise CADOperationError("STALE_REFERENCE", "Catalog is no longer open; reread open document IDs")
        try:
            doc.Families.Count
        except Exception as exc:
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "Source is not a material catalog") from exc
        return doc

    def catalog(self, a):
        families = self.catalog_document(a["catalog_document_id"]).Families
        return {"ok": True, "families": [{"index": i, "name": str(families.Item(i).Name),
                 "materials": [{"index": j, "name": str(families.Item(i).Materials.Item(j).Name)}
                               for j in range(1, families.Item(i).Materials.Count + 1)]}
                for i in range(1, families.Count + 1)]}

    def material(self, a):
        source = self.catalog_document(a["catalog_document_id"])
        material = source.Families.Item(a["family_index"]).Materials.Item(a["material_index"])
        if str(material.Name) != a["expected_material_name"]:
            raise CADOperationError("STALE_REFERENCE", "Catalog indices changed; material name differs")
        part = self.conn.get_active_part()
        manager = part.GetItem("CATMatManagerVBExt")
        self.state.mutation_started = True
        if a["mode"] == "apply_body":
            body = self.obj(a["body_handle"], {"body"})
            self.changed(a["body_handle"])
            manager.ApplyMaterialOnBody(body, material, int(a["link"]))
        else:
            manager.ApplyMaterialOnPart(part, material, int(a["link"]))
        result = self.update(part)
        result["material_name"] = str(material.Name)
        result["warning"] = "Assignment called successfully; independently check density and mass"
        return result

    def dmu(self, a):
        if not str(self.conn.active_document.Name).lower().endswith(".catproduct"):
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "DMU tool requires active CATProduct")
        product, mode = self.conn.active_document.Product, a["mode"]
        if mode == "clash":
            obj = product.GetTechnologicalObject("Clashes").Add()
            h = self.state.mark_created(obj, "clash")
            obj.Clearance, obj.InterferenceType = a["clearance_mm"], a["interference"]
            obj.Compute()
            return {"ok": True, "handle": h, "conflict_count": int(obj.Conflicts.Count), "scope": "CATIA default all-product clash scope"}
        if mode == "section":
            obj = product.GetTechnologicalObject("Sections").Add()
            h = self.state.mark_created(obj, "section")
            obj.SetPosition(tuple(a["position"]))
            obj.Width, obj.Height = a["width_mm"], a["height_mm"]
            result = self.update(product)
            result.update(handle=h, is_empty=bool(obj.IsEmpty()))
            return result
        if mode == "mechanism":
            fixed = self.obj(a["fixed_product_handle"], {"product"})
            obj = product.GetTechnologicalObject("Mechanisms").Add()
            h = self.state.mark_created(obj, "mechanism")
            obj.FixedPart = fixed
        else:
            obj = self.obj(a["mechanism_handle"], {"mechanism"})
            self.changed(a["mechanism_handle"])
            h = a["mechanism_handle"]
            if mode == "joint":
                records = [self.state.resolve(handle, {"product", "point", "line", "plane", "face", "edge", "vertex", "surface", "curve"}) for handle in a["element_handles"]]
                # A selected face's Value may be its parent feature; preserve the exact Reference.
                elements = tuple(r.reference if r.reference is not None else r.value for r in records)
                h = self.state.mark_created(obj.AddJoint(a["joint_type"], elements), "joint")
            elif mode == "command":
                joint = self.obj(a["joint_handle"], {"joint"})
                h = self.state.mark_created(obj.AddCommand(a["command_type"], joint), "mechanism_command")
            else:
                if len(a["values"]) != obj.NbCommands:
                    raise CADOperationError("INVALID_ARGUMENT", "Value count differs from mechanism command count")
                obj.PutCommandValues(tuple(a["values"]))
        result = self.update(obj)
        result.update(handle=h, degrees_of_freedom=int(obj.NbDof), commands=int(obj.NbCommands))
        return result
