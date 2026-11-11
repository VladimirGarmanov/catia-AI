"""Small contract checks for CAA Part Design calls; no Windows geometry assertions."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools


def fixture():
    dim = lambda: NS(ValuateFromString=Mock(), ValueAsString=lambda: "1mm")

    def length(value=1.0):
        parameter = NS(Value=value, ValueAsString=lambda: f"{parameter.Value}mm")
        parameter.ValuateFromString = Mock(side_effect=lambda text: setattr(
            parameter, "Value", float(text.removesuffix("mm").removesuffix("deg"))))
        return parameter
    feature = NS(Name="Result", Diameter=length(), Pitch=dim(), Depth=dim(),
                 Type=0, BottomType=0, BottomLimit=NS(LimitMode=0), Reverse=Mock(),
                 HeadDiameter=length(), HeadDepth=length(), HeadAngle=length(), BottomAngle=length(),
                 SetExplicitPolarity=Mock(), ReverseDirection=Mock(),
                 AddFaceToKeep=Mock(), AddFaceToRemove=Mock())
    factory = Mock()
    for name in ("AddNewAxisToAxis2", "AddNewSolidCombine", "AddNewSewSurface",
                 "AddNewRemoveFace", "AddNewReplaceFace", "AddNewThreadWithRef",
                 "AddNewAutoFillet", "AddNewTrim", "AddNewChamfer",
                 "AddNewHoleFromPoint", "AddNewHoleFromRefPoint"):
        getattr(factory, name).return_value = feature
    part = NS(ShapeFactory=factory, CreateReferenceFromObject=lambda x: x,
              UpdateObject=Mock(), Update=Mock(), IsUpToDate=lambda x: True)
    conn = NS(active_document=NS(Name="Test.CATPart"), get_active_part=lambda: part)
    state = SessionState(conn)
    engine = EngineeringTools(conn, state, NS(_active_sketch=None))
    tool = AdvancedGeometryTools(engine)
    def handle(kind):
        return state.register(NS(Name=kind), kind)
    return tool, part, feature, handle


@pytest.mark.parametrize("mode,method", [
    ("axis_to_axis", "AddNewAxisToAxis2"), ("solid_combine", "AddNewSolidCombine"),
    ("sew_surface", "AddNewSewSurface"), ("remove_faces", "AddNewRemoveFace"),
    ("replace_faces", "AddNewReplaceFace"), ("thread_tap", "AddNewThreadWithRef"),
    ("auto_fillet", "AddNewAutoFillet"), ("union_trim", "AddNewTrim"),
    ("chamfer_two_lengths", "AddNewChamfer"), ("hole_at_point", "AddNewHoleFromPoint"),
    ("hole_at_reference", "AddNewHoleFromRefPoint"),
])
def test_constructor_and_update_contract(mode, method):
    tool, part, feature, h = fixture()
    args = {
        "axis_to_axis": {"source_axis_handle": h("axis_system"), "target_axis_handle": h("axis_system")},
        "solid_combine": {"first_profile_handle": h("sketch"), "second_profile_handle": h("sketch"),
                          "first_direction_handle": h("line"), "second_direction_handle": h("line")},
        "sew_surface": {"surface_handle": h("surface"), "side": 0},
        "remove_faces": {"keep_face_handle": h("face"), "remove_face_handle": h("face")},
        "replace_faces": {"surface_handle": h("plane"), "remove_face_handle": h("face"), "side": 1},
        "thread_tap": {"lateral_face_handle": h("face"), "limit_face_handle": h("face"),
                       "diameter_mm": 10, "pitch_mm": 1, "depth_mm": 20,
                       "polarity": "tap", "hand": "left", "reverse": True},
        "auto_fillet": {"fillet_radius_mm": 2, "round_radius_mm": 3, "confirm_all_edges": True},
        "union_trim": {"operand_body_handle": h("body"), "keep_faces": [h("face")], "remove_faces": []},
        "chamfer_two_lengths": {"edge_handle": h("edge"), "first_length_mm": 2, "second_length_mm": 3, "propagation": 1, "reverse": True},
        "hole_at_point": {"position_mm": [1, 2, 3], "support_face_handle": h("face"), "depth_mm": 20, "diameter_mm": 10},
        "hole_at_reference": {"point_handle": h("point"), "support_face_handle": h("face"), "depth_mm": 20, "diameter_mm": 10},
    }[mode]
    result = tool.execute("catia_solid_operation", dict(args, mode=mode, body_handle=h("body")))
    assert result["ok"] and tool.state.created
    getattr(part.ShapeFactory, method).assert_called_once()
    part.UpdateObject.assert_called_once_with(feature)
    part.Update.assert_called_once_with()
    if mode == "thread_tap":
        feature.SetExplicitPolarity.assert_called_once_with(1)
        assert feature.Side == 1
        feature.Pitch.ValuateFromString.assert_called_once_with("1mm")
        feature.ReverseDirection.assert_called_once_with()
    if mode == "chamfer_two_lengths":
        assert part.ShapeFactory.AddNewChamfer.call_args.args[1:] == (1, 0, 1, 2, 3)
    if mode == "hole_at_point":
        assert part.ShapeFactory.AddNewHoleFromPoint.call_args.args[:3] == (1, 2, 3)


def test_union_trim_same_body_rejected_before_mutation():
    tool, part, feature, h = fixture()
    body = h("body")
    with pytest.raises(CADOperationError, match="distinct bodies"):
        tool.execute("catia_solid_operation", {"mode": "union_trim", "body_handle": body,
             "operand_body_handle": body, "keep_faces": [h("face")], "remove_faces": []})
    assert not part.ShapeFactory.mock_calls


def test_update_failure_retains_feature_evidence():
    tool, part, feature, h = fixture()
    part.Update.side_effect = RuntimeError("rebuild failed")
    with pytest.raises(CADOperationError, match="rebuild failed"):
        tool.execute("catia_solid_operation", {"mode": "auto_fillet", "body_handle": h("body"),
             "fillet_radius_mm": 2, "round_radius_mm": 3, "confirm_all_edges": True})
    assert tool.state.created and not tool.state.updated


def test_countersunk_through_reversed_hole_sets_native_modes():
    tool, part, feature, h = fixture()
    result = tool.execute("catia_solid_operation", {
        "mode": "hole_at_point", "body_handle": h("body"), "position_mm": [0, 0, 0],
        "support_face_handle": h("face"), "depth_mm": 20, "diameter_mm": 6.6,
        "hole_type": "countersunk", "head_diameter_mm": 12, "head_angle_deg": 90,
        "limit": "up_to_last", "reverse_direction": True})
    assert feature.Type == 3 and feature.CounterSunkMode == 2  # catCSModeAngleDiameter
    assert feature.BottomLimit.LimitMode == 2 and feature.BottomType == 0
    feature.HeadDiameter.ValuateFromString.assert_called_once_with("12mm")
    feature.HeadAngle.ValuateFromString.assert_called_once_with("90deg")
    feature.Reverse.assert_called_once_with()
    assert result["hole"]["limit_mode"] == 2 and result["hole"]["diameter"] == "6.6mm"


@pytest.mark.parametrize("options,message", [
    ({"hole_type": "countersunk", "head_diameter_mm": 12}, "exactly two"),
    ({"hole_type": "counterbored", "head_diameter_mm": 5, "head_depth_mm": 2}, "exceed the bore"),
    ({"hole_type": "counterbored", "head_diameter_mm": 12, "head_depth_mm": 25}, "less than the blind"),
    ({"bottom": "v", "limit": "up_to_last"}, "blind hole"),
    ({"bottom_angle_deg": 118}, "requires bottom=v"),
])
def test_invalid_hole_options_rejected_before_constructor(options, message):
    tool, part, feature, h = fixture()
    with pytest.raises(CADOperationError, match=message):
        tool.execute("catia_solid_operation", {
            "mode": "hole_at_point", "body_handle": h("body"), "position_mm": [0, 0, 0],
            "support_face_handle": h("face"), "depth_mm": 20, "diameter_mm": 6.6, **options})
    part.ShapeFactory.AddNewHoleFromPoint.assert_not_called()


def test_measure_exact_keeps_spa_lengths_in_mm_and_scales_area():
    from catia_mcp.tools.analysis_tools import AnalysisTools
    tool, part, feature, h = fixture()
    measurable = NS(GeometryName=10, Length=25.0, GetMinimumDistance=lambda other: 20.0)
    surface = NS(GeometryName=7, Area=0.0004, Perimeter=80.0)
    queue = [measurable, measurable, surface, surface]
    tool.conn.active_document.GetWorkbench = lambda name: NS(GetMeasurable=lambda ref: queue.pop(0))
    analysis = AnalysisTools(tool.engineering)
    line, other = h("line"), h("line")
    assert analysis.measure({"mode": "scalar", "property": "length", "handle": line})["value"] == 25.0
    distance = analysis.measure({"mode": "distance", "first_handle": line, "second_handle": other})
    assert distance["value"] == 20.0 and distance["unit"] == "mm"
    area = analysis.measure({"mode": "scalar", "property": "area", "handle": h("plane")})
    assert area["value"] == pytest.approx(400.0) and area["unit"] == "mm2"
    assert analysis.measure({"mode": "scalar", "property": "perimeter", "handle": h("plane")})["value"] == 80.0
    with pytest.raises(CADOperationError, match="Expected"):
        analysis.measure({"mode": "distance", "first_handle": h("body"), "second_handle": other})
