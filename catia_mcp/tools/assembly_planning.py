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
# mode -> (required measurable type on BOTH supports, CatConstraintType)
MATES = {
    "axis_coincidence": (10, 2), "axis_parallel": (10, 8),
    "axis_perpendicular": (10, 11), "plane_coincidence": (7, 2),
    "plane_offset": (7, 1), "plane_parallel": (7, 8),
    "plane_perpendicular": (7, 11), "plane_angle": (7, 6),
    "plane_contact": (7, 20), "point_coincidence": (11, 2),
}


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
            group("catia_assembly_mate", "Create ONE deliberately typed assembly mate between two distinct immediate root occurrences. Both supports must be fresh exact selections. Axis modes require measured LINE references, not cylindrical faces or AxisSystems. Plane modes require measured planes. Applies orientation/side/value BEFORE one Update; verifies type, settings, active native status and reads resulting poses. Does not ground either part, prove global DOF, clearance or unique solution. Stop on failure; no implicit rollback.", {
                "axis_coincidence": ORIENTATION, "axis_parallel": ORIENTATION,
                "axis_perpendicular": {}, "plane_coincidence": ORIENTATION,
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
        allowed = [mode for mode, (kind, _) in MATES.items()
                   if all(s[3] == kind for s in supports)]
        return {"ok": True, "supports": self._describe(supports), "compatible_modes": allowed,
                "solvability_checked": False, "remaining_dof": None,
                "warnings": ["Geometry kind is measured; support coordinates/normals are not measured here.",
                             "Coaxial mating requires explicit line-axis References. Cylinder faces are not substituted.",
                             "Refresh selection handles after each write. Preview does not reserve targets."],
                "session": self.state.context(self.state.document_id())}

    def mate(self, args):
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the sketch before assembly mating")
        root, mode = self.product(), args["mode"]
        supports = self._pair(args["selection_handles"])
        geometry, native_type = MATES[mode]
        if any(s[3] != geometry for s in supports):
            raise CADOperationError("WRONG_GEOMETRY_TYPE",
                f"{mode} needs two {GEOMETRIES[geometry]} supports; received "
                f"{[GEOMETRIES.get(s[3], s[3]) for s in supports]}. Select exact geometry; no inferred axes.")
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
        if mode in {"plane_offset", "plane_angle"}:
            obj.Mode = 0  # catCstModeDrivingDimension
            if mode == "plane_angle":
                obj.AngleSector = 0
            dimension(obj.Dimension, args["distance_mm"] if mode == "plane_offset" else args["angle_deg"],
                      "mm" if mode == "plane_offset" else "deg")
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
        if mode == "plane_angle":
            verify_equal(int(obj.AngleSector), 0, "Angle sector")
        after = self._describe(supports)
        return {**result, "handle": handle, "mode": mode, "constraint": self.constraint_data(obj),
                "before": before, "after": after, "native_constraint_satisfied": True,
                "remaining_dof": None, "global_assembly_verified": False,
                "warnings": ["Solver may move either occurrence and other connected parts. Reinspect the assembly at the stage boundary.",
                             "This does not prove clearance, a unique solution, or global full constraint."]}
