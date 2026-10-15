"""Advanced, explicitly allowlisted CAA ShapeFactory contracts.

Source: downloaded V5Automation/PartInterfaces/ShapeFactory and object pages.
No generic COM invocation, silent retries, or claim of native GUI equivalence.
"""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, dimension
from catia_mcp.tools.operations import OperationTools, BOOL, VECTOR, LINE, CURVE, array, group, unit_vector


COUNT = {"type": "integer", "minimum": 1, "maximum": 1000}
ANGLE = {"type": "number", "minimum": 0, "maximum": 360}
FACE_PAIR = {"type": "object", "properties": {"face_handle": HANDLE, "adjacent_face_handle": HANDLE},
             "required": ["face_handle", "adjacent_face_handle"], "additionalProperties": False}
MODES = {
    "surface_edge_fillet": {"edge_handle": HANDLE, "propagation": {"enum": [0, 1]}, "radius_mm": POSITIVE},
    "surface_variable_fillet": {"edge_handle": HANDLE, "propagation": {"enum": [0, 1]},
                                "variation": {"enum": [0, 1]}, "radius_mm": POSITIVE},
    "surface_face_fillet": {"first_face_handle": HANDLE, "second_face_handle": HANDLE, "radius_mm": POSITIVE},
    "surface_tritangent_fillet": {"first_face_handle": HANDLE, "second_face_handle": HANDLE, "remove_face_handle": HANDLE},
    "surfacic_auto_fillet": {"radius_mm": POSITIVE, "confirm_all_edges": {"const": True}},
    "pad_reference": {"profile_handle": HANDLE, "length_mm": POSITIVE},
    "pocket_reference": {"profile_handle": HANDLE, "length_mm": POSITIVE},
    "shaft_reference": {"profile_handle": HANDLE, "axis_handle": HANDLE, "first_angle_deg": ANGLE, "second_angle_deg": ANGLE},
    "groove_reference": {"profile_handle": HANDLE, "axis_handle": HANDLE, "first_angle_deg": ANGLE, "second_angle_deg": ANGLE},
    "rib_reference": {"profile_handle": HANDLE, "spine_handle": HANDLE},
    "slot_reference": {"profile_handle": HANDLE, "spine_handle": HANDLE},
    "stiffener_reference": {"profile_handle": HANDLE, "thickness_mm": POSITIVE, "symmetric": BOOL, "from_top": BOOL},
    "hole_barycenter": {"support_face_handle": HANDLE, "depth_mm": POSITIVE, "diameter_mm": POSITIVE},
    "hole_one_edge": {"position_mm": VECTOR, "edge_handle": HANDLE, "support_face_handle": HANDLE, "depth_mm": POSITIVE, "diameter_mm": POSITIVE},
    "hole_two_edges": {"position_mm": VECTOR, "first_edge_handle": HANDLE, "second_edge_handle": HANDLE, "support_face_handle": HANDLE, "depth_mm": POSITIVE, "diameter_mm": POSITIVE},
    "auto_draft": {"angle_deg": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 90},
                   "direction_handle": HANDLE, "parting_handle": HANDLE, "functional_faces": array(HANDLE)},
    "rectangular_pattern": {"feature_handle": HANDLE, "first_direction_handle": HANDLE, "second_direction_handle": HANDLE,
        "first_count": COUNT, "second_count": COUNT, "first_spacing_mm": POSITIVE, "second_spacing_mm": POSITIVE,
        "first_seed_position": COUNT, "second_seed_position": COUNT,
        "first_forward": BOOL, "second_forward": BOOL, "rotation_deg": NUMBER},
    "circular_pattern": {"feature_handle": HANDLE, "center_handle": HANDLE, "axis_handle": HANDLE,
        "radial_count": COUNT, "angular_count": COUNT, "radial_spacing_mm": POSITIVE, "angular_spacing_deg": POSITIVE,
        "radial_seed_position": COUNT, "angular_seed_position": COUNT,
        "axis_forward": BOOL, "rotation_deg": NUMBER, "keep_parallel": BOOL},
    "trim_divided_faces": {"operand_body_handle": HANDLE, "keep": array(FACE_PAIR, 0), "remove": array(FACE_PAIR, 0)},
}
for _pattern in ("rectangular_pattern", "circular_pattern"):
    MODES[_pattern + "_list"] = {**MODES[_pattern], "additional_feature_handles": array(HANDLE),
                                  "allow_legacy_v5r8_api": {"const": True}}
    MODES["surfacic_" + _pattern] = dict(MODES[_pattern])
MODES["surfacic_circular_pattern"]["complete_crown"] = BOOL
MODES["surfacic_user_pattern"] = {
    "feature_handle": HANDLE, "positions_sketch_handle": HANDLE,
    "anchor_handle": HANDLE, "instances": COUNT,
}
MODES["user_pattern_list"] = {
    **MODES["surfacic_user_pattern"], "additional_feature_handles": array(HANDLE),
    "allow_legacy_v5r8_api": {"const": True},
}
for _fillet in ("edge_fillet", "variable_fillet", "face_fillet", "tritangent_fillet"):
    MODES["legacy_" + _fillet] = {
        **MODES["surface_" + _fillet], "allow_legacy_api": {"const": True},
    }
CONSTRUCTORS = {
    "surfacic_rectangular_pattern": "AddNewSurfacicRectPattern",
    "surfacic_circular_pattern": "AddNewSurfacicCircPattern",
    "surfacic_user_pattern": "AddNewSurfacicUserPattern",
    "user_pattern_list": "AddNewUserPatternofList",
    "legacy_edge_fillet": "AddNewEdgeFilletWithConstantRadius",
    "legacy_variable_fillet": "AddNewEdgeFilletWithVaryingRadius",
    "legacy_face_fillet": "AddNewFaceFillet",
    "legacy_tritangent_fillet": "AddNewTritangentFillet",
    "surface_edge_fillet": "AddNewSurfaceEdgeFilletWithConstantRadius",
    "surface_variable_fillet": "AddNewSurfaceEdgeFilletWithVaryingRadius",
    "surface_face_fillet": "AddNewSurfaceFaceFillet", "surface_tritangent_fillet": "AddNewSurfaceTritangentFillet",
    "surfacic_auto_fillet": "AddNewSurfacicAutoFillet",
    "rectangular_pattern_list": "AddNewRectPatternofList", "circular_pattern_list": "AddNewCircPatternofList",
    "pad_reference": "AddNewPadFromRef", "pocket_reference": "AddNewPocketFromRef",
    "shaft_reference": "AddNewShaftFromRef", "groove_reference": "AddNewGrooveFromRef",
    "rib_reference": "AddNewRibFromRef", "slot_reference": "AddNewSlotFromRef",
    "stiffener_reference": "AddNewStiffenerFromRef", "hole_barycenter": "AddNewHole",
    "hole_one_edge": "AddNewHoleWithConstraint", "hole_two_edges": "AddNewHoleWith2Constraints",
    "auto_draft": "AddNewAutoDraft", "rectangular_pattern": "AddNewRectPattern",
    "circular_pattern": "AddNewCircPattern", "trim_divided_faces": "AddNewTrim",
}


class ShapeFactoryTools(OperationTools):
    def get_tool_definitions(self):
        return [group("catia_part_design_advanced",
            "Explicit CAA advanced Part Design contracts; active Part and closed sketch required. "
            "Reference profiles are not automatic conversion of arbitrary edges into valid profiles. "
            "Hole barycenter uses the support barycenter; one circular edge overrides requested XYZ with concentricity. "
            "Pattern booleans use forward-natural-direction semantics, seed positions are 1-based; max 10000 total instances. "
            "Divided Trim faces require actual adjacent faces on the opposite operand. "
            "Auto Draft retains the native default mode: its Mode type is ambiguous in this CAA snapshot; reflective modes are not exposed. "
            "Surface fillet constructors are explicit native variants, not solid fillets. Variable surface fillet initially uses a default radius only. "
            "List patterns use legacy V5R8-only methods and require explicit opt-in; no fallback to ordinary patterns. "
            "Surfacic patterns target the explicit Body and accept whole surface/curve/sketch/feature seeds. "
            "complete_crown distributes circular copies at 360/count degrees, overriding angular_spacing_deg. "
            "User patterns use a positioning sketch and an anchor point. Legacy fillets are explicit API aliases, "
            "not new capabilities; prefer the explicit solid/surface variants. "
            "All modes are experimental until Windows validation. No automatic repair or rollback.",
            MODES, {"body_handle": HANDLE})]

    def execute(self, name, a):
        if name != "catia_part_design_advanced" or a["mode"] not in CONSTRUCTORS:
            raise CADOperationError("UNSUPPORTED_OPERATION", "Unknown advanced Part Design mode")
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition before Part Design operations")
        native_mode = a["mode"]
        m = native_mode.removesuffix("_list")
        surfacic = native_mode.startswith("surfacic_") and "pattern" in native_mode
        if surfacic:
            m = m.removeprefix("surfacic_")
        if m.startswith("legacy_"):
            m = "surface_" + m.removeprefix("legacy_")
        kinds = {"profile_handle": {"sketch"} | CURVE, "spine_handle": {"sketch"} | CURVE,
                 "axis_handle": LINE, "direction_handle": LINE,
                 "support_face_handle": {"face"}, "edge_handle": {"edge"},
                 "first_face_handle": {"face"}, "second_face_handle": {"face"}, "remove_face_handle": {"face"},
                 "first_edge_handle": {"edge"}, "second_edge_handle": {"edge"},
                 "parting_handle": {"plane", "surface", "face"},
                 "first_direction_handle": LINE | {"plane", "face"},
                 "second_direction_handle": LINE | {"plane", "face"}, "center_handle": {"point", "vertex"}}
        # Capture all exact references before any constructor changes topology.
        refs = {key: self.ref(a[key], kind) for key, kind in kinds.items() if key in a}
        faces = [self.ref(h, {"face"}) for h in a.get("functional_faces", [])]
        pairs = {key: [(self.ref(p["face_handle"], {"face"}), self.ref(p["adjacent_face_handle"], {"face"}))
                       for p in a.get(key, [])] for key in ("keep", "remove")}
        seed_kinds = {"feature", "surface", "curve", "line", "sketch"} if surfacic else {"feature"}
        feature = self.obj(a["feature_handle"], seed_kinds) if "feature_handle" in a else None
        positions = self.obj(a["positions_sketch_handle"], {"sketch"}) if "positions_sketch_handle" in a else None
        anchor = self.obj(a["anchor_handle"], {"point", "vertex", "point2d"}) if "anchor_handle" in a else None
        additional = [self.obj(h, {"feature"}) for h in a.get("additional_feature_handles", [])]
        body = self.obj(a["body_handle"], {"body"})
        seeds = ([feature] if feature is not None else []) + additional
        for n, seed in enumerate(seeds):
            if any(same_object(seed, prior) for prior in seeds[:n]):
                raise CADOperationError("INVALID_ARGUMENT", "Duplicate pattern seed")
            if not surfacic and not any(same_object(seed, body.Shapes.Item(i)) for i in range(1, body.Shapes.Count + 1)):
                raise CADOperationError("INVALID_ARGUMENT", "Pattern seed must belong to the explicitly targeted Body")
        operand = self.obj(a["operand_body_handle"], {"body"}) if "operand_body_handle" in a else None
        if operand is not None:
            if same_object(body, operand):
                raise CADOperationError("INVALID_ARGUMENT", "Trim needs two different bodies")
            if not pairs["keep"] and not pairs["remove"]:
                raise CADOperationError("INVALID_ARGUMENT", "Specify divided faces and their adjacent faces")
            for face, adjacent in pairs["keep"] + pairs["remove"]:
                if same_object(face, adjacent):
                    raise CADOperationError("INVALID_ARGUMENT", "Adjacent face must differ from the trimmed face")
            if any(same_object(k[0], r[0]) and same_object(k[1], r[1]) for k in pairs["keep"] for r in pairs["remove"]):
                raise CADOperationError("INVALID_ARGUMENT", "The same face pair cannot be kept and removed")
        if m in {"shaft_reference", "groove_reference"} and not 0 < a["first_angle_deg"] + a["second_angle_deg"] <= 360:
            raise CADOperationError("INVALID_ARGUMENT", "Total revolution must be in (0,360] degrees")
        if m == "hole_two_edges" and same_object(refs["first_edge_handle"], refs["second_edge_handle"]):
            raise CADOperationError("INVALID_ARGUMENT", "Hole requires two distinct edges")
        if m in {"rectangular_pattern", "circular_pattern"}:
            keys = ("first", "second") if m == "rectangular_pattern" else ("radial", "angular")
            if a[f"{keys[0]}_count"] * a[f"{keys[1]}_count"] > 10000:
                raise CADOperationError("INVALID_ARGUMENT", "Pattern exceeds 10000-instance safety limit")
            if any(a[f"{key}_seed_position"] > a[f"{key}_count"] for key in keys):
                raise CADOperationError("INVALID_ARGUMENT", "Pattern seed position exceeds instance count")
            if m == "circular_pattern" and not a.get("complete_crown", False) and a["angular_spacing_deg"] * (a["angular_count"] - 1) >= 360:
                raise CADOperationError("INVALID_ARGUMENT", "Angular pattern repeats or exceeds a complete revolution")
        part = self.conn.get_active_part()
        try:
            constructor = getattr(part.ShapeFactory, CONSTRUCTORS[native_mode])
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", f"{CONSTRUCTORS[native_mode]} unavailable: {exc}") from exc
        self.engineering.body(a["body_handle"])
        if m == "surface_edge_fillet":
            obj = constructor(refs["edge_handle"], a["propagation"], a["radius_mm"])
        elif m == "surface_variable_fillet":
            obj = constructor(refs["edge_handle"], a["propagation"], a["variation"], a["radius_mm"])
        elif m == "surface_face_fillet":
            obj = constructor(refs["first_face_handle"], refs["second_face_handle"], a["radius_mm"])
        elif m == "surface_tritangent_fillet":
            obj = constructor(refs["first_face_handle"], refs["second_face_handle"], refs["remove_face_handle"])
        elif m == "surfacic_auto_fillet":
            obj = constructor(a["radius_mm"])
        elif m in {"pad_reference", "pocket_reference"}:
            obj = constructor(refs["profile_handle"], a["length_mm"])
        elif m in {"shaft_reference", "groove_reference"}:
            obj = constructor(refs["profile_handle"])
            self.state.mark_created(obj, "feature")
            obj.RevoluteAxis = refs["axis_handle"]
            dimension(obj.FirstAngle, a["first_angle_deg"], "deg")
            dimension(obj.SecondAngle, a["second_angle_deg"], "deg")
        elif m in {"rib_reference", "slot_reference"}:
            obj = constructor(refs["profile_handle"], refs["spine_handle"])
        elif m == "stiffener_reference":
            obj = constructor(refs["profile_handle"])
            self.state.mark_created(obj, "feature")
            obj.IsSymmetric, obj.IsFromTop = a["symmetric"], a["from_top"]
            dimension(obj.Thickness, a["thickness_mm"], "mm")
        elif m.startswith("hole_"):
            prefix = [] if m == "hole_barycenter" else list(a["position_mm"])
            if m == "hole_one_edge":
                prefix.append(refs["edge_handle"])
            elif m == "hole_two_edges":
                prefix.extend([refs["first_edge_handle"], refs["second_edge_handle"]])
            obj = constructor(*prefix, refs["support_face_handle"], a["depth_mm"])
            self.state.mark_created(obj, "feature")
            obj.Type, obj.BottomType = 0, 0
            dimension(obj.Diameter, a["diameter_mm"], "mm")
        elif m == "auto_draft":
            obj = constructor(a["angle_deg"])
            self.state.mark_created(obj, "feature")
            obj.PullingDirection = refs["direction_handle"]
            obj.PartingElement = refs["parting_handle"]
            for face in faces:
                obj.FunctionalFace = face
        elif m == "rectangular_pattern":
            obj = constructor(feature, a["first_count"], a["second_count"], a["first_spacing_mm"], a["second_spacing_mm"],
                a["first_seed_position"], a["second_seed_position"], refs["first_direction_handle"], refs["second_direction_handle"],
                a["first_forward"], a["second_forward"], a["rotation_deg"])
        elif m == "circular_pattern":
            args = [feature, a["radial_count"], a["angular_count"], a["radial_spacing_mm"], a["angular_spacing_deg"],
                a["radial_seed_position"], a["angular_seed_position"], refs["center_handle"], refs["axis_handle"],
                a["axis_forward"], a["rotation_deg"], a["keep_parallel"]]
            if surfacic:
                args.append(a["complete_crown"])
            obj = constructor(*args)
        elif m == "user_pattern":
            obj = constructor(feature, a["instances"])
            self.state.mark_created(obj, "feature")
            obj.AnchorPoint = anchor
            obj.AddFeatureToLocatePositions(positions)
        else:
            obj = constructor(operand)
            self.state.mark_created(obj, "feature")
            for face, adjacent in pairs["keep"]:
                obj.AddFaceToKeep2(face, adjacent)
            for face, adjacent in pairs["remove"]:
                obj.AddFaceToRemove2(face, adjacent)
        if additional:
            self.state.mark_created(obj, "feature")
            for seed in additional:
                obj.ItemToCopy = seed
        result = self.finish(obj)
        result["constructor"] = CONSTRUCTORS[native_mode]
        if additional:
            result["warnings"].append("Legacy list-pattern membership and generated instances require Windows verification; ItemToCopy assignments alone do not prove all seeds were copied.")
        result["live_validated"] = False
        return result


NONNEGATIVE = {"type": "number", "minimum": 0}
VOLUME_MODES = {
    "close_surface": {"surface_handle": HANDLE},
    "thick_surface": {"surface_handle": HANDLE, "orientation": {"enum": [-1, 1]},
                      "top_mm": NONNEGATIVE, "bottom_mm": NONNEGATIVE},
    "add": {"support_volume_handle": HANDLE, "operand_volume_handle": HANDLE},
    "remove": {"support_volume_handle": HANDLE, "operand_volume_handle": HANDLE},
    "intersect": {"support_volume_handle": HANDLE, "operand_volume_handle": HANDLE},
    "trim": {"support_volume_handle": HANDLE, "operand_volume_handle": HANDLE},
    "sew": {"support_volume_handle": HANDLE, "surface_handle": HANDLE, "side": {"enum": [0, 1]}},
    "shell": {"support_volume_handle": HANDLE, "face_handle": HANDLE,
              "internal_mm": NONNEGATIVE, "external_mm": NONNEGATIVE},
    "thickness": {"support_volume_handle": HANDLE, "face_handle": HANDLE, "offset_mm": NUMBER},
    "draft": {"support_volume_handle": HANDLE, "face_handle": HANDLE, "neutral_handle": HANDLE,
              "parting_handle": HANDLE, "direction": VECTOR,
              "neutral_propagation": {"enum": [0, 1]}, "draft_mode": {"enum": [0, 1, 2]},
              "angle_deg": {"type": "number", "exclusiveMinimum": -90, "exclusiveMaximum": 90},
              "multiselection": {"enum": [0, 1]}},
}
VOLUME_CONSTRUCTORS = {
    "close_surface": "AddNewVolumeCloseSurface", "thick_surface": "AddNewVolumeThickSurface",
    "add": "AddNewVolumeAdd", "remove": "AddNewVolumeRemove", "intersect": "AddNewVolumeIntersect",
    "trim": "AddNewVolumeTrim", "sew": "AddNewVolumeSewSurface", "shell": "AddNewVolumeShell",
    "thickness": "AddNewVolumeThickness", "draft": "AddNewVolumicDraft",
}


class VolumeFactoryTools(OperationTools):
    def get_tool_definitions(self):
        return [group("catia_volume_operation",
            "CAA volumic ShapeFactory operations in an explicit GS/OGS, not ordinary PartBody booleans. "
            "Requires CATIA volume-capable license and supported container. Use volume handles returned by this tool; "
            "arbitrary surfaces/features are not assumed to be volumes. Type=4 (GSD volume) is fixed internally. "
            "Faces must belong to the intended support volume; CATIA must validate their geometry. "
            "Draft exposes native neutral propagation, multiselection and draft modes with explicit references. "
            "Experimental until live Windows validation; no fallback or rollback.",
            VOLUME_MODES, {"container_handle": HANDLE})]

    def execute(self, name, a):
        if name != "catia_volume_operation" or a["mode"] not in VOLUME_CONSTRUCTORS:
            raise CADOperationError("UNSUPPORTED_OPERATION", "Unknown volume operation")
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition first")
        mode = a["mode"]
        container = self.obj(a["container_handle"], {"geoset", "ordered_geoset"})
        kinds = {"support_volume_handle": {"volume"}, "operand_volume_handle": {"volume"},
                 "surface_handle": {"surface", "face"}, "face_handle": {"face"},
                 "neutral_handle": {"face", "plane"}, "parting_handle": {"face", "plane", "surface"}}
        refs = {key: self.ref(a[key], kind) for key, kind in kinds.items() if key in a}
        if "operand_volume_handle" in a and same_object(
                self.obj(a["support_volume_handle"], {"volume"}), self.obj(a["operand_volume_handle"], {"volume"})):
            raise CADOperationError("INVALID_ARGUMENT", "Volume operands must differ")
        if mode == "thick_surface" and a["top_mm"] + a["bottom_mm"] <= 0:
            raise CADOperationError("INVALID_ARGUMENT", "Total thickness must be positive")
        if mode == "shell" and a["internal_mm"] + a["external_mm"] <= 0:
            raise CADOperationError("INVALID_ARGUMENT", "Total shell thickness must be positive")
        if mode == "thickness" and a["offset_mm"] == 0:
            raise CADOperationError("INVALID_ARGUMENT", "Thickness offset must be nonzero")
        direction = unit_vector(a["direction"]) if mode == "draft" else None
        if mode == "draft" and a["angle_deg"] == 0:
            raise CADOperationError("INVALID_ARGUMENT", "Draft angle must be nonzero")
        part = self.conn.get_active_part()
        try:
            constructor = getattr(part.ShapeFactory, VOLUME_CONSTRUCTORS[mode])
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", f"{VOLUME_CONSTRUCTORS[mode]} unavailable: {exc}") from exc
        self.changed(a["container_handle"])
        part.InWorkObject = container
        if not same_object(part.InWorkObject, container):
            raise CADOperationError("POSTCONDITION_FAILED", "CATIA did not accept the target container")
        if mode == "close_surface":
            obj = constructor(refs["surface_handle"])
        elif mode == "thick_surface":
            obj = constructor(refs["surface_handle"], a["orientation"], a["top_mm"], a["bottom_mm"])
        elif mode in {"add", "remove", "intersect"}:
            obj = constructor(refs["support_volume_handle"], refs["operand_volume_handle"], 4)
        elif mode == "trim":
            obj = constructor(refs["support_volume_handle"], refs["operand_volume_handle"])
        elif mode == "sew":
            obj = constructor(4, refs["support_volume_handle"], refs["surface_handle"], a["side"])
        elif mode == "shell":
            obj = constructor(refs["face_handle"], a["internal_mm"], a["external_mm"], refs["support_volume_handle"])
        elif mode == "thickness":
            obj = constructor(refs["face_handle"], a["offset_mm"], 4, refs["support_volume_handle"])
        else:
            obj = constructor(refs["face_handle"], refs["neutral_handle"], a["neutral_propagation"],
                refs["parting_handle"], *direction, a["draft_mode"], a["angle_deg"], a["multiselection"],
                4, refs["support_volume_handle"])
        # ShapeFactory inserts in InWorkObject; never AppendHybridShape a PartDesign shape.
        result = self.finish(obj, "volume")
        result["constructor"] = VOLUME_CONSTRUCTORS[mode]
        result["live_validated"] = False
        return result
