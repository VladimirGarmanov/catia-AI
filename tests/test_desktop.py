from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.desktop import DesktopTools, Window


def setup():
    backend = Mock()
    backend.window.return_value = Window(0, 0, "Desktop", (-800, 0, 800, 600))
    backend.capture.return_value = (b"png", 1600, 600)
    state = NS(mutation_started=False)
    tool = DesktopTools(None, state, backend_factory=lambda: backend)
    return tool, backend


def test_snapshot_without_com_or_active_document():
    tool, backend = setup()
    result = tool.execute("catia_ui_snapshot", {})
    assert result["width"] == 1600
    assert result["screen_origin"] == [-800, 0]
    backend.approve.assert_not_called()


@pytest.mark.parametrize("action", [
    {"kind": "click", "x": 10, "y": 10}, {"kind": "key", "key": "enter"},
    {"kind": "text", "text": "Fix"}, {"kind": "numeric_text", "text": "0"},
    {"kind": "hotkey", "keys": ["ctrl", "a"]}, {"kind": "scroll", "steps": 1},
])
def test_all_ui_input_disabled_before_backend_access(action):
    tool, backend = setup()
    with pytest.raises(CADOperationError) as error:
        tool.execute("catia_ui_action", {"action": action})
    assert error.value.code == "OPERATION_DISABLED"
    backend.window.assert_not_called()
    backend.send.assert_not_called()


def test_server_desktop_route_rejects_input_without_com():
    from catia_mcp.server import CATIAMCPServer
    server = CATIAMCPServer()
    server.connection.ensure_connected = Mock(side_effect=AssertionError("COM should not be called"))
    backend = Mock()
    backend.window.return_value = Window(0, 0, "Desktop", (0, 0, 800, 600))
    server.desktop_tools.backend_factory = lambda: backend
    args = {"request_id": "ui1", "reason": "test", "action": {"kind": "hotkey", "keys": ["ctrl", "a"]}}
    first = server._execute_serial("catia_ui_action", args)
    second = server._execute_serial("catia_ui_action", args)
    assert not first["ok"] and not second["ok"]
    assert first["code"] == second["code"] == "OPERATION_DISABLED"
    assert first["input_may_have_been_sent"] is False
    backend.send.assert_not_called()
    server.connection.ensure_connected.assert_not_called()
    server.worker.shutdown()
