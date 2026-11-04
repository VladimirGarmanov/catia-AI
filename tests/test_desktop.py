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
    {"kind": "text", "text": "Bracket"}, {"kind": "numeric_text", "text": "0"},
    {"kind": "hotkey", "keys": ["ctrl", "a"]}, {"kind": "scroll", "steps": 1},
])
def test_ui_actions_reach_mock_backend_without_com_or_confirmation(action):
    tool, backend = setup()
    assert tool.execute("catia_ui_action", {"action": action})["input_sent"]
    backend.send.assert_called_once_with(backend.window.return_value, action)
    backend.approve.assert_not_called()


def test_server_desktop_route_deduplicates_input_without_com():
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
    server.worker.shutdown()


def test_offscreen_and_cancelled_input_never_sent():
    tool, backend = setup()
    with pytest.raises(CADOperationError, match="outside"):
        tool.execute("catia_ui_action", {"action": {"kind": "click", "x": 2000, "y": 10}})
    tool.cancel_event = NS(is_set=lambda: True)
    with pytest.raises(CADOperationError, match="cancelled"):
        tool.execute("catia_ui_action", {"action": {"kind": "key", "key": "enter"}})
    backend.send.assert_not_called()


@pytest.mark.parametrize("partial", [True, False])
def test_input_invalidates_context_and_is_not_replayed(partial):
    import threading
    from catia_mcp.server import CATIAMCPServer
    server = CATIAMCPServer()
    tool, backend = setup()
    server.desktop_tools.backend_factory = lambda: backend
    if partial:
        backend.send.side_effect = CADOperationError("UI_INPUT_PARTIAL", "Only some events delivered")
    args = {"request_id": "partial", "reason": "recovery", "action": {"kind": "key", "key": "enter"}}
    try:
        first = server._execute_with_timeout_marker("catia_ui_action", args, threading.Event())
        assert first["ok"] is not partial
        if partial:
            assert first["input_may_have_been_sent"]
            assert first["tool_gap"]["ui_executed"] is None
        else:
            assert first["tool_gap"]["ui_executed"] is True
        assert server.session.reconciliation_required
        assert server._execute_serial("catia_ui_action", args)["replayed"]
        backend.send.assert_called_once()
    finally:
        server.worker.shutdown()


def test_fallback_only_offers_ui_for_known_completed_nonpolicy_failures():
    from catia_mcp.fallback import fallback_advice
    for code in ("COM_TIMEOUT", "SESSION_STATE_UNKNOWN", "OPERATION_DISABLED"):
        advice = fallback_advice({"ok": False, "code": code})["ui_fallback"]
        assert "catia_ui_action" not in advice["desktop_tools"]
    advice = fallback_advice({"ok": False, "code": "POSITION_UNAVAILABLE"})["ui_fallback"]
    assert advice["status"] == "available_after_inspection"
    assert "catia_ui_action" in advice["desktop_tools"]
