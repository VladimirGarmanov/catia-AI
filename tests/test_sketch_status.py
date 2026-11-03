"""Read-only constraint inspection; mocks do not run CATIA's native solver."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from catia_mcp.server import CATIAMCPServer


class Collection:
    def __init__(self, *items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


def constraint(status=0, inactive=False, mode=0, kind=14):
    return NS(Name="Radius.1", Type=kind, Status=status, Mode=mode,
              IsInactive=Mock(return_value=inactive), Dimension=NS(ValueAsString=lambda: "25mm"))


@pytest.fixture
def rig():
    server = CATIAMCPServer()
    sketch = NS(Name="Sketch.1", Constraints=Collection(), GeometricElements=Collection(NS(Name="Circle")),
                Evaluate=Mock(), OpenEdition=Mock(), CloseEdition=Mock())
    part = NS(Bodies=Collection(NS(Sketches=Collection(sketch))), HybridBodies=Collection(),
              IsUpToDate=Mock(return_value=True), Update=Mock())
    document = NS(Name="Part.CATPart", FullName="", Part=part)
    server.connection.app = NS(Caption="Mock CATIA", ActiveDocument=document)
    server.session.bind()
    handle = server.session.register(sketch, "sketch")
    yield NS(server=server, sketch=sketch, part=part, document=document, handle=handle)
    sketch.Evaluate.assert_not_called()
    sketch.OpenEdition.assert_not_called()
    sketch.CloseEdition.assert_not_called()
    part.Update.assert_not_called()
    assert server.session.revisions[server.session.document_id(document)] == 0
    server.worker.shutdown()


def inspect(rig, **args):
    return rig.server._execute_serial("catia_sketch_constraint_status", {"sketch_handle": rig.handle, **args})


def test_healthy_constraints_never_prove_full_constraint(rig):
    rig.sketch.Constraints = Collection(constraint(), constraint(mode=1))
    result = inspect(rig)
    assert result["ok"] and result["constraint_health"] == "satisfied"
    assert result["all_constraints_satisfied"] is True
    assert result["active_driving_count"] == result["active_reference_count"] == 1
    assert result["fully_constrained"] is result["remaining_dof"] is None
    assert result["status_freshness"] == "up_to_date"
    strict = inspect(rig, require_fully_constrained=True)
    assert not strict["ok"] and strict["code"] == "FULLY_CONSTRAINED_UNVERIFIED"
    assert not rig.server.session.reconciliation_required


def test_empty_and_inactive_sets_are_not_successful_constraint_evidence(rig):
    empty = inspect(rig)
    assert empty["constraint_health"] == "no_constraints"
    assert empty["all_constraints_satisfied"] is None
    rig.sketch.Constraints = Collection(constraint(status=5, inactive=True))
    inactive = inspect(rig)
    assert inactive["constraint_health"] == "no_active_constraints"
    assert inactive["all_constraints_satisfied"] is None and inactive["problem_indices"] == []
    assert inactive["inactive_count"] == 1


def test_failed_constraints_supply_exact_handles_and_error_without_overconstraint_guess(rig):
    rig.sketch.Constraints = Collection(constraint(status=3), constraint(status=5))
    result = inspect(rig, require_fully_constrained=True)
    assert not result["ok"] and result["code"] == "CONSTRAINTS_NOT_SATISFIED"
    assert result["problem_indices"] == [1, 2]
    assert len(result["problem_handles"]) == 2
    assert result["completeness"] == "unknown"
    assert result["all_constraints_satisfied"] is False
    assert all(not row["dimension_reliable"] for row in result["constraints"])


def test_partial_com_read_and_truncation_fail_closed(rig):
    unreadable = constraint()
    unreadable.IsInactive.side_effect = RuntimeError("COM refused IsInactive")
    rig.sketch.Constraints = Collection(constraint(), unreadable)
    result = inspect(rig)
    assert result["constraint_health"] == "unknown" and result["all_constraints_satisfied"] is None
    assert "inactive" in result["constraints"][1]["unavailable"]
    truncated = inspect(rig, max_constraints=1)
    assert truncated["constraint_count"] == 2 and truncated["inspected_count"] == 1
    assert truncated["truncated"] and truncated["all_constraints_satisfied"] is None
    rig.part.IsUpToDate.side_effect = RuntimeError("not exposed")
    assert inspect(rig)["up_to_date"] is None


def test_stale_calculation_and_wrong_target_are_explicit(rig):
    rig.part.IsUpToDate.return_value = False
    result = inspect(rig, require_fully_constrained=True)
    assert result["code"] == "UPDATE_REQUIRED"
    missing = rig.server._execute_serial("catia_sketch_constraint_status", {})
    assert missing["code"] == "NO_SKETCH_TARGET"
    wrong = rig.server.session.register(NS(Name="Not a sketch"), "feature")
    assert inspect(rig, sketch_handle=wrong)["code"] == "WRONG_GEOMETRY_TYPE"
    rig.part.Bodies = Collection()
    assert inspect(rig)["code"] == "STALE_REFERENCE"


def test_bound_open_sketch_and_mcp_error_flag(rig):
    editor = rig.server.sketcher_tools
    editor._active_sketch = rig.sketch
    editor._active_document = rig.document
    editor._active_document_identity = (rig.document.Name, "")
    result = rig.server._execute_serial("catia_sketch_constraint_status", {})
    assert result["ok"] and result["server_bound_open"]
    request = CallToolRequest(params=CallToolRequestParams(name="catia_sketch_constraint_status",
        arguments={"sketch_handle": rig.handle, "require_fully_constrained": True}))
    response = asyncio.run(rig.server.server.request_handlers[CallToolRequest](request)).root
    assert response.isError is True
    assert response.structuredContent["code"] == "FULLY_CONSTRAINED_UNVERIFIED"
    definition = next(d for d in rig.server.sketch_session_tools.get_tool_definitions() if d["name"] == "catia_sketch_constraint_status")
    assert definition["readOnlyHint"] is True
    assert "request_id" not in rig.server._schemas[definition["name"]]["required"]
