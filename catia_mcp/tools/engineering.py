"""Typed, handle-based operations. No arbitrary COM method/property execution."""
from __future__ import annotations

import math
from typing import Any

from catia_mcp.runtime import CADOperationError, same_object


HANDLE = {"type": "string", "minLength": 1}
NUMBER = {"type": "number"}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}


def tool(name, description, properties, required=(), readonly=False):
    return {"name": name, "description": description, "readOnlyHint": readonly,
            "inputSchema": {"type": "object", "properties": properties,
                            "required": list(required), "additionalProperties": False}}


def dimension(parameter, value, unit):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CADOperationError("INVALID_ARGUMENT", "Dimension must be finite")
    parameter.ValuateFromString(f"{value:.15g}{unit}")
    return {"requested": value, "unit": unit, "readback": str(parameter.ValueAsString())}


def geometry_kind(value, fallback="geometry"):
    """Use Automation type metadata, never a mutable display name."""
    try:
        kind = {2: "point2d", 3: "line2d", 5: "circle2d", 8: "ellipse2d",
                9: "curve", 10: "point", 11: "line", 12: "plane"}.get(int(value.GeometricType))
        if kind:
            return kind
    except Exception:
        pass
    try:
        interface = str(value._oleobj_.GetTypeInfo().GetDocumentation(-1)[0])
    except Exception:
        return fallback
    for prefix, kind in (("HybridShapePoint", "point"), ("HybridShapeLine", "line"),
                         ("HybridShapePlane", "plane"), ("HybridShapeCircle", "curve"),
                         ("HybridShapeSpline", "curve")):
        if interface.startswith(prefix):
            return kind
    if interface in {"HybridShapeExtrude", "HybridShapeRevol", "HybridShapeLoft", "HybridShapeFill", "HybridShapeOffset"}:
        return "surface"
    return fallback


class EngineeringTools:
    def __init__(self, connection, state, sketcher):
        self.conn, self.state, self.sketcher = connection, state, sketcher

    def get_tool_definitions(self):
        return [
            tool("catia_list_objects", "Enumerate CATPart objects with session handles; no topology guessing. Selection handles require the same live selection and expire on writes.",
                 {"max_objects": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500}}, readonly=True),
            tool("catia_create_container", "Create a Body, HybridBody or OrderedGeometricalSet in the bound CATPart.",
                 {"kind": {"enum": ["body", "geoset", "ordered_geoset"]}, "name": HANDLE}, ["kind", "name"]),
            tool("catia_feature_state", "Set in-work object or feature activation by exact handle; no deletion.",
                 {"handle": HANDLE, "action": {"enum": ["in_work", "activate", "deactivate"]}}, ["handle", "action"]),
            tool("catia_select_objects", "Replace CATIA selection with exact whole-object handles. Cannot synthesize faces/edges. Existing selection replacement is explicit.",
                 {"handles": {"type": "array", "items": HANDLE, "minItems": 1},
                  "replace_selection": {"const": True}}, ["handles", "replace_selection"]),
            tool("catia_swept_solid", "Rib or Slot from two closed-edition sketches in a specified Body. Update and status are checked, geometric sweep validity is decided by CATIA.",
                 {"mode": {"enum": ["rib", "slot"]}, "profile_handle": HANDLE,
                  "spine_handle": HANDLE, "body_handle": HANDLE, "name": HANDLE},
                 ["mode", "profile_handle", "spine_handle", "body_handle"]),
            tool("catia_boolean", "Boolean operation between two distinct Body handles in the bound Part. Source body is consumed by CATIA's feature tree.",
                 {"mode": {"enum": ["add", "remove", "intersect", "assemble"]},
                  "body_handle": HANDLE, "operand_handle": HANDLE, "name": HANDLE},
                 ["mode", "body_handle", "operand_handle"]),
            tool("catia_solid_loft", "Solid/removed loft through ordered sketch sections. Explicit point handle per section avoids unverified COM Nothing bridge. No automatic reordering.",
                 {"body_handle": HANDLE, "remove": {"type": "boolean", "default": False},
                  "sections": {"type": "array", "minItems": 2, "items": {
                      "type": "object", "properties": {"profile_handle": HANDLE,
                      "closing_point_handle": HANDLE, "orientation": {"enum": [1, -1]}},
                      "required": ["profile_handle", "closing_point_handle", "orientation"], "additionalProperties": False}},
                  "name": HANDLE}, ["body_handle", "sections"]),
            tool("catia_reference_plane", "Create a plane in an explicit HybridBody from typed handles. Tangent requires caller-defined point; incidence/normal tests remain unverified.",
                 {"mode": {"enum": ["offset", "parallel_point", "three_points", "two_lines", "line_point", "normal", "tangent", "equation"]},
                  "container_handle": HANDLE, "references": {"type": "array", "items": HANDLE, "default": []},
                  "offset_mm": NUMBER, "coefficients": {"type": "array", "items": NUMBER, "minItems": 4, "maxItems": 4},
                  "point_on_surface_tolerance_mm": POSITIVE,
                  "name": HANDLE}, ["mode", "container_handle"]),
            tool("catia_reference_point", "Create a point in a HybridBody: absolute Part mm coordinates, plane-local coordinates, between points, or curve fraction. No invented surface UV convention.",
                 {"mode": {"enum": ["coordinates", "on_plane", "between", "on_curve"]},
                  "container_handle": HANDLE, "references": {"type": "array", "items": HANDLE},
                  "coordinates_mm": {"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 3},
                  "frame_id": {"enum": ["part", "support_plane"]},
                  "ratio": {"type": "number", "minimum": 0, "maximum": 1}, "name": HANDLE},
                 ["mode", "container_handle"]),
            tool("catia_create_parameter", "Create a typed Part parameter. Length/angle values explicitly use mm/deg via ValuateFromString, never bare SI assumptions.",
                 {"name": HANDLE, "kind": {"enum": ["length", "angle", "real", "integer", "boolean", "string"]},
                  "value": {"type": ["number", "string", "boolean"]}}, ["name", "kind", "value"]),
            tool("catia_create_formula", "Create a Knowledgeware formula for an exact parameter handle. CATIA syntax/license errors propagate; no scripts or macros.",
                 {"name": HANDLE, "parameter_handle": HANDLE, "expression": HANDLE}, ["name", "parameter_handle", "expression"]),
            tool("catia_measure_object", "Measure area/volume by Reference with explicit SI and public units. Other getters require separate validated adapters; no guessed array conventions.",
                 {"handle": HANDLE, "property": {"enum": ["area", "volume"]}}, ["handle", "property"], readonly=True),
        ]

    def execute(self, name, args):
        methods = {"catia_list_objects": self.list_objects, "catia_create_container": self.create_container,
                   "catia_feature_state": self.feature_state, "catia_select_objects": self.select_objects,
                   "catia_swept_solid": self.swept_solid, "catia_boolean": self.boolean,
                   "catia_solid_loft": self.solid_loft, "catia_reference_plane": self.reference_plane,
                   "catia_reference_point": self.reference_point,
                   "catia_create_parameter": self.create_parameter, "catia_create_formula": self.create_formula,
                   "catia_measure_object": self.measure}
        return methods[name](args)

    def list_objects(self, args):
        part = self.conn.get_active_part()
        limit = args.get("max_objects", 500)
        result, warnings = [], []

        def add(value, kind, parent=None, **kwargs):
            if len(result) >= limit:
                return None
            if kind == "geometry":
                kind = geometry_kind(value)
            handle = self.state.register(value, kind, **kwargs)
            result.append({"handle": handle, "kind": kind,
                           "name": str(getattr(value, "Name", "")), "container": parent})
            return handle

        def visit(collection, kind, parent=None, depth=0):
            if depth > 30 or len(result) >= limit:
                return
            for index in range(1, collection.Count + 1):
                obj = collection.Item(index)
                handle = add(obj, kind, parent)
                if handle is None:
                    break
                children = {"body": [("Sketches", "sketch"), ("Shapes", "feature")],
                            "geoset": [("HybridShapes", "geometry"), ("HybridSketches", "sketch"), ("HybridBodies", "geoset")],
                            "ordered_geoset": [("HybridShapes", "geometry"), ("Sketches", "sketch")]}.get(kind, [])
                if kind == "sketch":
                    children = [("GeometricElements", "geometry")]
                for attribute, child_kind in children:
                    try:
                        visit(getattr(obj, attribute), child_kind, handle, depth + 1)
                    except Exception as exc:
                        warnings.append(f"{obj.Name}.{attribute}: {exc}")

        visit(part.Bodies, "body")
        visit(part.HybridBodies, "geoset")
        try:
            visit(part.OrderedGeometricalSets, "ordered_geoset")
        except Exception as exc:
            warnings.append(f"OrderedGeometricalSets: {exc}")
        for plane in (part.OriginElements.PlaneXY, part.OriginElements.PlaneYZ, part.OriginElements.PlaneZX):
            add(plane, "plane")
        selection = self.conn.active_document.Selection
        for index in range(1, selection.Count2 + 1):
            item = selection.Item2(index)
            try:
                if not same_object(item.Document, self.conn.active_document):
                    raise ValueError("Selection belongs to another document/occurrence")
                kind = str(item.Type).lower()
                if kind.endswith("face"):
                    kind = "face"
                elif kind.endswith("edge"):
                    kind = "edge"
                add(item.Value, kind, reference=item.Reference, topology=True, selection_index=index)
            except Exception as exc:
                warnings.append(f"Selection {index}: no exact handle: {exc}")
        visit(part.Parameters, "parameter")
        return {"ok": True, "objects": result, "session": self.state.context(self.state.document_id()),
                "truncated": len(result) >= limit, "warnings": warnings}

    def finish(self, obj, kind, args, container=None):
        handle = self.state.mark_created(obj, kind)
        if args.get("name"):
            obj.Name = args["name"]
        if container is not None:
            container.AppendHybridShape(obj)
        part = self.conn.get_active_part()
        try:
            part.UpdateObject(obj)
            part.Update()
        except Exception as exc:
            raise CADOperationError("UPDATE_FAILED", f"Created {handle}; Update failed: {exc}") from exc
        if not part.IsUpToDate(obj):
            raise CADOperationError("POSTCONDITION_FAILED", f"{handle} is not up to date")
        self.state.updated = True
        return {"ok": True, "handle": handle, "name": str(obj.Name),
                "checks": [{"name": "up_to_date", "passed": True}],
                "warnings": ["Geometric postconditions not independently measured; Windows verification required"]}

    def create_container(self, args):
        part = self.conn.get_active_part()
        collection = getattr(part, {"body": "Bodies", "geoset": "HybridBodies",
                                   "ordered_geoset": "OrderedGeometricalSets"}[args["kind"]])
        return self.finish(collection.Add(), args["kind"], args)

    def feature_state(self, args):
        part = self.conn.get_active_part()
        obj = self.state.resolve(args["handle"], {"body", "geoset", "ordered_geoset", "feature", "sketch", "geometry"}).value
        self.state.modified.append(args["handle"])
        self.state.mutation_started = True
        if args["action"] == "in_work":
            part.InWorkObject = obj
            if not same_object(part.InWorkObject, obj):
                raise CADOperationError("POSTCONDITION_FAILED", "InWorkObject readback differs")
        else:
            inactive = args["action"] == "deactivate"
            (part.Inactivate if inactive else part.Activate)(obj)
            part.Update()
            if bool(part.IsInactive(obj)) != inactive:
                raise CADOperationError("POSTCONDITION_FAILED", "Activation readback differs")
            self.state.updated = True
        return {"ok": True}

    def select_objects(self, args):
        records = [self.state.resolve(h) for h in args["handles"]]
        if any(r.reference is not None for r in records):
            raise CADOperationError("UNSUPPORTED_OPERATION", "Only whole objects can be selected by this tool")
        selection = self.conn.active_document.Selection
        self.state.mutation_started = True
        selection.Clear()
        for record in records:
            selection.Add(record.value)
        if selection.Count2 != len(records):
            raise CADOperationError("POSTCONDITION_FAILED", "Selection count differs (duplicate objects?)")
        return {"ok": True, "count": selection.Count2}

    def body(self, handle):
        if self.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition first")
        body = self.state.resolve(handle, {"body"}).value
        self.conn.get_active_part().InWorkObject = body
        return body

    def swept_solid(self, args):
        profile = self.state.resolve(args["profile_handle"], {"sketch"}).value
        spine = self.state.resolve(args["spine_handle"], {"sketch"}).value
        self.body(args["body_handle"])
        factory = self.conn.get_active_part().ShapeFactory
        feature = (factory.AddNewRib if args["mode"] == "rib" else factory.AddNewSlot)(profile, spine)
        return self.finish(feature, "feature", args)

    def boolean(self, args):
        operand = self.state.resolve(args["operand_handle"], {"body"}).value
        target = self.state.resolve(args["body_handle"], {"body"}).value
        if same_object(operand, target):
            raise CADOperationError("INVALID_ARGUMENT", "Boolean needs distinct bodies")
        self.body(args["body_handle"])
        factory = self.conn.get_active_part().ShapeFactory
        constructors = {"add": factory.AddNewAdd, "remove": factory.AddNewRemove,
                        "intersect": factory.AddNewIntersect, "assemble": factory.AddNewAssemble}
        return self.finish(constructors[args["mode"]](operand), "feature", args)

    def solid_loft(self, args):
        sections = [(self.state.reference(s["profile_handle"], {"sketch"}), s["orientation"],
                     self.state.reference(s["closing_point_handle"], {"point", "point2d", "vertex"}))
                    for s in args["sections"]]
        self.body(args["body_handle"])
        factory = self.conn.get_active_part().ShapeFactory
        loft = factory.AddNewRemovedLoft() if args.get("remove") else factory.AddNewLoft()
        handle = self.state.mark_created(loft, "feature")
        # Raw COM dispatch exposes HybridShape; no pycatia wrapper is mixed in.
        hybrid = loft.HybridShape
        for reference, orientation, point in sections:
            hybrid.AddSectionToLoft(reference, orientation, point)
        result = self.finish(loft, "feature", args)
        result["constructor_handle"] = handle
        return result

    def reference_plane(self, args):
        container = self.state.resolve(args["container_handle"], {"geoset"}).value
        modes = {"offset": ("AddNewPlaneOffset", [{"plane"}]),
                 "parallel_point": ("AddNewPlaneOffsetPt", [{"plane"}, {"point", "point2d", "vertex"}]),
                 "three_points": ("AddNewPlane3Points", [{"point", "point2d", "vertex"}] * 3),
                 "two_lines": ("AddNewPlane2Lines", [{"line", "line2d"}] * 2),
                 "line_point": ("AddNewPlane1Line1Pt", [{"line", "line2d"}, {"point", "point2d", "vertex"}]),
                 "normal": ("AddNewPlaneNormal", [{"curve", "line", "line2d"}, {"point", "vertex"}]),
                 "tangent": ("AddNewPlaneTangent", [{"face", "surface"}, {"point", "vertex"}]),
                 "equation": ("AddNewPlaneEquation", [])}
        method, kinds = modes[args["mode"]]
        if args["mode"] == "tangent":
            if "point_on_surface_tolerance_mm" not in args:
                raise CADOperationError("INVALID_ARGUMENT", "Tangent mode requires point_on_surface_tolerance_mm; independent incidence measurement may remain unavailable")
        elif "point_on_surface_tolerance_mm" in args:
            raise CADOperationError("INVALID_ARGUMENT", "Incidence tolerance is only accepted for tangent planes")
        handles = args.get("references", [])
        if len(handles) != len(kinds):
            raise CADOperationError("INVALID_ARGUMENT", f"{args['mode']} requires {len(kinds)} references")
        values = [self.state.reference(h, k) for h, k in zip(handles, kinds)]
        if args["mode"] == "offset":
            if "offset_mm" not in args or "coefficients" in args:
                raise CADOperationError("INVALID_ARGUMENT", "Offset mode requires offset_mm only")
            values += [args["offset_mm"], False]
        elif args["mode"] == "equation":
            values = args.get("coefficients", [])
            if len(values) != 4 or sum(x*x for x in values[:3]) == 0 or "offset_mm" in args:
                raise CADOperationError("INVALID_ARGUMENT", "Equation requires [A,B,C,D], nonzero normal, no offset")
        elif "offset_mm" in args or "coefficients" in args:
            raise CADOperationError("INVALID_ARGUMENT", "Unexpected offset/coefficients for this mode")
        shape = getattr(self.conn.get_active_part().HybridShapeFactory, method)(*values)
        result = self.finish(shape, "plane", args, container)
        if args["mode"] == "tangent":
            result["warnings"].append("Point-on-surface incidence and normal agreement NOT verified")
            result["incidence_check"] = {"requested_tolerance_mm": args["point_on_surface_tolerance_mm"],
                                         "status": "unverified", "reason": "No calibrated distance/normal adapter on this host"}
        return result

    def reference_point(self, args):
        container = self.state.resolve(args["container_handle"], {"geoset"}).value
        mode = args["mode"]
        count = {"coordinates": 0, "on_plane": 1, "between": 2, "on_curve": 1}[mode]
        handles = args.get("references", [])
        if len(handles) != count:
            raise CADOperationError("INVALID_ARGUMENT", f"{mode} requires {count} references")
        factory = self.conn.get_active_part().HybridShapeFactory
        if mode in {"coordinates", "on_plane"}:
            coordinates = args.get("coordinates_mm", [])
            size, frame = (3, "part") if mode == "coordinates" else (2, "support_plane")
            if len(coordinates) != size or args.get("frame_id") != frame or "ratio" in args:
                raise CADOperationError("INVALID_ARGUMENT", f"Expected {size} coordinates, frame_id={frame}, no ratio")
            point = (factory.AddNewPointCoord(*coordinates) if mode == "coordinates" else
                     factory.AddNewPointOnPlane(self.state.reference(handles[0], {"plane"}), *coordinates))
        else:
            if "ratio" not in args or "coordinates_mm" in args or "frame_id" in args:
                raise CADOperationError("INVALID_ARGUMENT", "This mode requires ratio only, no coordinates/frame")
            if mode == "between":
                refs = [self.state.reference(h, {"point", "point2d", "vertex"}) for h in handles]
                point = factory.AddNewPointBetween(*refs, args["ratio"], 1)
            else:
                point = factory.AddNewPointOnCurveFromPercent(self.state.reference(handles[0], {"curve", "line", "line2d"}), args["ratio"], False)
        return self.finish(point, "point", args, container)

    def create_parameter(self, args):
        params = self.conn.get_active_part().Parameters
        if any(str(params.Item(i).Name) == args["name"] for i in range(1, params.Count + 1)):
            raise CADOperationError("AMBIGUOUS_REFERENCE", "Parameter name already exists")
        kind, value = args["kind"], args["value"]
        valid = {"length": type(value) in (int, float), "angle": type(value) in (int, float),
                 "real": type(value) in (int, float), "integer": type(value) is int,
                 "boolean": type(value) is bool, "string": type(value) is str}
        if not valid[kind]:
            raise CADOperationError("INVALID_ARGUMENT", "Value does not match parameter kind")
        if kind in {"length", "angle"}:
            parameter = params.CreateDimension(args["name"], "LENGTH" if kind == "length" else "ANGLE", 0)
            handle = self.state.mark_created(parameter, "parameter")
            data = dimension(parameter, value, "mm" if kind == "length" else "deg")
        else:
            method = {"real": "CreateReal", "integer": "CreateInteger", "boolean": "CreateBoolean", "string": "CreateString"}[kind]
            parameter = getattr(params, method)(args["name"], value)
            handle = self.state.mark_created(parameter, "parameter")
            data = {"value": parameter.Value}
        self.conn.get_active_part().Update()
        self.state.updated = True
        return {"ok": True, "handle": handle, "data": data}

    def create_formula(self, args):
        parameter = self.state.resolve(args["parameter_handle"], {"parameter"}).value
        formula = self.conn.get_active_part().Relations.CreateFormula(args["name"], "", parameter, args["expression"])
        handle = self.state.mark_created(formula, "relation")
        self.conn.get_active_part().Update()
        self.state.updated = True
        return {"ok": True, "handle": handle, "value": str(parameter.ValueAsString())}

    def measure(self, args):
        record = self.state.resolve(args["handle"])
        if record.kind in {"body", "geoset", "ordered_geoset", "parameter"}:
            raise CADOperationError("WRONG_GEOMETRY_TYPE", "Measure geometry, not a container/parameter")
        measurable = self.conn.active_document.GetWorkbench("SPAWorkbench").GetMeasurable(self.state.reference(args["handle"]))
        geometry = int(measurable.GeometryName)
        valid = {"area": {2, 3, 4, 5, 6, 7}, "volume": {2}}
        if geometry not in valid[args["property"]]:
            raise CADOperationError("WRONG_GEOMETRY_TYPE", f"GeometryName={geometry} does not support requested measurement")
        value = float(measurable.Area if args["property"] == "area" else measurable.Volume)
        if not math.isfinite(value) or value < 0:
            raise CADOperationError("POSTCONDITION_FAILED", "Invalid measurement")
        power = 2 if args["property"] == "area" else 3
        return {"ok": True, "geometry_name": geometry, "api_value": value, "api_unit": f"m^{power}",
                "value": value * 1000**power, "unit": f"mm^{power}", "frame": "active_part", "occurrence": None}
