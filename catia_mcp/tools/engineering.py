"""Typed, handle-based operations. No arbitrary COM method/property execution."""
from __future__ import annotations

import math

from catia_mcp.runtime import CADOperationError, same_object


HANDLE = {"type": "string", "minLength": 1}
NUMBER = {"type": "number"}
POSITIVE = {"type": "number", "exclusiveMinimum": 0}


TREE_CHILDREN = {"body": [("Sketches", "sketch"), ("Shapes", "feature"), ("HybridShapes", "geometry"),
                          ("HybridBodies", "geoset"), ("OrderedGeometricalSets", "ordered_geoset")],
                 "geoset": [("HybridShapes", "geometry"), ("HybridSketches", "sketch"), ("HybridBodies", "geoset")],
                 "ordered_geoset": [("HybridShapes", "geometry"), ("Sketches", "sketch"),
                                    ("OrderedGeometricalSets", "ordered_geoset")]}
SKETCH_INTERNAL_KINDS = frozenset({"constraint", "point2d", "line2d", "circle2d", "ellipse2d"})
PARAMETER_ACCESS = {0: "read_only", 1: "read_write", 2: "user"}


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
            tool("catia_list_objects", "Enumerate CATPart objects with session handles; no topology guessing. Default scope is the session focus (catia_set_focus), else the whole Part. Compact by default: no parameters and no sketch GeometricElements/Constraints unless requested or scoped to that sketch; omitted counts are reported. Selection handles require the same live selection and expire on writes.",
                 {"max_objects": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
                  "scope_handle": {**HANDLE, "description": "Body/geoset/ordered_geoset/sketch handle: list only that subtree"},
                  "ignore_focus": {"type": "boolean", "default": False, "description": "List the whole Part even when a focus is set"},
                  "kinds": {"type": "array", "items": HANDLE, "minItems": 1, "maxItems": 32, "uniqueItems": True,
                            "description": "Emit only these kinds, e.g. body, sketch, feature, plane, point, line, surface, parameter"},
                  "include_parameters": {"type": "boolean", "default": False},
                  "parameter_filter": {"type": "string", "minLength": 1, "maxLength": 256, "description": "Case-insensitive name substring"},
                  "include_internal_parameters": {"type": "boolean", "default": False,
                                                  "description": "Also feature/internal parameters (UserAccessMode 0/1); default only user parameters (UserAccessMode 2)"},
                  "include_sketch_internals": {"type": "boolean", "default": False}}, readonly=True),
            tool("catia_set_focus", "Session-only focus on the part being modeled: document_id plus optional Body/geoset handle used as default scope by catia_list_objects/catia_list_features. Does not activate, select or change CATIA. Cleared automatically when the active document changes.",
                 {"document_id": HANDLE, "scope_handle": HANDLE, "clear": {"type": "boolean", "default": False}},
                 ["document_id"], readonly=True),
            tool("catia_rename_object", "Rename an existing whole tree object by handle: Part bodies/features/sketches/GSD/constraints/relations/parameters, root assembly occurrences/constraints/publications, or Drawing sheets/views/annotations. Read tree handles first; selection/BRep handles, files and built-in origins are excluded. Component Name is instance name, not PartNumber; drawing text Name is not displayed Text; view Name changes its prefix. Parameter.Rename sets a global name. Metadata only: reads name back, leaves sketch edition open and does not run geometry Update or Save. Duplicate sibling names are rejected.",
                 {"handle": HANDLE, "new_name": {"type": "string", "minLength": 1, "maxLength": 1024},
                  "expected_name": {"type": "string", "description": "Optional exact old Name from discovery; reject external renaming"}},
                 ["handle", "new_name"]),
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
            tool("catia_reference_point", "Legacy subset: point in a HybridBody by absolute Part mm, plane-local mm, between points or curve fraction. Prefer catia_point (full Point Definition dialog modes with readback).",
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
        if name == "catia_rename_object":
            from catia_mcp.tools.naming import rename_object
            return rename_object(self, args)
        methods = {"catia_list_objects": self.list_objects, "catia_set_focus": self.set_focus,
                   "catia_create_container": self.create_container,
                   "catia_feature_state": self.feature_state, "catia_select_objects": self.select_objects,
                   "catia_swept_solid": self.swept_solid, "catia_boolean": self.boolean,
                   "catia_solid_loft": self.solid_loft, "catia_reference_plane": self.reference_plane,
                   "catia_reference_point": self.reference_point,
                   "catia_create_parameter": self.create_parameter, "catia_create_formula": self.create_formula,
                   "catia_measure_object": self.measure}
        return methods[name](args)

    def set_focus(self, args):
        state = self.state
        if state.bound_document != args["document_id"]:
            raise CADOperationError("MODEL_CONTEXT_REQUIRED", "Read catia_get_model_state for this document before setting focus")
        if args.get("clear"):
            if "scope_handle" in args:
                raise CADOperationError("INVALID_ARGUMENT", "clear=true takes no scope_handle")
            state.focus, state.focus_cleared = None, None
            return {"ok": True, "focus": None, "session": state.context(args["document_id"])}
        focus = state.set_focus(args["document_id"], args.get("scope_handle"))
        return {"ok": True, "focus": focus, "session": state.context(args["document_id"]),
                "note": "Session-only default read scope; CATIA document, selection and InWorkObject unchanged"}

    def list_objects(self, args):
        limit = args.get("max_objects", 500)
        kinds = set(args["kinds"]) if args.get("kinds") else None
        include_parameters = args.get("include_parameters", False)
        if not include_parameters and ("parameter_filter" in args or args.get("include_internal_parameters")):
            raise CADOperationError("INVALID_ARGUMENT", "parameter_filter/include_internal_parameters require include_parameters=true")
        if kinds and "parameter" in kinds and not include_parameters:
            raise CADOperationError("INVALID_ARGUMENT", "kind 'parameter' requires include_parameters=true")
        if "scope_handle" in args and args.get("ignore_focus"):
            raise CADOperationError("INVALID_ARGUMENT", "Choose scope_handle OR ignore_focus")
        part = self.conn.get_active_part()
        scope, source, scope_handle = None, "part", args.get("scope_handle")
        if scope_handle:
            scope, source = self.state.resolve(scope_handle, {"body", "geoset", "ordered_geoset", "sketch"}), "argument"
        elif not args.get("ignore_focus"):
            focus = self.state.current_focus()
            if focus and focus.get("handle"):
                scope_handle = focus["handle"]
                scope, source = self.state.resolve(scope_handle), "focus"
        expand_sketches = args.get("include_sketch_internals", False) or (scope is not None and scope.kind == "sketch")
        if kinds and kinds & SKETCH_INTERNAL_KINDS and not expand_sketches:
            raise CADOperationError("INVALID_ARGUMENT", "Sketch element/constraint kinds require include_sketch_internals=true or a sketch scope_handle")
        result, warnings, omitted = [], [], {}
        dropped = False

        def add(value, kind, parent=None, extra=None, **kwargs):
            nonlocal dropped
            if len(result) >= limit:
                dropped = True
                return None
            if kind == "geometry":
                kind = geometry_kind(value)
            handle = self.state.register(value, kind, **kwargs)
            if kinds is None or kind in kinds:
                entry = {"handle": handle, "kind": kind, "name": str(getattr(value, "Name", ""))}
                if parent:
                    entry["container"] = parent
                entry.update({k: v for k, v in (extra or {}).items() if v not in (None, "")})
                result.append(entry)
            return handle

        def visit_one(obj, kind, parent=None, depth=0):
            handle = add(obj, kind, parent)
            if handle is None:
                return False
            children = TREE_CHILDREN.get(kind, [])
            if kind == "sketch":
                if expand_sketches:
                    children = [("GeometricElements", "geometry"), ("Constraints", "constraint")]
                else:
                    omitted["sketch_internals"] = omitted.get("sketch_internals", 0) + 1
            for attribute, child_kind in children:
                try:
                    visit(getattr(obj, attribute), child_kind, handle, depth + 1)
                except Exception as exc:
                    warnings.append(f"{obj.Name}.{attribute}: {exc}")
            return True

        def visit(collection, kind, parent=None, depth=0):
            if depth > 30 or dropped:
                return
            for index in range(1, collection.Count + 1):
                if not visit_one(collection.Item(index), kind, parent, depth):
                    break

        if scope is not None:
            visit_one(scope.value, scope.kind)
        else:
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
        if include_parameters and (kinds is None or "parameter" in kinds):
            self._list_parameters(part, scope, args, add, omitted, warnings)
        else:
            try:
                omitted["parameters"] = int(self._scope_parameters(part, scope).Count)
            except Exception as exc:
                warnings.append(f"Parameters.Count: {exc}")
        scope_info = {"source": source}
        if scope is not None:
            scope_info.update(handle=scope_handle, kind=scope.kind, name=str(scope.value.Name))
        data = {"ok": True, "objects": result, "scope": scope_info,
                "session": self.state.context(self.state.document_id()),
                "truncated": dropped, "warnings": warnings}
        focus = self.state.focus_report()
        if focus:
            data["focus"] = focus
        if include_parameters:
            data["parameter_classification"] = {"basis": "Parameter.UserAccessMode == 2 (user)",
                                                "live_validated": False}
        if omitted:
            data["omitted"] = omitted
        return data

    @staticmethod
    def _scope_parameters(part, scope):
        # Read-only CAA KnowledgeInterfaces: Parameters.SubList(iObject, iRecursively)
        # returns the parameters owned by the scope subtree; whole Part otherwise.
        return part.Parameters.SubList(scope.value, True) if scope is not None else part.Parameters

    def _list_parameters(self, part, scope, args, add, omitted, warnings):
        # Parameter.UserAccessMode: 0 read-only, 1 read/write, 2 user parameter.
        # A COM failure here must not lose the tree handles gathered already.
        try:
            parameters = self._scope_parameters(part, scope)
            count = int(parameters.Count)
        except Exception as exc:
            warnings.append(f"Parameters.SubList: {exc}")
            omitted["parameters"] = "unreadable"
            return
        needle = args.get("parameter_filter", "").lower()
        internal = args.get("include_internal_parameters", False)
        hidden = unknown = unreadable = 0
        for index in range(1, count + 1):
            try:
                parameter = parameters.Item(index)
                name = str(parameter.Name)
            except Exception as exc:
                warnings.append(f"Parameters.Item({index}): {exc}")
                unreadable += 1
                continue
            if needle and needle not in name.lower():
                continue
            try:
                mode = int(parameter.UserAccessMode)
            except Exception:
                mode = None
            if mode != 2 and not internal:
                if mode is None:
                    unknown += 1
                else:
                    hidden += 1
                continue
            try:
                value = parameter.ValueAsString
                value = str(value() if callable(value) else value)
            except Exception:
                value = None
            access = PARAMETER_ACCESS.get(mode, "unknown") if internal else None
            if add(parameter, "parameter", extra={"value": value, "access": access}) is None:
                break
        if hidden:
            omitted["internal_parameters"] = hidden
        if unknown:
            omitted["unclassified_parameters"] = unknown
            warnings.append(f"{unknown} parameters omitted: UserAccessMode unreadable")
        if unreadable:
            omitted["unreadable_parameters"] = unreadable

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
