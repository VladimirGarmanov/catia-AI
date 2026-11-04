import asyncio
import json
from unittest.mock import Mock
from catia_mcp.tools.desktop import Window

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from catia_mcp.server import CATIAMCPServer
from catia_mcp.tool_gaps import ToolGapJournal
from catia_mcp.runtime import CADOperationError


def test_reports_persist_and_deduplicate_across_journal_instances(tmp_path):
    path = tmp_path / "missing_tools.jsonl"
    args = dict(tool_name="Sheet metal flange", reason="No native flange constructor", request_id="gap-1")
    first = ToolGapJournal(path).record(**args)
    assert first["ok"] and not first["replayed"]
    assert ToolGapJournal(path).record(**args)["replayed"]
    assert len(path.read_text().splitlines()) == 1
    assert json.loads(path.read_text())["tool_name"] == args["tool_name"]
    with pytest.raises(CADOperationError) as err:
        ToolGapJournal(path).record(**{**args, "tool_name": "Different operation"})
    assert err.value.code == "INVALID_ARGUMENT"


def test_report_tool_works_during_com_timeout_and_does_not_modify_session():
    server = CATIAMCPServer()
    server.connection.ensure_connected = Mock(side_effect=AssertionError("No COM"))
    server.session.reconciliation_required = True
    before = server.session.context()
    args = dict(tool_name="Associative trim", reason="Typed mode unavailable", request_id="report-1")
    async def run():
        server._timed_out = True
        server._inflight = asyncio.get_running_loop().create_future()
        result = await server.server.request_handlers[CallToolRequest](
            CallToolRequest(params=CallToolRequestParams(name="catia_report_missing_tool", arguments=args)))
        return result.root
    try:
        result = asyncio.run(run())
        assert result.isError is False and result.structuredContent["status"] == "recorded"
        assert server.session.context() == before
        server.connection.ensure_connected.assert_not_called()
    finally:
        server.worker.shutdown()


def test_ui_attempt_logs_capability_and_delivery_but_not_typed_text():
    server = CATIAMCPServer()
    backend = Mock()
    backend.window.return_value = Window(0, 0, "Desktop", (0, 0, 800, 600))
    server.desktop_tools.backend_factory = lambda: backend
    args = {"request_id": "ui-gap-1", "reason": "Need a native Drafting surface finish symbol",
            "missing_tool": "Drafting Surface Finish Symbol",
            "action": {"kind": "text", "text": "PRIVATE INPUT MUST NOT BE LOGGED"}}
    try:
        first = server._execute_serial("catia_ui_action", args)
        assert first["input_sent"] and first["tool_gap"]["ok"]
        assert server._execute_serial("catia_ui_action", args)["replayed"]
        text = server.capability_tools.journal.path.read_text()
        assert len(text.splitlines()) == 1 and "PRIVATE INPUT" not in text
        record = json.loads(text)
        assert record["tool_name"] == args["missing_tool"] and record["ui_executed"]
        assert record["outcome"] == "input_sent"
        backend.send.assert_called_once()
    finally:
        server.worker.shutdown()


def test_log_failure_does_not_mask_sent_input_or_repeat_it(tmp_path):
    server = CATIAMCPServer()
    backend = Mock()
    backend.window.return_value = Window(0, 0, "Desktop", (0, 0, 800, 600))
    server.desktop_tools.backend_factory = lambda: backend
    server.capability_tools.journal.path = tmp_path / "journal.jsonl"
    server.capability_tools.journal.path.write_text("broken JSON\n")
    try:
        result = server._execute_serial("catia_ui_action", {
            "request_id": "failure", "reason": "Missing operation", "missing_tool": "Example",
            "action": {"kind": "key", "key": "enter"}})
        assert result["ok"] and result["input_sent"]
        assert result["tool_gap"]["ok"] is False
        assert result["tool_gap"]["error"]["code"] == "TOOL_GAP_LOG_INVALID"
        assert server.capability_tools.journal.path.read_text() == "broken JSON\n"
        backend.send.assert_called_once()
    finally:
        server.worker.shutdown()
