"""Policy failures must be deterministic, non-mutating and not offer UI bypass."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from catia_mcp.constraint_policy import check_constraint_edit
from catia_mcp.fallback import fallback_advice
from catia_mcp.runtime import CADOperationError
from catia_mcp.server import CATIAMCPServer


@pytest.fixture
def server():
    server = CATIAMCPServer()
    server.connection.ensure_connected = Mock(side_effect=AssertionError("No COM permitted"))
    yield server
    server.worker.shutdown()


@pytest.mark.parametrize("name,args", [
    ("catia_sketch_constraint", {"type": "fix", "geometry_index_1": 1}),
    ("catia_sketch_constraint", {"type": "AutoConstraint"}),
    ("catia_sketch_constraint", {"type": "auto_constrain"}),
    ("catia_sketch_constraint", {"type": "catCstTypeReference"}),
    ("catia_sketch_constraint", {"type": 0}),
    ("catia_fix_constraint", {"component_name": "Base"}),
    ("catia_assembly_constraint", {"mode": "fix", "selection_handle": "s"}),
    ("catia_assembly_operation", {"mode": "fix_together", "product_handles": ["a", "b"]}),
    ("catia_dmu", {"mode": "mechanism", "fixed_product_handle": "base"}),
])
def test_forbidden_commands_fail_before_com_in_router_and_handler(server, name, args):
    result = server._execute_serial(name, args)
    assert result["ok"] is False and result["code"] == "OPERATION_DISABLED"
    assert not result["created_handles"] and not result["modified_handles"]
    assert result["status"] == "failed" and not server.session.mutation_started
    server.connection.ensure_connected.assert_not_called()
    with pytest.raises(CADOperationError) as error:
        server._tool_router[name].execute(name, args)
    assert error.value.code == "OPERATION_DISABLED"
    advice = fallback_advice(result)["ui_fallback"]
    assert advice["status"] == "input_disabled_by_policy"
    assert "catia_ui_action" not in advice["desktop_tools"]


def test_existing_fix_can_only_be_disabled_or_removed():
    fixed = NS(Type=0)
    for action in ("activate", "driving", "reference", "replace_element", "orientation", "rename", "dimension"):
        with pytest.raises(CADOperationError) as error:
            check_constraint_edit(fixed, action)
        assert error.value.code == "OPERATION_DISABLED"
    for action in ("deactivate", "remove"):
        check_constraint_edit(fixed, action)
    check_constraint_edit(NS(Type=14), "reference")  # A reference radius is not Fix.
    with pytest.raises(CADOperationError, match="Cannot read constraint Type"):
        check_constraint_edit(NS(), "activate")


def test_mcp_protocol_reports_disabled_operations_as_errors(server):
    for name, args in (
        ("catia_fix_constraint", {"component_name": "Base"}),
    ):
        request = CallToolRequest(params=CallToolRequestParams(name=name, arguments=args))
        response = asyncio.run(server.server.request_handlers[CallToolRequest](request)).root
        assert response.isError is True
        assert response.structuredContent["code"] == "OPERATION_DISABLED"
    server.connection.ensure_connected.assert_not_called()


def test_capability_discovery_does_not_route_to_disabled_operations(server):
    for capability in ("CATIA-044", "CATIA-142", "CATIA-147"):
        result = server._execute_serial("catia_capability_request", {"capability_id": capability})
        assert result["code"] == "OPERATION_DISABLED" and not result["executed"]
        row = server._execute_serial("catia_capability_status", {"capability_id": capability})["matches"][0]
        assert not row["implemented"] and not row["available_in_session"]
        assert row["implementation_coverage"] == "disabled_by_policy"
    assert "fix" not in server._schemas["catia_sketch_constraint"]["properties"]["type"]["enum"]
