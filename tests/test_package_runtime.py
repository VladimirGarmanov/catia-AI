"""Small offline safety smoke set. These doubles do not validate CATIA COM."""
from types import SimpleNamespace
import json
import threading

from jsonschema import Draft202012Validator

from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.sketcher import SketcherTools


class FakeConnection:
    def __init__(self):
        self.active_document = SimpleNamespace(Name="Test.CATPart")
        self.operation_body = None
    def ensure_connected(self):
        pass


def server_with_fake_tools():
    server = CATIAMCPServer()
    server.connection = FakeConnection()
    server.session = SessionState(server.connection)
    server.connection.session = server.session
    server._tool_router["catia_get_model_state"] = SimpleNamespace(execute=lambda *_: {"ok": True})
    return server


def test_schemas_and_original_names():
    server = CATIAMCPServer()
    try:
        from importlib.resources import files
        original = json.loads(files("CATIA_AGENT_CODEX_PACKAGE").joinpath("CATIA_AGENT_EXISTING_TOOLS.json").read_text())
        assert {x["name"] for x in original["tools"]} <= set(server._tool_router)
        for schema in server._schemas.values():
            Draft202012Validator.check_schema(schema)
        result = server._execute_serial("catia_capability_status", {"capability_id": "CATIA-010"})
        assert result["matches"][0]["documented"] is False
        assert result["matches"][0]["implemented"] is False
    finally:
        server.worker.shutdown()


def test_worker_replay_and_wrong_document():
    server = server_with_fake_tools()
    calls = []
    server._tool_router["catia_pad"] = SimpleNamespace(execute=lambda *_: calls.append(threading.get_ident()) or "created")
    try:
        server.worker.submit(server._execute_serial, "catia_get_model_state", {}).result()
        args = {"height": 10, "request_id": "one"}
        first = server.worker.submit(server._execute_serial, "catia_pad", args).result()
        second = server.worker.submit(server._execute_serial, "catia_pad", args).result()
        assert first["ok"] and second["replayed"] and len(calls) == 1
        assert calls[0] != threading.get_ident()
        server.connection.active_document = SimpleNamespace(Name="Other.CATPart")
        result = server.worker.submit(server._execute_serial, "catia_pad", {"height": 10}).result()
        assert result["code"] == "DOCUMENT_MISMATCH" and len(calls) == 1
    finally:
        server.worker.shutdown()


def test_failed_write_requires_inspection_and_does_not_replay():
    server = server_with_fake_tools()
    calls = []
    def fail(*_):
        calls.append(1)
        raise RuntimeError("UpdateObject failed after constructor")
    server._tool_router["catia_pad"] = SimpleNamespace(execute=fail)
    try:
        server._execute_serial("catia_get_model_state", {})
        args = {"height": 5, "request_id": "failed"}
        assert server._execute_serial("catia_pad", args)["status"] == "partial_failure"
        assert server._execute_serial("catia_pad", args)["replayed"]
        assert server._execute_serial("catia_pad", {"height": 5})["code"] == "PARTIAL_MUTATION"
        assert len(calls) == 1
    finally:
        server.worker.shutdown()


def test_topology_invalidated_and_unknown_handle_rejected():
    connection = FakeConnection()
    state = SessionState(connection)
    key = state.bind()["document_id"]
    handle = state.register(object(), "face", reference=object(), topology=True, selection_index=1)
    state.finish_write(key)
    try:
        state.resolve(handle)
    except CADOperationError as exc:
        assert exc.code == "STALE_REFERENCE"
    else:
        raise AssertionError("stale topology resolved")


def test_axis_is_construction_and_center_line():
    connection = FakeConnection()
    sketcher = SketcherTools(connection)
    sketcher._active_sketch = SimpleNamespace()
    line = SimpleNamespace(GeometricType=3, Construction=False, Name="Line.1")
    sketcher._set_axis(line)
    assert line.Construction and sketcher._active_sketch.CenterLine is line


def test_invalid_arguments_do_not_call_backend():
    server = server_with_fake_tools()
    calls = []
    server._tool_router["catia_pad"] = SimpleNamespace(execute=lambda *_: calls.append(1))
    try:
        result = server._execute_serial("catia_pad", {"height": float("nan")})
        assert result["code"] == "INVALID_ARGUMENT" and not calls
        result = server._execute_serial("catia_pad", {"height": 10, "arbitrary_com_method": "Delete"})
        assert result["code"] == "INVALID_ARGUMENT" and not calls
    finally:
        server.worker.shutdown()
