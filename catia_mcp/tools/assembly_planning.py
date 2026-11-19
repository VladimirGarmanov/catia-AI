"""Assembly spatial context and deliberately typed axis/plane mating.

CAA references and Windows acceptance probes are documented in ASSEMBLY_DRAWING.md.
No name-based BRep construction, inferred cylinder axes or implicit grounding.
"""
from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.assembly_management import AssemblyManagementTools
from catia_mcp.tools.domain_support import verify_equal
from catia_mcp.tools.engineering import HANDLE, tool, dimension
from catia_mcp.tools.operations import array, group


READ_TOOLS = frozenset({"catia_assembly_spatial_context", "catia_assembly_mate_preview"})
IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1., 0., 0., 0.]
ORIENTATIONS = {"same": 0, "opposite": 1, "undefined": 2}
SIDES = {"positive": 0, "negative": 1, "undefined": 4}
ORIENTATION = {"orientation": {"enum": list(ORIENTATIONS)}}
# CatMeasurableName from CAA; these classify the exact Reference, not Value/Name.
GEOMETRIES = {4: "cylinder", 5: "sphere", 6: "cone", 7: "plane",
              9: "circle", 10: "line", 11: "point", 12: "axis_system"}
LINE, PLANE, POINT = 10, 7, 11
# mode -> (allowed ordered (first, second) measurable pairs, CatConstraintType).
# Order follows the CAA CatConstraintType 3D tables; supports given in the other
# order are swapped before AddBiEltCst, never reinterpreted.
MATES = {
    "axis_coincidence": ({(LINE, LINE)}, 2), "axis_parallel": ({(LINE, LINE)}, 8),
    "axis_perpendicular": ({(LINE, LINE)}, 11), "axis_offset": ({(LINE, LINE)}, 1),
    "axis_angle": ({(LINE, LINE)}, 6),
    "axis_in_plane": ({(LINE, PLANE)}, 2), "axis_plane_parallel": ({(LINE, PLANE)}, 8),
    "axis_plane_perpendicular": ({(LINE, PLANE)}, 11), "axis_plane_offset": ({(LINE, PLANE)}, 1),
    "plane_coincidence": ({(PLANE, PLANE)}, 2),
    "plane_offset": ({(PLANE, PLANE)}, 1), "plane_parallel": ({(PLANE, PLANE)}, 8),
    "plane_perpendicular": ({(PLANE, PLANE)}, 11), "plane_angle": ({(PLANE, PLANE)}, 6),
    "plane_contact": ({(PLANE, PLANE)}, 20), "point_coincidence": ({(POINT, POINT)}, 2),
    "point_on_axis": ({(POINT, LINE)}, 2), "point_on_plane": ({(POINT, PLANE)}, 2),
}
DISTANCE_MODES = {"plane_offset", "axis_offset", "axis_plane_offset"}
ANGLE_MODES = {"plane_angle", "axis_angle"}
# Measured postconditions after Update (SPA Measurable, product coordinates).
ZERO_DISTANCE = {"axis_coincidence", "axis_in_plane", "plane_coincidence", "plane_contact",
                 "point_coincidence", "point_on_axis", "point_on_plane"}
PARALLEL = {"axis_coincidence", "axis_parallel", "axis_offset", "plane_coincidence",
            "plane_parallel", "plane_offset", "plane_contact"}
PERPENDICULAR = {"axis_perpendicular", "plane_perpendicular"}
AXIS_HINT = ("Cylinder/cone faces are not axes. In that part create a native Axis with "
             "catia_wireframe_surface mode=axis_line from the face or circular edge, then select the Axis.")


def ordered_supports(mode, supports):
    """Return supports in the CAA element order for this mode, or None if incompatible."""
    pairs = MATES[mode][0]
    kinds = (supports[0][3], supports[1][3])
    if kinds in pairs:
        return list(supports)
    if kinds[::-1] in pairs:
        return [supports[1], supports[0]]
    return None


def angle_matches(value, degrees):
    """SPA angle unit is not stated by CAA: accept the degree or radian reading."""
    import math
    targets = {0: (0.0,), 90: (90.0, math.pi / 2), 180: (180.0, math.pi)}[degrees]
    return any(abs(value - target) <= 1e-4 * max(1.0, target) for target in targets)


def compose_pose(parent, local):
    """T_root_child = T_root_parent * T_parent_child, column-major axes, mm."""
    def rotate(vector):
        return [sum(parent[3*j+i] * vector[j] for j in range(3)) for i in range(3)]

    axes = [v for start in (0, 3, 6) for v in rotate(local[start:start+3])]
    origin = [x+y for x, y in zip(parent[9:], rotate(local[9:]))]
    return axes + origin


class AssemblyPlanningTools(AssemblyManagementTools):
    def get_tool_definitions(self):
        return [
            tool("catia_assembly_spatial_context", "Read occurrence tree, compose nested poses into active-root coordinates, and collect constraints/publications for planning. Origins are datum origins, NOT centers, extents or clearances. Missing parent poses propagate as unavailable; truncated data is not a complete assembly. No activation, movement, Update or save.", {
                "max_objects": {"type": "integer", "minimum": 1, "maximum": 2000},
                "max_depth": {"type": "integer", "minimum": 0, "maximum": 30},
            }, readonly=True),
            tool("catia_assembly_mate_preview", "Read two fresh selected exact supports, their immediate root occurrences, measured geometry types, current poses and compatible typed mate modes. Does NOT test solvability, infer an axis from a cylinder, or create constraints. Select actual lines for axis mates; a whole AxisSystem is not a line.", {
                "selection_handles": array(HANDLE, 2, 2),
            }, ["selection_handles"], True),
            group("catia_assembly_mate", "Create ONE deliberately typed assembly mate between two distinct immediate root occurrences. Both supports must be fresh exact selections. Axis modes require measured LINE references (e.g. a native Axis from catia_wireframe_surface mode=axis_line, a sketch/GSD line or an axis-system axis line), not cylindrical faces or whole AxisSystems. Plane modes require measured planes; mixed modes take one line/point and one plane/line in either selection order. After Update the SPA distance/angle between the supports is measured where the mode defines it. Applies orientation/side/value BEFORE one Update; verifies type, settings, active native status and reads resulting poses. Does not ground either part, prove global DOF, clearance or unique solution. Stop on failure; no implicit rollback.", {
                "axis_coincidence": ORIENTATION, "axis_parallel": ORIENTATION,
                "axis_perpendicular": {}, "plane_coincidence": ORIENTATION,
                "axis_offset": {**ORIENTATION, "distance_mm": {"type": "number", "minimum": 0}},
                "axis_angle": {"angle_deg": {"type": "number", "minimum": 0, "maximum": 180}},
                "axis_in_plane": {}, "axis_plane_parallel": {},
                "axis_plane_perpendicular": ORIENTATION,
                "axis_plane_offset": {"distance_mm": {"type": "number", "minimum": 0}},
                "point_on_axis": {}, "point_on_plane": {},
                "plane_offset": {**ORIENTATION,
                                 "distance_mm": {"type": "number", "minimum": 0},
                                 "side": {"enum": list(SIDES)}},
                "plane_parallel": ORIENTATION, "plane_perpendicular": {},
                "plane_angle": {"angle_deg": {"type": "number", "minimum": 0, "maximum": 180}},
                "plane_contact": {}, "point_coincidence": {},
            }, {"selection_handles": array(HANDLE, 2, 2),
                "name": {"type": "string", "minLength": 1, "maxLength": 128}}),
        ]

    def execute(self, name, args):
        return {"catia_assembly_spatial_context": self.spatial_context,
                "catia_assembly_mate_preview": self.preview,
                "catia_assembly_mate": self.mate}[name](args)

    def spatial_context(self, args):
        result = self.inspect({**args, "include_positions": True})
        by_handle = {}
        for row in result["products"]:
            parent = row["parent"]
            try:
                if parent is None:
                    # The root defines this frame. This is NOT a substitute for
                    # an unreadable child pose, and does not ground the root.
                    pose = list(IDENTITY)
                else:
                    local = row["axis_components"]
                    if local is None:
                        raise CADOperationError("POSITION_UNAVAILABLE", "Occurrence pose unreadable")
                    self.validate_pose(local)
                    parent_pose = by_handle[parent]["root_axis_components"]
                    if parent_pose is None:
                        raise CADOperationError("POSITION_UNAVAILABLE", "Ancestor pose unreadable")
                    pose = compose_pose(parent_pose, local)
                row["root_axis_components"] = pose
                row["origin_root_mm"] = pose[9:]
            except (CADOperationError, KeyError) as exc:
                row["root_axis_components"] = row["origin_root_mm"] = None
                row.setdefault("unavailable", {})["root_pose"] = str(exc)
            row["immediate_root_occurrence"] = parent is not None and by_handle[parent]["parent"] is None
            by_handle[row["handle"]] = row
        result.update(
            frame="active CATProduct root; rotation axes are columns; translation mm",
            spatial_complete=not result["truncated"] and all(
                row["root_axis_components"] is not None for row in result["products"]),
            fully_constrained=None, remaining_dof=None,
            limitations=["Origins are not geometric centers or bounding boxes; no clash/clearance inference.",
                         "Native constraint satisfaction is not global DOF or an intended mate graph.",
                         "Nested occurrences are read only; writes remain scoped to root children."],
        )
        return result

    def _pair(self, handles):
        if len(handles) != 2 or len(set(handles)) != 2:
            raise CADOperationError("INVALID_ARGUMENT", "Choose two distinct support handles")
        supports = []
        spa = self.conn.active_document.GetWorkbench("SPAWorkbench")
        for handle in handles:
            reference = self.selected_reference(handle)  # Validates revision, current selection, owner.
            record = self.state.resolve(handle)
            occurrence = self.conn.active_document.Selection.Item2(record.selection_index).LeafProduct
            measurable = spa.GetMeasurable(reference)
            geometry = int(measurable.GeometryName)
            supports.append((handle, reference, occurrence, geometry))
        if same_object(supports[0][2], supports[1][2]):
            raise CADOperationError("INVALID_ARGUMENT", "Assembly mate needs two different root occurrences")
        if same_object(supports[0][1], supports[1][1]):
            raise CADOperationError("INVALID_ARGUMENT", "Both handles resolve to the same exact Reference")
        return supports

    def _pose(self, occurrence):
        pose = read_array(occurrence.Position.GetComponents, 12)
        self.validate_pose(pose)
        return pose

    def _describe(self, supports):
        rows = []
        for handle, _, occurrence, geometry in supports:
            rows.append({"selection_handle": handle,
                         "component_handle": self.state.register(occurrence, "product"),
                         "component_name": str(occurrence.Name),
                         "geometry_type": geometry,
                         "geometry_kind": GEOMETRIES.get(geometry, "unsupported"),
                         "parent_axis_components": self._pose(occurrence)})
        return rows

    def preview(self, args):
        supports = self._pair(args["selection_handles"])
        allowed = [mode for mode in MATES if ordered_supports(mode, supports) is not None]
        warnings = ["Geometry kind is measured; support coordinates/normals are not measured here.",
                    "Refresh selection handles after each write. Preview does not reserve targets."]
        if any(s[3] in (4, 6) for s in supports):
            warnings.insert(0, AXIS_HINT)
        return {"ok": True, "supports": self._describe(supports), "compatible_modes": allowed,
                "solvability_checked": False, "remaining_dof": None, "warnings": warnings,
                "session": self.state.context(self.state.document_id())}

    def _measure(self, mode, first, second):
        """Measured distance/angle between the two supports; failures are unverified, not success."""
        try:
            spa = self.conn.active_document.GetWorkbench("SPAWorkbench")
            measurable = spa.GetMeasurable(first)
            distance = float(measurable.GetMinimumDistance(second))
            angle = None
            if mode in PARALLEL | PERPENDICULAR and POINT not in MATES[mode][0]:
                angle = float(measurable.GetAngleBetween(second))
        except Exception as exc:
            return {"status": "unverified", "reason": str(exc)}
        failures = []
        if mode in ZERO_DISTANCE and abs(distance) > 1e-3:
            failures.append(f"distance {distance} is not zero")
        if angle is not None and mode in PARALLEL and not (angle_matches(angle, 0) or angle_matches(angle, 180)):
            failures.append(f"angle {angle} is not parallel")
        if angle is not None and mode in PERPENDICULAR and not angle_matches(angle, 90):
            failures.append(f"angle {angle} is not perpendicular")
        return {"status": "failed" if failures else "passed", "minimum_distance": distance,
                "angle": angle, "failures": failures,
                "units": "SPA product coordinates; distance mm, angle unit unstated by CAA (deg or rad accepted)"}

    def mate(self, args):
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the sketch before assembly mating")
        root, mode = self.product(), args["mode"]
        supports = self._pair(args["selection_handles"])
        pairs, native_type = MATES[mode]
        ordered = ordered_supports(mode, supports)
        if ordered is None:
            needed = " or ".join(f"{GEOMETRIES[a]}+{GEOMETRIES[b]}" for a, b in sorted(pairs))
            hint = f" {AXIS_HINT}" if any(s[3] in (4, 6) for s in supports) else ""
            raise CADOperationError("WRONG_GEOMETRY_TYPE",
                f"{mode} needs {needed} supports; received "
                f"{[GEOMETRIES.get(s[3], s[3]) for s in supports]}. Select exact geometry; no inferred axes.{hint}")
        supports = ordered
        before = self._describe(supports)  # All reads complete before the first mutation.
        collection = root.Connections("CATIAConstraints")
        for i in range(1, collection.Count + 1):
            if str(collection.Item(i).Name) == args["name"]:
                raise CADOperationError("INVALID_ARGUMENT", "Constraint name exists; inspect it rather than duplicate it")
        self.state.mutation_started = True
        for row in before:
            self.changed(row["component_handle"])
        obj = collection.AddBiEltCst(native_type, supports[0][1], supports[1][1])
        handle = self.state.mark_created(obj, "constraint")
        obj.Name = args["name"]
        if "orientation" in args:
            obj.Orientation = ORIENTATIONS[args["orientation"]]
        if "side" in args:
            obj.Side = SIDES[args["side"]]
        expected_dimension = None
        if mode in DISTANCE_MODES | ANGLE_MODES:
            obj.Mode = 0  # catCstModeDrivingDimension
            if mode in ANGLE_MODES:
                obj.AngleSector = 0
            dimension(obj.Dimension, args["distance_mm"] if mode in DISTANCE_MODES else args["angle_deg"],
                      "mm" if mode in DISTANCE_MODES else "deg")
            expected_dimension = float(obj.Dimension.Value)
        result = self.update(root)
        verify_equal(int(obj.Type), native_type, "Mate type")
        verify_equal(str(obj.Name), args["name"], "Mate name")
        verify_equal(bool(obj.IsInactive()), False, "Mate active")
        verify_equal(int(obj.Status), 0, "Native mate solver status")
        if "orientation" in args:
            verify_equal(int(obj.Orientation), ORIENTATIONS[args["orientation"]], "Mate orientation")
        if "side" in args:
            verify_equal(int(obj.Side), SIDES[args["side"]], "Mate side")
        if expected_dimension is not None:
            verify_equal(float(obj.Dimension.Value), expected_dimension, "Mate dimension after Update")
            verify_equal(int(obj.Mode), 0, "Driving dimension")
        if mode in ANGLE_MODES:
            verify_equal(int(obj.AngleSector), 0, "Angle sector")
        after = self._describe(supports)
        measured = self._measure(mode, supports[0][1], supports[1][1])
        if measured["status"] == "failed":
            raise CADOperationError("WRONG_GEOMETRY_EFFECT",
                f"Mate {handle} is solver-satisfied but measured geometry disagrees: {measured['failures']}; inspect it")
        return {**result, "handle": handle, "mode": mode, "constraint": self.constraint_data(obj),
                "before": before, "after": after, "measured": measured,
                "support_order": [row[0] for row in supports], "native_constraint_satisfied": True,
                "remaining_dof": None, "global_assembly_verified": False,
                "warnings": ["Solver may move either occurrence and other connected parts. Reinspect the assembly at the stage boundary.",
                             "This does not prove clearance, a unique solution, or global full constraint."]}
