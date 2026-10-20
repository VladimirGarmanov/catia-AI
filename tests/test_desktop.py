from types import SimpleNamespace as NS
from unittest.mock import Mock
import threading

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


def test_action_without_snapshot_or_confirmation():
    tool, backend = setup()
    result = tool.execute("catia_ui_action", {"action": {"kind": "text", "text": "Привет"}})
    assert result["input_sent"] and not result["geometry_verified"]
    backend.send.assert_called_once()
    backend.approve.assert_not_called()


def test_cancellation_prevents_input():
    tool, backend = setup()
    tool.cancel_event = threading.Event()
    tool.cancel_event.set()
    with pytest.raises(CADOperationError, match="cancelled"):
        tool.execute("catia_ui_action", {"action": {"kind": "key", "key": "enter"}})
    backend.send.assert_not_called()


def test_server_desktop_route_never_connects_and_deduplicates():
    from catia_mcp.server import CATIAMCPServer
    server = CATIAMCPServer()
    server.connection.ensure_connected = Mock(side_effect=AssertionError("COM should not be called"))
    backend = Mock()
    backend.window.return_value = Window(0, 0, "Desktop", (0, 0, 800, 600))
    server.desktop_tools.backend_factory = lambda: backend
    args = {"request_id": "ui1", "reason": "test", "action": {"kind": "hotkey", "keys": ["ctrl", "a"]}}
    first = server._execute_serial("catia_ui_action", args)
    second = server._execute_serial("catia_ui_action", args)
    assert first["ok"] and second["replayed"]
    backend.send.assert_called_once()
    server.connection.ensure_connected.assert_not_called()
