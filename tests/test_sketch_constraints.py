"""CAA contract doubles; these checks do not run the CATIA solver."""
from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest
from catia_mcp.tools.sketcher import SketcherTools


@pytest.fixture
def rig():
    point = lambda: NS(GeometricType=2)
    origin = point()
    line = NS(GeometricType=3, StartPoint=point(), EndPoint=point())
    elements = [line, NS(GeometricType=5), NS(GeometricType=8)]
    created = []
    def add(code, *refs):
        dimension = NS(ValuateFromString=Mock(), ValueAsString=lambda: "25mm")
        c = NS(Name="C", Status=0, Type=code, Mode=0, Dimension=dimension, IsInactive=lambda: False)
        created.append((code, refs, c))
        return c
    constraints = NS(AddMonoEltCst=Mock(side_effect=add), AddBiEltCst=Mock(side_effect=add),
                     AddTriEltCst=Mock(side_effect=add), Count=0)
    doc = NS(Name="Test.CATPart", FullName="")
    part = NS(CreateReferenceFromObject=lambda obj: obj)
    editor = SketcherTools(NS(active_document=doc, get_active_part=lambda: part))
    sketch = NS(Constraints=constraints, Evaluate=Mock(), AbsoluteAxis=NS(Origin=origin),
                GeometricElements=NS(Count=3, Item=lambda i: elements[i-1]))
    editor._active_sketch = sketch
    editor._active_document = doc
    editor._active_document_identity = (doc.Name, "")
    return NS(editor=editor, sketch=sketch, created=created, line=line, origin=origin)


@pytest.mark.parametrize("kind,index,value,code", [
    ("radius", 2, 25, 14), ("length", 1, 25, 5), ("horizontal", 1, None, 10),
    ("vertical", 1, None, 13), ("major_radius", 3, 25, 18), ("minor_radius", 3, 25, 19),
])
def test_documented_mono_types(rig, kind, index, value, code):
    args = {"type": kind, "geometry_index_1": index}
    if value is not None:
        args["value"] = value
    rig.editor._add_constraint(args)
    assert rig.created[0][0] == code
    if value is not None:
        rig.created[0][2].Dimension.ValuateFromString.assert_called_once_with("25mm")


def test_endpoint_to_origin_and_direction(rig):
    rig.editor._add_constraint({"type": "distance", "geometry_index_1": 1,
        "element_1": "start", "element_2": "origin", "distance_direction": "horizontal", "value": 25})
    code, refs, c = rig.created[0]
    assert code == 1 and refs[0] is rig.line.StartPoint and refs[1] is rig.origin
    assert c.DistanceDirection == 1


def test_same_line_distinct_endpoints_are_valid(rig):
    rig.editor._add_constraint({"type": "distance", "geometry_index_1": 1,
        "geometry_index_2": 1, "element_1": "start", "element_2": "end", "value": 25})
    assert rig.created[0][1] == (rig.line.StartPoint, rig.line.EndPoint)


@pytest.mark.parametrize("args", [
    {"type": "radius", "geometry_index_1": 1, "value": 25},
    {"type": "radius", "geometry_index_1": 2, "element_1": "start", "value": 25},
    {"type": "length", "geometry_index_1": 1, "value": -1},
    {"type": "length", "geometry_index_1": 1, "value": 25, "distance_direction": "horizontal"},
    {"type": "coincidence", "geometry_index_1": 1, "geometry_index_2": 1},
    {"type": "fix", "element_1": "origin", "geometry_index_1": 1},
    {"type": "midpoint", "geometry_index_1": 1, "geometry_index_2": 2},
])
def test_invalid_requests_do_not_mutate(rig, args):
    with pytest.raises(ValueError):
        rig.editor._add_constraint(args)
    assert not rig.created


def test_diagnosis_never_infers_zero_dof(rig):
    rig.editor._add_constraint({"type": "horizontal", "geometry_index_1": 1})
    c = rig.created[0][2]
    rig.sketch.Constraints.Count = 1
    rig.sketch.Constraints.Item = lambda i: c
    report = rig.editor._diagnose()
    assert report["all_constraints_satisfied"] is True
    assert report["remaining_dof"] is None and report["iso_constrained"] is None
    c.Status = 3
    assert rig.editor._diagnose()["constraints"][0]["diagnosis"] == "wrong_value"


def test_failed_solver_retains_created_constraint(rig):
    rig.sketch.Evaluate.side_effect = RuntimeError("solver failed")
    with pytest.raises(RuntimeError, match="solver failed"):
        rig.editor._add_constraint({"type": "radius", "geometry_index_1": 2, "value": 25})
    assert len(rig.created) == 1


@pytest.mark.parametrize("shape", ["circle", "rectangle"])
def test_origin_anchored_profiles_use_constraints_not_fix(rig, shape):
    factory = NS(CreatePoint=lambda x, y: NS(GeometricType=2),
                 CreateLine=lambda *args: NS(GeometricType=3),
                 CreateClosedCircle=lambda *args: NS(GeometricType=5))
    rig.editor._active_factory = factory
    if shape == "circle":
        rig.editor._draw_circle(0, 0, 25, True)
        assert [c[0] for c in rig.created] == [3, 14]
    else:
        rig.editor._draw_rectangle(0, 0, 25, 10, True)
        assert [c[0] for c in rig.created] == [10, 13, 10, 13, 5, 5, 2]
    assert not any(code == 0 for code, refs, c in rig.created)


def test_origin_anchor_refuses_displaced_profile_before_creation(rig):
    factory = Mock()
    rig.editor._active_factory = factory
    with pytest.raises(ValueError, match="first corner"):
        rig.editor._draw_rectangle(1, 0, 25, 10, True)
    with pytest.raises(ValueError, match="center"):
        rig.editor._draw_circle(1, 0, 25, True)
    assert not factory.mock_calls and not rig.created
