"""CATIA Automation contract doubles; these tests do not run the CATIA solver."""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.sketcher import SketcherTools


@dataclass
class Reference:
    element: object


@pytest.fixture
def rig():
    elements = [SimpleNamespace(Name=name) for name in
                ("AbsoluteAxis", "Circle.1", "Line.1", "Line.2")]
    dimension = SimpleNamespace(Value=0.0)
    constraint = SimpleNamespace(Dimension=dimension)

    def mono(code, reference):
        assert isinstance(reference, Reference), "CATIA expects a Reference, not raw geometry"
        assert code in {0, 5, 10, 13, 14}, "Constraint requires two elements"
        if code == 14:
            assert reference.element is elements[1], "Radius requires the circle"
        return constraint

    def bi(code, first, second):
        assert isinstance(first, Reference) and isinstance(second, Reference)
        assert code in {1, 2, 4, 6, 8, 11}
        return constraint

    constraints = SimpleNamespace(AddMonoEltCst=Mock(side_effect=mono),
                                  AddBiEltCst=Mock(side_effect=bi))
    geometry = SimpleNamespace(Count=4, Item=Mock(side_effect=lambda i: elements[i - 1]))
    sketch = SimpleNamespace(Constraints=constraints, GeometricElements=geometry)
    part = SimpleNamespace(CreateReferenceFromObject=Mock(side_effect=Reference))
    connection = SimpleNamespace(get_active_part=Mock(return_value=part))
    tools = SketcherTools(connection)
    tools._active_sketch = sketch
    return SimpleNamespace(tools=tools, constraints=constraints, part=part,
                           sketch=sketch, elements=elements, constraint=constraint)


# Expected values come from CATIA CatConstraintType, not from production constants.
@pytest.mark.parametrize("kind,indices,value,code", [
    ("radius", [2], 25, 14),
    ("distance", [3], 40, 5),  # One line means Length, not Distance.
    ("distance", [3, 4], 10, 1),
    ("angle", [3, 4], 45, 6),
    ("coincidence", [3, 4], None, 2),
    ("tangent", [2, 3], None, 4),
    ("perpendicular", [3, 4], None, 11),
    ("parallel", [3, 4], None, 8),
    ("horizontal", [3], None, 10),
    ("vertical", [3], None, 13),
    ("fix", [2], None, 0),
])
def test_constraint_type_arity_and_reference_contract(rig, kind, indices, value, code):
    args = {"type": kind, "geometry_index_1": indices[0]}
    if len(indices) == 2:
        args["geometry_index_2"] = indices[1]
    if value is not None:
        args["value"] = value
    result = rig.tools.execute("catia_sketch_constraint", args)
    method = (rig.constraints.AddMonoEltCst if len(indices) == 1
              else rig.constraints.AddBiEltCst)
    method.assert_called_once_with(code, *(Reference(rig.elements[i - 1]) for i in indices))
    assert rig.part.CreateReferenceFromObject.call_count == len(indices)
    assert "constraint added" in result
    if value is not None:
        assert rig.constraint.Dimension.Value == value


@pytest.mark.parametrize("args", [
    {"type": "radius", "geometry_index_1": 2},
    {"type": "radius", "geometry_index_1": 2, "value": 0},
    {"type": "radius", "geometry_index_1": 2, "value": -25},
    {"type": "radius", "geometry_index_1": 2, "value": float("nan")},
    {"type": "radius", "geometry_index_1": 2, "value": float("inf")},
    {"type": "radius", "geometry_index_1": 2, "value": True},
    {"type": "radius", "geometry_index_1": 2, "value": "25"},
    {"type": "angle", "geometry_index_1": 3, "value": 45},
    {"type": "angle", "geometry_index_1": 3, "geometry_index_2": 4, "value": 361},
    {"type": "distance", "geometry_index_1": 3, "value": -1},
    {"type": "parallel", "geometry_index_1": 3},
    {"type": "fix", "geometry_index_1": 2, "geometry_index_2": 3},
    {"type": "fix", "geometry_index_1": 2, "value": 25},
    {"type": "unknown", "geometry_index_1": 2},
    {"type": "fix"},
    *({"type": "fix", "geometry_index_1": i} for i in (0, -1, 5, True, 2.5, "2")),
    {"type": "parallel", "geometry_index_1": 3, "geometry_index_2": 5},
    {"type": "parallel", "geometry_index_1": 3, "geometry_index_2": 3},
])
def test_invalid_arguments_do_not_create_constraints(rig, args):
    with pytest.raises(ValueError):
        rig.tools.execute("catia_sketch_constraint", args)
    rig.constraints.AddMonoEltCst.assert_not_called()
    rig.constraints.AddBiEltCst.assert_not_called()


def test_reference_error_preserves_cause_and_does_not_create_constraint(rig):
    rig.part.CreateReferenceFromObject.side_effect = RuntimeError("COM reference failed")
    with pytest.raises(RuntimeError, match="COM reference failed"):
        rig.tools.execute("catia_sketch_constraint",
                          {"type": "radius", "geometry_index_1": 2, "value": 25})
    rig.constraints.AddMonoEltCst.assert_not_called()


def test_dimension_failure_reports_partial_creation_without_retry(rig):
    class BrokenDimension:
        @property
        def Value(self):
            return 10

        @Value.setter
        def Value(self, value):
            raise RuntimeError("COM dimension rejected")

    rig.constraint.Dimension = BrokenDimension()
    with pytest.raises(RuntimeError, match="created.*COM dimension rejected"):
        rig.tools.execute("catia_sketch_constraint",
                          {"type": "radius", "geometry_index_1": 2, "value": 25})
    rig.constraints.AddMonoEltCst.assert_called_once()


def test_silently_ignored_dimension_is_not_reported_as_success(rig):
    class UnchangedDimension:
        @property
        def Value(self):
            return 10

        @Value.setter
        def Value(self, value):
            pass

    rig.constraint.Dimension = UnchangedDimension()
    with pytest.raises(RuntimeError, match="readback is 10.0, expected 25"):
        rig.tools.execute("catia_sketch_constraint",
                          {"type": "radius", "geometry_index_1": 2, "value": 25})
    rig.constraints.AddMonoEltCst.assert_called_once()


def test_missing_sketch_stops_before_com(rig):
    rig.tools._active_sketch = None
    with pytest.raises(RuntimeError, match="No active sketch"):
        rig.tools.execute("catia_sketch_constraint",
                          {"type": "radius", "geometry_index_1": 2, "value": 25})
    rig.constraints.AddMonoEltCst.assert_not_called()


def test_constraint_com_failure_is_mcp_error(rig):
    server = CATIAMCPServer()
    server.connection.app = SimpleNamespace(Caption="Mock CATIA")
    server.sketcher_tools.conn = rig.tools.conn
    server.sketcher_tools._active_sketch = rig.sketch
    rig.constraints.AddMonoEltCst.side_effect = RuntimeError("The method AddMonoEltCst failed")
    request = CallToolRequest(params=CallToolRequestParams(
        name="catia_sketch_constraint",
        arguments={"type": "radius", "geometry_index_1": 2, "value": 25}))
    response = asyncio.run(server.server.request_handlers[CallToolRequest](request))
    assert response.root.isError is True
    message = response.root.content[0].text
    assert "radius" in message and "14" in message
    assert "The method AddMonoEltCst failed" in message
    rig.constraints.AddMonoEltCst.assert_called_once()
