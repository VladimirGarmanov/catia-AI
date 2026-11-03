"""CAA call contracts only; mock objects cannot establish geometric validity."""
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from jsonschema import Draft202012Validator
from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.shape_factory import ShapeFactoryTools, CONSTRUCTORS, VolumeFactoryTools, VOLUME_CONSTRUCTORS


def fixture():
    def dim(value=1):
        parameter = NS(Value=value, ValueAsString=lambda: str(parameter.Value))
        parameter.ValuateFromString = Mock(side_effect=lambda text: setattr(parameter, "Value", float(text.removesuffix("mm").removesuffix("deg"))))
        return parameter
    feature = NS(Name="Result", FirstAngle=dim(), SecondAngle=dim(), Thickness=dim(), Diameter=dim(),
                 AddFaceToKeep2=Mock(), AddFaceToRemove2=Mock(), AddFeatureToLocatePositions=Mock())
    feature.AddFeatureToLocatePositions.side_effect = lambda sketch: setattr(feature, "FeatureToLocatePositions", sketch)
    factory = Mock()
    for method in CONSTRUCTORS.values():
        getattr(factory, method).return_value = feature
    def rectangular(seed, n1, n2, s1, s2, p1, p2, d1, d2, f1, f2, angle):
        feature.FirstDirectionRepartition = NS(InstancesCount=dim(n1), Spacing=dim(s1))
        feature.SecondDirectionRepartition = NS(InstancesCount=dim(n2), Spacing=dim(s2))
        feature.FirstDirectionRow, feature.SecondDirectionRow = dim(p1), dim(p2)
        feature.FirstOrientation, feature.SecondOrientation = f1, f2
        feature.RotationAngle = dim(angle)
        return feature
    def circular(seed, nr, na, sr, sa, pr, pa, center, axis, forward, angle, parallel, crown=False):
        feature.RadialRepartition = NS(InstancesCount=dim(nr), Spacing=dim(sr))
        feature.AngularRepartition = NS(InstancesCount=dim(na), AngularSpacing=dim(360 / na if crown else sa))
        feature.RadialDirectionRow, feature.AngularDirectionRow = dim(pr), dim(pa)
        feature.RotationOrientation, feature.RadialAlignment = forward, not parallel
        feature.RotationAngle = dim(angle)
        return feature
    for mode, method in CONSTRUCTORS.items():
        if "rectangular_pattern" in mode:
            getattr(factory, method).side_effect = rectangular
        elif "circular_pattern" in mode:
            getattr(factory, method).side_effect = circular
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


@pytest.mark.parametrize("mode", ["rectangular_pattern", "rectangular_pattern_list", "surfacic_rectangular_pattern",
                                  "circular_pattern", "circular_pattern_list", "surfacic_circular_pattern"])
def test_patterns_allow_zero_unused_spacing_and_read_actual_parameters(mode):
    tool, part, feature, cases = fixture()
    args = cases[mode]
    if "rectangular" in mode:
        args.update(second_count=1, second_spacing_mm=0)
    else:
        args.update(radial_spacing_mm=0, angular_spacing_deg=17, complete_crown=True)
        # CAA accepts a cylindrical face / plane as a circular-axis reference.
        args["axis_handle"] = tool.state.register(NS(Name="CylinderFace"), "face")
    Draft202012Validator(tool.get_tool_definitions()[0]["inputSchema"]).validate(args)
    result = tool.execute("catia_part_design_advanced", args)["pattern"]
    assert result["parameter_readback_verified"] and not result["geometry_verified"]
    if "circular" in mode:
        native = getattr(part.ShapeFactory, CONSTRUCTORS[mode]).call_args.args
        assert native[4] == 90  # complete crown overrides the input before COM
        assert native[8] is tool.obj(args["axis_handle"], {"face"})
        assert result["parameters"]["angular_spacing_deg"] == 90
    else:
        assert result["parameters"]["total_instances_including_source"] == 3


@pytest.mark.parametrize("changes", [dict(first_spacing_mm=0), dict(first_spacing_mm=float("nan")),
                                    dict(first_count=1, second_count=1), dict(first_seed_position=0)])
def test_invalid_pattern_rejected_before_changing_current_body(changes):
    tool, part, feature, cases = fixture()
    args = dict(cases["rectangular_pattern"], **changes)
    with pytest.raises(CADOperationError) as error:
        tool.execute("catia_part_design_advanced", args)
    assert error.value.code == "INVALID_ARGUMENT"
    assert not part.ShapeFactory.mock_calls and not hasattr(part, "InWorkObject")


@pytest.mark.parametrize("failure", ["wrong_count", "missing_readback", "update"])
def test_pattern_failure_retains_created_object_without_retry(failure):
    tool, part, feature, cases = fixture()
    def bad_update():
        if failure == "wrong_count":
            feature.FirstDirectionRepartition.InstancesCount.Value = 99
        elif failure == "missing_readback":
            del feature.FirstDirectionRow
        else:
            raise RuntimeError("CATIA update rejected")
    part.Update.side_effect = bad_update
    with pytest.raises(CADOperationError) as error:
        tool.execute("catia_part_design_advanced", cases["rectangular_pattern"])
    assert error.value.code == {"wrong_count": "POSTCONDITION_FAILED", "missing_readback": "POSTCONDITION_UNAVAILABLE", "update": "UPDATE_FAILED"}[failure]
    assert len(tool.state.created) == 1
    part.ShapeFactory.AddNewRectPattern.assert_called_once()


def legacy_fixture(circular=False):
    from catia_mcp.tools.part_design import PartDesignTools
    tool, part, feature, cases = fixture()
    tool.conn.session = tool.state
    tool.conn.ensure_connected = Mock()
    tool.conn.refresh_display = Mock()
    args = cases["circular_pattern" if circular else "rectangular_pattern"]
    tool.conn.get_active_part_body = lambda: tool.obj(args["body_handle"], {"body"})
    call = {"feature_handle": args["feature_handle"]}
    if circular:
        call.update(count=4, center_handle=args["center_handle"], axis_handle=args["axis_handle"], keep_parallel=False)
    else:
        call.update(dir1_count=3, dir1_spacing=10, first_direction_handle=args["first_direction_handle"],
                    second_direction_handle=args["second_direction_handle"], dir2_forward=False)
    return PartDesignTools(tool.conn), tool, part, feature, call


@pytest.mark.parametrize("circular", [False, True])
def test_legacy_patterns_use_exact_handles_and_return_readback(circular):
    legacy, tool, part, feature, args = legacy_fixture(circular)
    name = "catia_circ_pattern" if circular else "catia_rect_pattern"
    schema = next(d["inputSchema"] for d in legacy.get_tool_definitions() if d["name"] == name)
    Draft202012Validator(schema).validate(args)
    result = legacy.execute(name, args)
    assert result["pattern"]["parameters"]["total_instances_including_source"] == (4 if circular else 3)
    assert part.InWorkObject is tool.conn.get_active_part_body()
    if circular:
        assert part.ShapeFactory.AddNewCircPattern.call_args.args[-1] is False
        assert feature.CircularPatternParameters == 1


def test_legacy_selection_preserves_exact_face_edge_references_and_never_uses_parent():
    legacy, tool, part, feature, args = legacy_fixture(True)
    document = tool.conn.active_document
    center, axis = object(), object()
    class Selected:
        Document = document
        Type = "CylindricalFace"
        Value = property(lambda self: pytest.fail("must not resolve the parent feature"))
        Reference = axis
    selected_axis = Selected()
    selected_center = NS(Document=document, Type="Vertex", Reference=center)
    document.Selection = NS(Count2=2, Item2=lambda i: (selected_center, selected_axis)[i-1])
    del args["center_handle"], args["axis_handle"]
    legacy.execute("catia_circ_pattern", args)
    assert part.ShapeFactory.AddNewCircPattern.call_args.args[7:9] == (center, axis)
    selected_axis.Reference = None
    part.ShapeFactory.reset_mock()
    with pytest.raises(CADOperationError) as error:
        legacy.execute("catia_circ_pattern", args)
    assert error.value.code == "STALE_REFERENCE"
    assert not part.ShapeFactory.mock_calls


def test_circular_overlap_and_half_handle_pair_are_rejected():
    legacy, tool, part, feature, args = legacy_fixture(True)
    with pytest.raises(CADOperationError, match="span"):
        legacy.execute("catia_circ_pattern", dict(args, angular_spacing=120))
    del args["center_handle"]
    with pytest.raises(CADOperationError, match="both"):
        legacy.execute("catia_circ_pattern", args)
    assert not part.ShapeFactory.mock_calls


def test_solid_user_pattern_checks_body_and_exposes_count_limitation():
    from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools
    tool, part, feature, cases = fixture()
    advanced = AdvancedGeometryTools(tool.engineering)
    args = dict(cases["user_pattern_list"], mode="user_pattern")
    del args["additional_feature_handles"], args["allow_legacy_v5r8_api"]
    part.ShapeFactory.AddNewUserPattern.return_value = feature
    result = advanced.execute("catia_solid_operation", args)
    assert result["pattern"]["anchor_verified"] and result["pattern"]["positions_verified"]
    assert result["pattern"]["actual_instances"] is None
    part.ShapeFactory.reset_mock()
    body = tool.obj(args["body_handle"], {"body"})
    body.Shapes = NS(Count=0)
    with pytest.raises(CADOperationError, match="Body"):
        advanced.execute("catia_solid_operation", args)
    assert not part.ShapeFactory.mock_calls


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
