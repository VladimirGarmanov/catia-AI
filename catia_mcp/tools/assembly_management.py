"""Occurrence and constraint management using documented CAA Product interfaces.

Writes target the active assembly's immediate children. Editing a nested external
subassembly requires activating and binding that document explicitly first.
"""
import math

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.constraint_policy import check_constraint_command, check_constraint_edit
from catia_mcp.tools.domains import DomainTools, absolute_file
from catia_mcp.tools.domain_support import members, member_index, read_properties, verify_equal
from catia_mcp.tools.engineering import HANDLE, NUMBER, tool, dimension
from catia_mcp.tools.operations import BOOL, VECTOR, array, group, unit_vector

TEXT = {"type": "string"}
PAIR = {"selection_handles": array(HANDLE, 2, 2)}
TRIPLE = {"selection_handles": array(HANDLE, 3, 3)}


class AssemblyManagementTools(DomainTools):
    def get_tool_definitions(self):
        return [
            tool("catia_assembly_inspect", "Read occurrence tree, root constraints, publications and optional parent-relative poses. Unavailable COM fields are explicit. No activation or Update.", {
                "max_objects": {"type": "integer", "minimum": 1, "maximum": 2000},
                "max_depth": {"type": "integer", "minimum": 0, "maximum": 30},
                "include_positions": BOOL,
            }, readonly=True),
            group("catia_assembly_component", "Manage immediate occurrences of the active CATProduct only. Positions use parent-frame mm and column-major rotation. No source-document edits or saves; no implicit constraint suppression.", {
                "new_component": {"document_type": {"enum": ["Part", "Product"]}, "part_number": HANDLE},
                "import_file": {"file_path": HANDLE},
                "rename": {"component_handle": HANDLE, "name": HANDLE},
                "description": {"component_handle": HANDLE, "description": TEXT},
                "remove": {"component_handle": HANDLE},
                "set_position": {"component_handle": HANDLE, "axis_components": array(NUMBER, 12, 12)},
                "translate": {"component_handle": HANDLE, "translation_mm": VECTOR},
                "rotate": {"component_handle": HANDLE, "axis": VECTOR, "angle_deg": NUMBER},
                "update": {},
            }),
            group("catia_assembly_constraint", "Create or edit root assembly constraints. Fix is disabled; existing Fix constraints may only be deactivated or removed. Creation/replacement requires fresh exact selection handles, never names or edge indices. sphere_concentric is sphere/sphere only, not cylinder-axis alignment. symmetry uses two supports then a symmetry line/plane; planar_angle uses two planes then their intersection line. distance_three uses two supports then a measurement direction. angle_sector also changes native angle/side/orientation. Read native solver status after Update. Geometry compatibility is checked by CATIA.", {
                **{mode: PAIR for mode in ("coincidence", "parallel", "perpendicular", "contact")},
                **{mode: PAIR for mode in ("tangent", "sphere_concentric")},
                "symmetry": TRIPLE,
                "planar_angle": {**TRIPLE, "value": NUMBER},
                "distance_three": {**TRIPLE, "value": NUMBER},
                "distance": {**PAIR, "value": NUMBER},
                "angle": {**PAIR, "value": NUMBER},
                "angle_sector": {"constraint_handle": HANDLE, "sector": {"type": "integer", "minimum": 0, "maximum": 3}},
                "distance_direction": {"constraint_handle": HANDLE, "direction": {"enum": ["free", "x", "y", "z"]}},
                "driving_mode": {"constraint_handle": HANDLE, "driving": BOOL},
                "edit_value": {"constraint_handle": HANDLE, "value": NUMBER},
                "orientation": {"constraint_handle": HANDLE, "orientation": {"enum": ["same", "opposite", "undefined"]}},
                "side": {"constraint_handle": HANDLE, "side": {"enum": ["positive", "negative", "undefined"]}},
                **{mode: {"constraint_handle": HANDLE} for mode in ("activate", "deactivate", "remove")},
                "rename": {"constraint_handle": HANDLE, "name": HANDLE},
                "replace_element": {"constraint_handle": HANDLE, "element": {"type": "integer", "minimum": 1, "maximum": 3}, "selection_handle": HANDLE},
            }),
            group("catia_assembly_publication", "Rename, rebind or remove an existing publication of the active root Product. Rebinding requires an exact current selection; external reference products are not changed.", {
                "rename": {"name": HANDLE},
                "rebind": {"selection_handle": HANDLE},
                "remove": {},
            }, {"publication_handle": HANDLE}),
        ]

    def execute(self, name, a):
        return {"catia_assembly_inspect": self.inspect, "catia_assembly_component": self.component,
                "catia_assembly_constraint": self.constraint, "catia_assembly_publication": self.publication}[name](a)

    def constraint_data(self, obj):
        row = read_properties(obj, {"Name": str, "Type": int, "Status": int, "Mode": int, "Orientation": int, "Side": int})
        try:
            row["inactive"] = bool(obj.IsInactive())
        except Exception as exc:
            row["inactive"] = None
            row.setdefault("unavailable", {})["inactive"] = str(exc)
        if row["Type"] in {1, 6, 7}:
            try:
                row["dimension"] = str(obj.Dimension.ValueAsString())
            except Exception as exc:
                row["dimension"] = None
                row.setdefault("unavailable", {})["dimension"] = str(exc)
        for attr, kinds in (("AngleSector", {6, 7}), ("DistanceDirection", {1})):
            if row["Type"] in kinds:
                extra = read_properties(obj, {attr: int})
                row[attr] = extra[attr]
                if "unavailable" in extra:
                    row.setdefault("unavailable", {}).update(extra["unavailable"])
        return row

    def inspect(self, a):
        root = self.product()
        rows, warnings = [], []
        limit = a.get("max_objects", 500)
        truncated = False

        def walk(value, parent, depth):
            nonlocal truncated
            if len(rows) >= limit:
                truncated = True
                return
            h = self.state.register(value, "product")
            row = {"handle": h, "parent": parent, **read_properties(value, {
                "Name": str, "PartNumber": str, "DescriptionInst": str,
                "DescriptionRef": str, "Revision": str, "Nomenclature": str, "Definition": str})}
            rows.append(row)
            if a.get("include_positions", False):
                try:
                    row["axis_components"] = read_array(value.Position.GetComponents, 12)
                except Exception as exc:
                    row["axis_components"] = None
                    row.setdefault("unavailable", {})["axis_components"] = str(exc)
            if depth >= a.get("max_depth", 8):
                truncated |= bool(value.Products.Count)
                return
            for index, child in members(value.Products):
                walk(child, h, depth + 1)
                if len(rows) >= limit:
                    truncated |= index < value.Products.Count
                    break

        walk(root, None, 0)
        constraints, publications = [], []
        for attr, kind, dest in (("constraints", "constraint", constraints), ("publications", "publication", publications)):
            try:
                collection = root.Connections("CATIAConstraints") if attr == "constraints" else root.Publications
                for i, obj in members(collection):
                    if i > limit:
                        truncated = True
                        break
                    row = self.constraint_data(obj) if kind == "constraint" else {"Name": str(obj.Name)}
                    dest.append({"handle": self.state.register(obj, kind), **row})
            except Exception as exc:
                warnings.append(f"{attr}: {exc}")
        return {"ok": True, "products": rows, "constraints": constraints, "publications": publications,
                "truncated": truncated, "warnings": warnings, "position_frame": "parent; axes then origin in mm",
                "session": self.state.context(self.state.document_id())}

    def occurrence(self, handle):
        root = self.product()
        obj = self.obj(handle, {"product"})
        return obj, member_index(root.Products, obj)

    @staticmethod
    def validate_pose(pose):
        if len(pose) != 12 or not all(math.isfinite(x) for x in pose):
            raise CADOperationError("INVALID_ARGUMENT", "Position needs 12 finite components")
        axes = [pose[i:i+3] for i in (0, 3, 6)]
        for i in range(3):
            for j in range(3):
                if not math.isclose(sum(x*y for x, y in zip(axes[i], axes[j])), float(i == j), abs_tol=1e-7):
                    raise CADOperationError("INVALID_ARGUMENT", "Position axes must be orthonormal")
        x, y, z = axes
        det = x[0]*(y[1]*z[2]-y[2]*z[1])-x[1]*(y[0]*z[2]-y[2]*z[0])+x[2]*(y[0]*z[1]-y[1]*z[0])
        if not math.isclose(det, 1.0, abs_tol=1e-7):
            raise CADOperationError("INVALID_ARGUMENT", "Position must be right-handed, not reflected")

    def component(self, a):
        root, mode = self.product(), a["mode"]
        if mode == "update":
            return self.update(root)
        if mode in {"new_component", "import_file"}:
            document = self.conn.active_document
            before = [value for _, value in members(root.Products)]
            path = absolute_file(a["file_path"], True) if mode == "import_file" else None
            if path and path.suffix.lower() not in {".catpart", ".catproduct"}:
                raise CADOperationError("INVALID_ARGUMENT", "Import requires CATPart or CATProduct")
            self.state.mutation_started = True
            try:
                if path:
                    root.Products.AddComponentsFromFiles((str(path),), "All")
                else:
                    root.Products.AddNewComponent(a["document_type"], a["part_number"])
            finally:
                # Native constructors may leave occurrences behind even if they raise.
                if same_object(self.conn.active_document, document):
                    for _, obj in members(root.Products):
                        if not any(same_object(obj, old) for old in before):
                            self.state.mark_created(obj, "product")
            if not same_object(self.conn.active_document, document):
                raise CADOperationError("DOCUMENT_MISMATCH", "CATIA changed active document during component creation; inspect before continuing")
            result = self.update(root)
            verify_equal(int(root.Products.Count), len(before) + 1, "Occurrence count")
            result["created"] = list(self.state.created)
            return result
        obj, index = self.occurrence(a["component_handle"])
        target = None
        if mode in {"set_position", "translate", "rotate"}:
            # Preflight SAFEARRAY support before changing anything.
            old = read_array(obj.Position.GetComponents, 12)
            self.validate_pose(old)
            target = list(a["axis_components"]) if mode == "set_position" else list(old)
            if mode == "translate":
                target[9:] = [x+y for x, y in zip(old[9:], a["translation_mm"])]
            elif mode == "rotate":
                u = unit_vector(a["axis"])
                c, s = math.cos(math.radians(a["angle_deg"])), math.sin(math.radians(a["angle_deg"]))
                # Rodrigues: rotate each basis vector about the occurrence origin in parent axes.
                for offset in (0, 3, 6):
                    v = old[offset:offset+3]
                    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                    dot = sum(x*y for x, y in zip(u, v))
                    target[offset:offset+3] = [c*v[i] + s*cross[i] + (1-c)*dot*u[i] for i in range(3)]
            self.validate_pose(target)
        if mode == "rename" and any(str(v.Name) == a["name"] and not same_object(v, obj) for _, v in members(root.Products)):
            raise CADOperationError("INVALID_ARGUMENT", "Another occurrence already has that name")
        count = int(root.Products.Count)
        self.changed(a["component_handle"])
        if mode == "remove":
            root.Products.Remove(index)
            self.state.objects.pop(a["component_handle"], None)
        elif mode == "rename":
            obj.Name = a["name"]
        elif mode == "description":
            obj.DescriptionInst = a["description"]
        else:
            obj.Position.SetComponents(tuple(target))
        result = self.update(root)
        if mode == "remove":
            verify_equal(int(root.Products.Count), count - 1, "Occurrence count")
            result["removed_handle"] = a["component_handle"]
        elif target is not None:
            actual = read_array(obj.Position.GetComponents, 12)
            for i, expected in enumerate(target):
                verify_equal(actual[i], expected, f"Solved pose[{i}]")
            result["axis_components"] = actual
        else:
            field = "Name" if mode == "rename" else "DescriptionInst"
            actual = str(getattr(obj, field))
            verify_equal(actual, a["name" if mode == "rename" else "description"], field)
            result[field] = actual
        return result

    def selected_reference(self, handle):
        record = self.state.resolve(handle)
        if record.reference is None or record.selection_index is None:
            raise CADOperationError("INVALID_ARGUMENT", "Select the exact assembly support and reread selection")
        selected = self.conn.active_document.Selection.Item2(record.selection_index)
        leaf = selected.LeafProduct
        # Nested reference edits can affect another assembly; scope to root occurrences.
        member_index(self.product().Products, leaf)
        return record.reference

    def constraint(self, a):
        check_constraint_command("catia_assembly_constraint", a)
        root, mode = self.product(), a["mode"]
        collection = root.Connections("CATIAConstraints")
        kinds = {"distance": 1, "distance_three": 1, "coincidence": 2,
                 "sphere_concentric": 3, "tangent": 4, "angle": 6, "planar_angle": 7,
                 "parallel": 8, "perpendicular": 11, "symmetry": 15, "contact": 20}
        expected_dimension = None
        if mode in kinds:
            handles = a["selection_handles"]
            if len(set(handles)) != len(handles):
                raise CADOperationError("INVALID_ARGUMENT", "Constraint supports must be distinct selection handles")
            refs = [self.selected_reference(h) for h in handles]
            self.state.mutation_started = True
            constructor = collection.AddTriEltCst if mode in {"symmetry", "planar_angle", "distance_three"} else collection.AddBiEltCst
            obj = constructor(kinds[mode], *refs)
            handle = self.state.mark_created(obj, "constraint")
            if mode in {"distance", "distance_three", "angle", "planar_angle"}:
                dimension(obj.Dimension, a["value"], "mm" if kinds[mode] == 1 else "deg")
                expected_dimension = float(obj.Dimension.Value)
        else:
            handle = a["constraint_handle"]
            obj = self.obj(handle, {"constraint"})
            index = member_index(collection, obj)
            check_constraint_edit(obj, mode)
            if mode in {"edit_value", "driving_mode"} and int(obj.Type) not in {1, 6, 7}:
                raise CADOperationError("INVALID_ARGUMENT", "Only distance and angle constraints have an editable dimension here")
            if mode == "angle_sector" and int(obj.Type) not in {6, 7}:
                raise CADOperationError("INVALID_ARGUMENT", "Angle sector requires an angular constraint")
            if mode == "distance_direction" and int(obj.Type) != 1:
                raise CADOperationError("INVALID_ARGUMENT", "Distance direction requires a distance constraint")
            ref = self.selected_reference(a["selection_handle"]) if mode == "replace_element" else None
            count = int(collection.Count)
            self.changed(handle)
            if mode == "remove":
                collection.Remove(index)
                self.state.objects.pop(handle, None)
                result = self.update(root)
                verify_equal(int(collection.Count), count - 1, "Constraint count")
                return {**result, "removed_handle": handle}
            if mode == "edit_value":
                dimension(obj.Dimension, a["value"], "mm" if int(obj.Type) == 1 else "deg")
                expected_dimension = float(obj.Dimension.Value)
            elif mode == "orientation":
                obj.Orientation = {"same": 0, "opposite": 1, "undefined": 2}[a["orientation"]]
            elif mode == "side":
                obj.Side = {"positive": 0, "negative": 1, "undefined": 4}[a["side"]]
            elif mode == "angle_sector":
                obj.AngleSector = a["sector"]
            elif mode == "distance_direction":
                obj.DistanceDirection = {"free": 0, "x": 1, "y": 2, "z": 3}[a["direction"]]
            elif mode == "driving_mode":
                obj.Mode = 0 if a["driving"] else 1
            elif mode == "rename":
                obj.Name = a["name"]
            elif mode == "replace_element":
                obj.SetConstraintElement(a["element"], ref)
            elif mode == "activate":
                obj.Activate()
            else:
                obj.Deactivate()
        result = self.update(root)
        if expected_dimension is not None:
            verify_equal(float(obj.Dimension.Value), expected_dimension, "Constraint dimension after solve")
        if mode in {"activate", "deactivate"}:
            verify_equal(bool(obj.IsInactive()), mode == "deactivate", "Constraint suppression")
        if mode == "rename":
            verify_equal(str(obj.Name), a["name"], "Constraint name")
        if mode == "orientation":
            verify_equal(int(obj.Orientation), {"same": 0, "opposite": 1, "undefined": 2}[a["orientation"]], "Orientation")
        if mode == "side":
            verify_equal(int(obj.Side), {"positive": 0, "negative": 1, "undefined": 4}[a["side"]], "Side")
        if mode == "angle_sector":
            verify_equal(int(obj.AngleSector), a["sector"], "Angle sector")
        if mode == "distance_direction":
            verify_equal(int(obj.DistanceDirection), {"free": 0, "x": 1, "y": 2, "z": 3}[a["direction"]], "Distance direction")
        if mode == "driving_mode":
            verify_equal(int(obj.Mode), 0 if a["driving"] else 1, "Constraint mode")
        if not obj.IsInactive() and int(obj.Status) != 0:
            raise CADOperationError("POSTCONDITION_FAILED", f"Constraint is not solved: native Status={obj.Status}")
        return {**result, "handle": handle, "constraint": self.constraint_data(obj)}

    def publication(self, a):
        root = self.product()
        collection = root.Publications
        obj = self.obj(a["publication_handle"], {"publication"})
        member_index(collection, obj)
        old_name = str(obj.Name)
        if a["mode"] == "rename" and any(str(v.Name) == a["name"] and not same_object(obj, v) for _, v in members(collection)):
            raise CADOperationError("INVALID_ARGUMENT", "Publication name already exists")
        ref = self.selected_reference(a["selection_handle"]) if a["mode"] == "rebind" else None
        count = int(collection.Count)
        self.changed(a["publication_handle"])
        if a["mode"] == "remove":
            collection.Remove(old_name)
            self.state.objects.pop(a["publication_handle"], None)
        elif a["mode"] == "rename":
            obj.Name = a["name"]
        else:
            collection.SetDirect(old_name, ref)
        result = self.update(root)
        if a["mode"] == "remove":
            verify_equal(int(collection.Count), count - 1, "Publication count")
        elif a["mode"] == "rename":
            verify_equal(str(obj.Name), a["name"], "Publication name")
        return {**result, "warning": "Publication consumers and exact rebind effect require inspection in CATIA"}
