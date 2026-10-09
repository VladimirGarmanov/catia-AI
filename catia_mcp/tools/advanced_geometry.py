"""Documented wireframe/surface and solid constructors with explicit target handles."""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, dimension
from catia_mcp.tools.operations import (
    BOOL, VECTOR, POINT, LINE, CURVE, SURFACE, OperationTools, array, group, unit_vector,
)


WIRE_MODES = {
    "point_center": {"curve_handle": HANDLE},
    "point_curve_distance": {"curve_handle": HANDLE, "distance_mm": NUMBER, "reverse": BOOL},
    "point_curve_reference_distance": {"curve_handle": HANDLE, "point_handle": HANDLE, "distance_mm": NUMBER, "reverse": BOOL},
    "point_curve_reference_fraction": {"curve_handle": HANDLE, "point_handle": HANDLE, "fraction": {"type": "number", "minimum": 0, "maximum": 1}, "reverse": BOOL},
    "point_curve_direction": {"curve_handle": HANDLE, "direction": VECTOR, "distance_mm": NUMBER, "reverse": BOOL},
    "point_plane_reference": {"plane_handle": HANDLE, "point_handle": HANDLE, "plane_coordinates_mm": array(NUMBER, 2, 2)},
    "point_surface_reference": {"surface_handle": HANDLE, "point_handle": HANDLE, "direction": VECTOR, "distance_mm": NUMBER},
    "point_surface": {"surface_handle": HANDLE, "direction": VECTOR, "distance_mm": NUMBER},
    "line_point_direction": {"point_handle": HANDLE, "direction": VECTOR, "begin_mm": NUMBER, "end_mm": NUMBER},
    "line_normal": {"surface_handle": HANDLE, "point_handle": HANDLE, "begin_mm": NUMBER, "end_mm": NUMBER},
    "line_tangent": {"curve_handle": HANDLE, "point_handle": HANDLE, "begin_mm": NUMBER, "end_mm": NUMBER},
    "plane_angle": {"plane_handle": HANDLE, "axis_handle": HANDLE, "angle_deg": NUMBER, "reverse": BOOL},
    "plane_curve": {"curve_handle": HANDLE},
    "plane_mean": {"point_handles": array(HANDLE, 3)},
    "cylinder": {"point_handle": HANDLE, "direction": VECTOR, "radius_mm": POSITIVE, "first_length_mm": POSITIVE, "second_length_mm": POSITIVE},
    "sphere": {"point_handle": HANDLE, "axis_handle": HANDLE, "radius_mm": POSITIVE,
               "parallel_begin_deg": NUMBER, "parallel_end_deg": NUMBER,
               "meridian_begin_deg": NUMBER, "meridian_end_deg": NUMBER},
    "helix": {"axis_handle": HANDLE, "point_handle": HANDLE, "pitch_mm": POSITIVE, "height_mm": POSITIVE,
              "clockwise": BOOL, "start_angle_deg": NUMBER, "taper_angle_deg": NUMBER, "taper_outward": BOOL},
    "extract": {"source_handle": HANDLE, "propagation": {"enum": [1, 2, 3]}},
    "boundary": {"surface_handle": HANDLE},
    "extrapolate": {"boundary_handle": HANDLE, "surface_handle": HANDLE, "length_mm": POSITIVE},
    "extrapolate_until": {"boundary_handle": HANDLE, "surface_handle": HANDLE, "until_handle": HANDLE},
    "healing": {"surface_handle": HANDLE, "distance_mm": POSITIVE, "tangency_deg": POSITIVE},
    "curve_smooth": {"curve_handle": HANDLE, "deviation_mm": POSITIVE, "tangency_deg": POSITIVE},
    "remove_face": {"keep_face_handle": HANDLE, "remove_face_handle": HANDLE},
    "replace_face": {"surface_handle": HANDLE, "remove_face_handle": HANDLE, "side": {"enum": [-1, 1]}},
}

SOLID_MODES = {
    "user_pattern": {"feature_handle": HANDLE, "positions_sketch_handle": HANDLE, "anchor_handle": HANDLE, "instances": {"type": "integer", "minimum": 2}},
    "stiffener": {"sketch_handle": HANDLE, "thickness_mm": POSITIVE, "symmetric": BOOL, "from_top": BOOL},
    "face_fillet": {"first_face_handle": HANDLE, "second_face_handle": HANDLE, "radius_mm": POSITIVE},
    "tritangent_fillet": {"first_face_handle": HANDLE, "second_face_handle": HANDLE, "remove_face_handle": HANDLE},
    "variable_fillet": {"edge_handle": HANDLE, "radius_mm": POSITIVE,
                        "propagation": {"enum": [0, 1]}, "variation": {"enum": [0, 1]},
                        "vertices": array({"type": "object", "properties": {"handle": HANDLE, "radius_mm": POSITIVE},
                                           "required": ["handle", "radius_mm"], "additionalProperties": False}, 0)},
    "rotate": {"axis_handle": HANDLE, "angle_deg": NUMBER},
    "translate": {"direction": VECTOR, "distance_mm": NUMBER},
    "affinity": {"origin_handle": HANDLE, "plane_handle": HANDLE, "axis_handle": HANDLE,
                 "x_ratio": POSITIVE, "y_ratio": POSITIVE, "z_ratio": POSITIVE},
    "scale": {"reference_handle": HANDLE, "factor": POSITIVE},
    "split": {"surface_handle": HANDLE, "side": {"enum": [0, 1]}},
}


class AdvancedGeometryTools(OperationTools):
    def get_tool_definitions(self):
        return [
            group("catia_wireframe_surface", "Typed GSD operations. Part-frame directions; lengths mm, angles deg. Exact face/edge handles require current selection. Live Windows verification pending.", WIRE_MODES, {"container_handle": HANDLE}),
            group("catia_solid_operation", "Additional Part Design features in an explicit Body. Constructors followed by Update/readback; no silent fallback or deletion.", SOLID_MODES, {"body_handle": HANDLE}),
            group("catia_profile_solids", "Explicit geometry-equivalent alternative to Multi Pad/Multi Pocket: creates SEPARATE ordinary features from separate sketches, each with its own depth. Not a native multi-domain feature. Stops at first failed Update; never rolls back or retries.", {
                "pads": {}, "pockets": {},
            }, {"body_handle": HANDLE, "profiles": array({"type": "object", "properties": {
                    "sketch_handle": HANDLE, "depth_mm": POSITIVE},
                    "required": ["sketch_handle", "depth_mm"], "additionalProperties": False}, 2, 100)}),
            group("catia_axis_system", "Create an orthonormal axis system in the active Part; origin mm in Part coordinates.",
                  {"create": {"origin_mm": VECTOR, "x_direction": VECTOR, "y_direction": VECTOR}}),
            group("catia_feature_options", "Modify documented properties of an existing feature. Use exact handles, not tree-name guesses. No arbitrary property setting.", {
                "prism_second_limit": {"feature_handle": HANDLE, "length_mm": POSITIVE},
                "prism_direction": {"feature_handle": HANDLE, "direction_handle": HANDLE},
                "hole_thread": {"feature_handle": HANDLE, "description": HANDLE, "pitch_mm": POSITIVE, "depth_mm": POSITIVE},
                "draft_add_faces": {"feature_handle": HANDLE, "domain_index": {"type": "integer", "minimum": 1}, "faces": array(HANDLE)},
                "shell_add_faces": {"feature_handle": HANDLE, "faces": array(HANDLE)},
                "loft_guides": {"feature_handle": HANDLE, "guides": array(HANDLE), "coupling": {"enum": [1, 2, 3, 4]}},
            }),
        ]

    def execute(self, name, a):
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition before 3D operations")
        if name == "catia_wireframe_surface":
            return self.wireframe(a)
        if name == "catia_solid_operation":
            return self.solid(a)
        if name == "catia_feature_options":
            return self.options(a)
        if name == "catia_profile_solids":
            return self.profile_solids(a)
        x, y = unit_vector(a["x_direction"]), unit_vector(a["y_direction"])
        if abs(sum(u * v for u, v in zip(x, y))) > 1e-8:
            raise CADOperationError("INVALID_ARGUMENT", "Axis directions must be perpendicular")
        axis = self.conn.get_active_part().AxisSystems.Add()
        self.state.mark_created(axis, "axis_system")
        axis.PutOrigin(tuple(a["origin_mm"]))
        axis.PutVectors(x, y)
        return self.finish(axis, "axis_system")

    def wireframe(self, a):
        container = self.obj(a["container_handle"], {"geoset"})
        f = self.conn.get_active_part().HybridShapeFactory
        m = a["mode"]
        # Resolve every supplied reference before any constructor can change the tree.
        kinds = {"point_handle": POINT, "axis_handle": LINE | {"axis_system"}, "curve_handle": CURVE,
                 "plane_handle": {"plane"}, "surface_handle": SURFACE, "boundary_handle": CURVE,
                 "until_handle": SURFACE, "keep_face_handle": {"face"}, "remove_face_handle": {"face"},
                 "source_handle": CURVE | SURFACE | POINT}
        r = {key: self.ref(a[key], types) for key, types in kinds.items() if key in a}
        if "begin_mm" in a and a["begin_mm"] >= a["end_mm"]:
            raise CADOperationError("INVALID_ARGUMENT", "Line begin must be smaller than end")
        direction = None
        if "direction" in a:
            direction = f.AddNewDirectionByCoord(*unit_vector(a["direction"]))
        kind = "surface"
        if m == "point_center":
            obj, kind = f.AddNewPointCenter(r["curve_handle"]), "point"
        elif m == "point_curve_distance":
            obj, kind = f.AddNewPointOnCurveFromDistance(r["curve_handle"], a["distance_mm"], a["reverse"]), "point"
        elif m == "point_curve_reference_distance":
            obj, kind = f.AddNewPointOnCurveWithReferenceFromDistance(r["curve_handle"], r["point_handle"], a["distance_mm"], a["reverse"]), "point"
        elif m == "point_curve_reference_fraction":
            obj, kind = f.AddNewPointOnCurveWithReferenceFromPercent(r["curve_handle"], r["point_handle"], a["fraction"], a["reverse"]), "point"
        elif m == "point_curve_direction":
            obj, kind = f.AddNewPointOnCurveAlongDirection(r["curve_handle"], a["distance_mm"], a["reverse"], direction), "point"
        elif m == "point_plane_reference":
            obj, kind = f.AddNewPointOnPlaneWithReference(r["plane_handle"], r["point_handle"], *a["plane_coordinates_mm"]), "point"
        elif m == "point_surface_reference":
            obj, kind = f.AddNewPointOnSurfaceWithReference(r["surface_handle"], r["point_handle"], direction, a["distance_mm"]), "point"
        elif m == "point_surface":
            obj, kind = f.AddNewPointOnSurface(r["surface_handle"], direction, a["distance_mm"]), "point"
        elif m == "line_point_direction":
            obj, kind = f.AddNewLinePtDir(r["point_handle"], direction, a["begin_mm"], a["end_mm"], False), "line"
        elif m == "line_normal":
            obj, kind = f.AddNewLineNormal(r["surface_handle"], r["point_handle"], a["begin_mm"], a["end_mm"], False), "line"
        elif m == "line_tangent":
            obj, kind = f.AddNewLineTangency(r["curve_handle"], r["point_handle"], a["begin_mm"], a["end_mm"], False), "line"
        elif m == "plane_angle":
            obj, kind = f.AddNewPlaneAngle(r["plane_handle"], r["axis_handle"], a["angle_deg"], a["reverse"]), "plane"
        elif m == "plane_curve":
            obj, kind = f.AddNewPlane1Curve(r["curve_handle"]), "plane"
        elif m == "plane_mean":
            points = tuple(self.ref(h, POINT) for h in a["point_handles"])
            obj, kind = f.AddNewPlaneMean(points, len(points)), "plane"
        elif m == "cylinder":
            obj = f.AddNewCylinder(r["point_handle"], a["radius_mm"], a["first_length_mm"], a["second_length_mm"], direction)
        elif m == "sphere":
            if not (-90 <= a["parallel_begin_deg"] < a["parallel_end_deg"] <= 90 and
                    0 < a["meridian_end_deg"] - a["meridian_begin_deg"] <= 360):
                raise CADOperationError("INVALID_ARGUMENT", "Invalid sphere angular limits")
            obj = f.AddNewSphere(r["point_handle"], r["axis_handle"], a["radius_mm"], a["parallel_begin_deg"], a["parallel_end_deg"], a["meridian_begin_deg"], a["meridian_end_deg"])
        elif m == "helix":
            obj = f.AddNewHelix(r["axis_handle"], False, r["point_handle"], a["pitch_mm"], a["height_mm"], a["clockwise"], a["start_angle_deg"], a["taper_angle_deg"], a["taper_outward"])
            kind = "curve"
        elif m == "extract":
            source_kind = self.state.resolve(a["source_handle"]).kind
            kind = "surface" if source_kind in SURFACE else "curve" if source_kind in CURVE else "point"
            obj = f.AddNewExtract(r["source_handle"])
            self.state.mark_created(obj, kind)
            obj.PropagationType = a["propagation"]
        elif m == "boundary":
            obj, kind = f.AddNewBoundaryOfSurface(r["surface_handle"]), "curve"
        elif m == "extrapolate":
            obj = f.AddNewExtrapolLength(r["boundary_handle"], r["surface_handle"], a["length_mm"])
        elif m == "extrapolate_until":
            obj = f.AddNewExtrapolUntil(r["boundary_handle"], r["surface_handle"], r["until_handle"])
        elif m == "healing":
            obj = f.AddNewHealing(r["surface_handle"])
            self.state.mark_created(obj, kind)
            obj.SetDistanceObjective(a["distance_mm"])
            # TangencyObjective is a LENGTH, not an angle. Use the Angle object.
            dimension(obj.TangencyAngle, a["tangency_deg"], "deg")
        elif m == "curve_smooth":
            obj, kind = f.AddNewCurveSmooth(r["curve_handle"]), "curve"
            self.state.mark_created(obj, kind)
            obj.MaximumDeviationActivity = True
            obj.SetMaximumDeviation(a["deviation_mm"])
            dimension(obj.TangencyThreshold, a["tangency_deg"], "deg")
        elif m == "remove_face":
            obj = f.AddNewRemoveFace(r["keep_face_handle"], r["remove_face_handle"])
        else:  # replace_face; mode has already passed the discriminated schema.
            obj = f.AddNewReplaceFace(r["surface_handle"], r["remove_face_handle"], a["side"])
        return self.finish(obj, kind, container)

    def profile_solids(self, a):
        body = self.obj(a["body_handle"], {"body"})
        profiles = [(self.obj(row["sketch_handle"], {"sketch"}), row["depth_mm"]) for row in a["profiles"]]
        # Validate the entire batch before even changing InWorkObject.
        if any(not any(same_object(sketch, body.Sketches.Item(i)) for i in range(1, body.Sketches.Count + 1))
               for sketch, _ in profiles):
            raise CADOperationError("INVALID_ARGUMENT", "Every profile must belong to the specified Body")
        if any(same_object(sketch, other) for i, (sketch, _) in enumerate(profiles) for other, _ in profiles[i+1:]):
            raise CADOperationError("INVALID_ARGUMENT", "Duplicate sketch in feature sequence")
        part = self.conn.get_active_part()
        constructor = part.ShapeFactory.AddNewPad if a["mode"] == "pads" else part.ShapeFactory.AddNewPocket
        self.engineering.body(a["body_handle"])
        results = []
        for index, (sketch, depth) in enumerate(profiles):
            try:
                feature = constructor(sketch, depth)
                self.state.mark_created(feature, "feature")
                dimension(feature.FirstLimit.Dimension, depth, "mm")
                result = self.finish(feature)
                result["depth_readback"] = str(feature.FirstLimit.Dimension.ValueAsString())
                part.InWorkObject = feature
                results.append(result)
            except Exception as exc:
                raise CADOperationError("PARTIAL_MUTATION", f"Feature sequence stopped at index {index} (zero-based); {len(results)} features completed. Inspect created_handles; no rollback. {exc}") from exc
        return {"ok": True, "features": results, "native_multi_domain_feature": False,
                "warning": "Separate features; profile closure and resulting material volume need independent verification"}

    def solid(self, a):
        m = a["mode"]
        types = {"sketch_handle": {"sketch"}, "first_face_handle": {"face"}, "second_face_handle": {"face"},
                 "remove_face_handle": {"face"}, "edge_handle": {"edge"}, "axis_handle": LINE,
                 "reference_handle": POINT | {"plane"}, "surface_handle": SURFACE,
                 "origin_handle": POINT, "plane_handle": {"plane"}}
        r = {k: self.ref(a[k], v) for k, v in types.items() if k in a and k != "sketch_handle"}
        sketch = self.obj(a["sketch_handle"], {"sketch"}) if "sketch_handle" in a else None
        pattern_feature = self.obj(a["feature_handle"], {"feature"}) if "feature_handle" in a else None
        positions = self.obj(a["positions_sketch_handle"], {"sketch"}) if "positions_sketch_handle" in a else None
        anchor = self.obj(a["anchor_handle"], POINT | {"point2d"}) if "anchor_handle" in a else None
        vertices = [(self.ref(v["handle"], {"vertex"}), v["radius_mm"]) for v in a.get("vertices", [])]
        direction = unit_vector(a["direction"]) if "direction" in a else None
        self.engineering.body(a["body_handle"])
        f = self.conn.get_active_part().ShapeFactory
        if m == "user_pattern":
            obj = f.AddNewUserPattern(pattern_feature, a["instances"])
            self.state.mark_created(obj, "feature")
            obj.AnchorPoint = anchor
            obj.AddFeatureToLocatePositions(positions)
        elif m == "stiffener":
            obj = f.AddNewStiffener(sketch)
            self.state.mark_created(obj, "feature")
            obj.IsFromTop, obj.IsSymmetric = a["from_top"], a["symmetric"]
            dimension(obj.Thickness, a["thickness_mm"], "mm")
        elif m == "face_fillet":
            obj = f.AddNewFaceFillet(r["first_face_handle"], r["second_face_handle"], a["radius_mm"])
        elif m == "tritangent_fillet":
            obj = f.AddNewTritangentFillet(r["first_face_handle"], r["second_face_handle"], r["remove_face_handle"])
        elif m == "variable_fillet":
            obj = f.AddNewEdgeFilletWithVaryingRadius(r["edge_handle"], a["propagation"], a["variation"], a["radius_mm"])
            self.state.mark_created(obj, "feature")
            for ref, radius in vertices:
                obj.AddImposedVertex(ref, radius)
        elif m == "rotate":
            obj = f.AddNewRotate2(r["axis_handle"], a["angle_deg"])
        elif m == "translate":
            vector = self.conn.get_active_part().HybridShapeFactory.AddNewDirectionByCoord(*direction)
            obj = f.AddNewTranslate2(a["distance_mm"])
            self.state.mark_created(obj, "feature")
            obj.HybridShape.VectorType = 0
            obj.HybridShape.Direction = vector
            dimension(obj.HybridShape.Distance, a["distance_mm"], "mm")
        elif m == "affinity":
            obj = f.AddNewAffinity2(a["x_ratio"], a["y_ratio"], a["z_ratio"])
            self.state.mark_created(obj, "feature")
            hybrid = obj.HybridShape
            hybrid.AxisOrigin, hybrid.AxisPlane, hybrid.AxisFirstDirection = r["origin_handle"], r["plane_handle"], r["axis_handle"]
        elif m == "scale":
            obj = f.AddNewScaling(r["reference_handle"], a["factor"])
        else:
            obj = f.AddNewSplit(r["surface_handle"], a["side"])
        return self.finish(obj)

    def options(self, a):
        obj = self.obj(a["feature_handle"], {"feature"})
        refs = [self.ref(h, {"face"}) for h in a.get("faces", [])]
        guides = [self.ref(h, CURVE) for h in a.get("guides", [])]
        direction = self.ref(a["direction_handle"], LINE) if "direction_handle" in a else None
        self.changed(a["feature_handle"])
        if a["mode"] == "prism_second_limit":
            obj.IsSymmetric = False
            obj.SecondLimit.LimitMode = 0
            dimension(obj.SecondLimit.Dimension, a["length_mm"], "mm")
        elif a["mode"] == "prism_direction":
            obj.DirectionType = 1
            obj.SetDirection(direction)
        elif a["mode"] == "hole_thread":
            # Verified in official pycatia enumeration_types.py; absent in package subset.
            obj.ThreadingMode = 0  # catThreadedHoleThreading
            obj.HoleThreadDescription.Value = a["description"]
            dimension(obj.ThreadPitch, a["pitch_mm"], "mm")
            dimension(obj.ThreadDepth, a["depth_mm"], "mm")
        elif a["mode"] == "draft_add_faces":
            domain = obj.DraftDomains.Item(a["domain_index"])
            for ref in refs:
                domain.AddFaceToDraft(ref)
        elif a["mode"] == "shell_add_faces":
            for ref in refs:
                obj.AddFaceToRemove(ref)
        else:
            hybrid = obj.HybridShape
            for ref in guides:
                hybrid.AddGuide(ref)
            hybrid.SectionCoupling = a["coupling"]
        return self.update(self.conn.get_active_part())
