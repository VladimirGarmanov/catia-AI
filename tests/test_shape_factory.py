"""CAA call contracts only; mock objects cannot establish geometric validity."""
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from jsonschema import Draft202012Validator
from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.shape_factory import ShapeFactoryTools, CONSTRUCTORS, VolumeFactoryTools, VOLUME_CONSTRUCTORS


def fixture():
    dim = lambda: NS(ValuateFromString=Mock(), ValueAsString=lambda: "1mm")
    feature = NS(Name="Result", FirstAngle=dim(), SecondAngle=dim(), Thickness=dim(), Diameter=dim(),
                 AddFaceToKeep2=Mock(), AddFaceToRemove2=Mock(), AddFeatureToLocatePositions=Mock())
    factory = Mock()
    for method in CONSTRUCTORS.values():
        getattr(factory, method).return_value = feature
    part = NS(ShapeFactory=factory, CreateReferenceFromObject=lambda x: x,
              UpdateObject=Mock(), Update=Mock(), IsUpToDate=lambda x: True)
    conn = NS(active_document=NS(Name="Test.CATPart"), get_active_part=lambda: part)
    state = SessionState(conn)
    tool = ShapeFactoryTools(EngineeringTools(conn, state, NS(_active_sketch=None)))
    def h(kind):
        return state.register(NS(Name=kind), kind)
    common = {"body_handle": h("body")}
    cases = {
        "pad_reference": {"profile_handle": h("sketch"), "length_mm": 10},
        "pocket_reference": {"profile_handle": h("sketch"), "length_mm": 10},
        "shaft_reference": {"profile_handle": h("sketch"), "axis_handle": h("line"), "first_angle_deg": 270, "second_angle_deg": 90},
        "groove_reference": {"profile_handle": h("sketch"), "axis_handle": h("line"), "first_angle_deg": 90, "second_angle_deg": 0},
        "rib_reference": {"profile_handle": h("sketch"), "spine_handle": h("curve")},
        "slot_reference": {"profile_handle": h("sketch"), "spine_handle": h("curve")},
        "stiffener_reference": {"profile_handle": h("sketch"), "thickness_mm": 3, "symmetric": True, "from_top": False},
        "hole_barycenter": {"support_face_handle": h("face"), "depth_mm": 10, "diameter_mm": 4},
        "hole_one_edge": {"position_mm": [1, 2, 3], "edge_handle": h("edge"), "support_face_handle": h("face"), "depth_mm": 10, "diameter_mm": 4},
        "hole_two_edges": {"position_mm": [1, 2, 3], "first_edge_handle": h("edge"), "second_edge_handle": h("edge"), "support_face_handle": h("face"), "depth_mm": 10, "diameter_mm": 4},
        "auto_draft": {"angle_deg": 5, "direction_handle": h("line"), "parting_handle": h("plane"), "functional_faces": [h("face")]},
        "rectangular_pattern": {"feature_handle": h("feature"), "first_direction_handle": h("line"), "second_direction_handle": h("line"),
            "first_count": 3, "second_count": 2, "first_spacing_mm": 10, "second_spacing_mm": 20,
            "first_seed_position": 1, "second_seed_position": 1, "first_forward": True, "second_forward": False, "rotation_deg": 0},
        "circular_pattern": {"feature_handle": h("feature"), "center_handle": h("point"), "axis_handle": h("line"),
            "radial_count": 1, "angular_count": 4, "radial_spacing_mm": 10, "angular_spacing_deg": 90,
            "radial_seed_position": 1, "angular_seed_position": 1, "axis_forward": True, "rotation_deg": 0, "keep_parallel": False},
        "trim_divided_faces": {"operand_body_handle": h("body"), "keep": [{"face_handle": h("face"), "adjacent_face_handle": h("face")}], "remove": []},
    }
    cases.update({
        "surface_edge_fillet": {"edge_handle": h("edge"), "propagation": 1, "radius_mm": 2},
        "surface_variable_fillet": {"edge_handle": h("edge"), "propagation": 1, "variation": 0, "radius_mm": 2},
        "surface_face_fillet": {"first_face_handle": h("face"), "second_face_handle": h("face"), "radius_mm": 2},
        "surface_tritangent_fillet": {"first_face_handle": h("face"), "second_face_handle": h("face"), "remove_face_handle": h("face")},
        "surfacic_auto_fillet": {"radius_mm": 2, "confirm_all_edges": True},
    })
    for pattern in ("rectangular_pattern", "circular_pattern"):
        cases[pattern + "_list"] = dict(cases[pattern], additional_feature_handles=[h("feature")], allow_legacy_v5r8_api=True)
        cases["surfacic_" + pattern] = dict(cases[pattern], feature_handle=h("surface"))
    cases["surfacic_circular_pattern"]["complete_crown"] = True
    cases["surfacic_user_pattern"] = {"feature_handle": h("surface"), "positions_sketch_handle": h("sketch"),
                                        "anchor_handle": h("point"), "instances": 3}
    cases["user_pattern_list"] = dict(cases["surfacic_user_pattern"], feature_handle=h("feature"),
                                      additional_feature_handles=[h("feature")], allow_legacy_v5r8_api=True)
    for fillet in ("edge_fillet", "variable_fillet", "face_fillet", "tritangent_fillet"):
        cases["legacy_" + fillet] = dict(cases["surface_" + fillet], allow_legacy_api=True)
    seeds = [r.value for r in state.objects.values() if r.kind == "feature"]
    for record in state.objects.values():
        if record.kind == "body":
            record.value.Shapes = NS(Count=len(seeds), Item=lambda i: seeds[i-1])
    return tool, part, feature, {m: dict(a, mode=m, **common) for m, a in cases.items()}


@pytest.mark.parametrize("mode", list(CONSTRUCTORS))
def test_modes_validate_and_call_native_constructor(mode):
    tool, part, feature, cases = fixture()
    schema = tool.get_tool_definitions()[0]["inputSchema"]
    Draft202012Validator(schema).validate(cases[mode])
    result = tool.execute("catia_part_design_advanced", cases[mode])
    assert result["ok"] and result["live_validated"] is False
    getattr(part.ShapeFactory, CONSTRUCTORS[mode]).assert_called_once()
    part.UpdateObject.assert_called_once_with(feature)
    part.Update.assert_called_once_with()
    if mode == "rectangular_pattern":
        args = part.ShapeFactory.AddNewRectPattern.call_args.args
        assert args[1:7] == (3, 2, 10, 20, 1, 1)
        assert args[9:] == (True, False, 0)
    if mode == "shaft_reference":
        feature.FirstAngle.ValuateFromString.assert_called_once_with("270deg")
    if mode == "trim_divided_faces":
        feature.AddFaceToKeep2.assert_called_once()


def test_preflight_rejects_invalid_pattern_without_mutation():
    tool, part, feature, cases = fixture()
    args = cases["rectangular_pattern"]
    args["first_seed_position"] = 4
    with pytest.raises(CADOperationError, match="seed"):
        tool.execute("catia_part_design_advanced", args)
    assert not part.ShapeFactory.mock_calls and not tool.state.created


def test_partial_property_failure_keeps_created_evidence():
    tool, part, feature, cases = fixture()
    feature.FirstAngle.ValuateFromString.side_effect = RuntimeError("angle rejected")
    with pytest.raises(RuntimeError, match="angle rejected"):
        tool.execute("catia_part_design_advanced", cases["shaft_reference"])
    assert len(tool.state.created) == 1
    part.Update.assert_not_called()


@pytest.mark.parametrize("mode", list(VOLUME_CONSTRUCTORS))
def test_volume_contracts_and_explicit_container(mode):
    base, part, feature, _ = fixture()
    tool = VolumeFactoryTools(base.engineering)
    def h(kind):
        return tool.state.register(NS(Name=kind), kind)
    constructor = getattr(part.ShapeFactory, VOLUME_CONSTRUCTORS[mode])
    constructor.return_value = feature
    support, operand, surface, face = h("volume"), h("volume"), h("surface"), h("face")
    cases = {
        "close_surface": {"surface_handle": surface},
        "thick_surface": {"surface_handle": surface, "orientation": 1, "top_mm": 5, "bottom_mm": 0},
        **{key: {"support_volume_handle": support, "operand_volume_handle": operand}
           for key in ("add", "remove", "intersect", "trim")},
        "sew": {"support_volume_handle": support, "surface_handle": surface, "side": 0},
        "shell": {"support_volume_handle": support, "face_handle": face, "internal_mm": 1, "external_mm": 0},
        "thickness": {"support_volume_handle": support, "face_handle": face, "offset_mm": 2},
        "draft": {"support_volume_handle": support, "face_handle": face, "neutral_handle": h("plane"),
                  "parting_handle": h("plane"), "direction": [0, 0, 2], "neutral_propagation": 0,
                  "draft_mode": 0, "angle_deg": 5, "multiselection": 0},
    }
    container = h("geoset")
    args = dict(cases[mode], mode=mode, container_handle=container)
    Draft202012Validator(tool.get_tool_definitions()[0]["inputSchema"]).validate(args)
    result = tool.execute("catia_volume_operation", args)
    assert result["ok"] and tool.state.resolve(result["handle"]).kind == "volume"
    assert part.InWorkObject is tool.state.resolve(container).value
    constructor.assert_called_once()
    part.Update.assert_called_once()
    if mode in {"add", "remove", "intersect"}:
        assert constructor.call_args.args[-1] == 4
    if mode == "draft":
        assert constructor.call_args.args[4:7] == (0, 0, 1)
        assert constructor.call_args.args[-2] == 4


def test_reference_parser_preserves_literal_types_without_running_scripts():
    from scripts.sync_v5_reference import Page
    page = Page()
    page.feed("<p>arg</p><script>activateLink('Reference','Reference'); arbitraryCall();</script><style>hidden</style>")
    assert page.text == ["arg", "Reference"]
