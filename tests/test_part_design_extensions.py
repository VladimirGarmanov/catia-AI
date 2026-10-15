"""Small contract checks for CAA Part Design calls; no Windows geometry assertions."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools


def fixture():
    dim = lambda: NS(ValuateFromString=Mock(), ValueAsString=lambda: "1mm")
    feature = NS(Name="Result", Diameter=dim(), Pitch=dim(), Depth=dim(),
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
