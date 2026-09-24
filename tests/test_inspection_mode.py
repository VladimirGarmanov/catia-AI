"""Offline checks for the MCP inspection boundary and Codex role files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, ListToolsRequest

import catia_mcp.connection as connection_module
from catia_mcp.server import CATIAMCPServer, INSPECTION_TOOL_NAMES
from scripts.configure_codex_agents import ROLE_ACCESS, configure_agents, render_agent_config

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def test_inspection_server_only_lists_explicit_tools():
    full = CATIAMCPServer()
    inspection = CATIAMCPServer(inspection_only=True)
    assert len(full._tool_router) == 81
    assert set(inspection._tool_router) == INSPECTION_TOOL_NAMES
    assert inspection.connection.allow_launch is False

    listed = asyncio.run(inspection.server.request_handlers[ListToolsRequest](
        ListToolsRequest()))
    names = {tool.name for tool in listed.root.tools}
    assert names == INSPECTION_TOOL_NAMES
    assert "catia_new_part" not in names
    assert "catia_update_part" not in names
    assert "catia_save_document" not in names
    # These legacy measurement paths are not validated enough for acceptance.
    assert "catia_get_inertia" not in names
    assert "catia_get_bounding_box" not in names


def test_inspection_server_rejects_mutation_without_connecting():
    inspection = CATIAMCPServer(inspection_only=True)
    inspection.connection.connect = lambda: (_ for _ in ()).throw(
        AssertionError("Connection must not be attempted"))
    request = CallToolRequest(params=CallToolRequestParams(
        name="catia_new_part", arguments={}))
    response = asyncio.run(
        inspection.server.request_handlers[CallToolRequest](request))
    assert response.root.isError is True
    assert response.root.structuredContent["code"] == "INSPECTION_ONLY"


def test_inspection_connection_never_launches_catia(monkeypatch):
    calls = []

    def no_running_catia(_):
        calls.append("GetActiveObject")
        raise RuntimeError("not running")

    def forbidden_dispatch(_):
        calls.append("Dispatch")
        raise AssertionError("Inspection mode must not launch CATIA")

    monkeypatch.setattr(connection_module, "HAS_COM", True)
    monkeypatch.setattr(connection_module, "pythoncom", SimpleNamespace(
        CoInitialize=lambda: None), raising=False)
    monkeypatch.setattr(connection_module, "win32com", SimpleNamespace(
        client=SimpleNamespace(GetActiveObject=no_running_catia,
                               Dispatch=forbidden_dispatch)), raising=False)
    connection = connection_module.CATIAConnection(allow_launch=False)
    with pytest.raises(RuntimeError, match="will not launch CATIA"):
        connection.connect()
    assert calls == ["GetActiveObject"]


def test_portable_agents_load_without_incomplete_mcp_stubs():
    root = Path(__file__).resolve().parents[1]
    agent_dir = root / ".codex" / "agents"
    expected = {
        "cad_drawing_reader", "cad_model_inspector", "cad_planner",
        "cad_safety_reviewer", "cad_executor", "cad_verifier",
    }
    parsed = [tomllib.loads(path.read_text(encoding="utf-8"))
              for path in agent_dir.glob("*.toml")]
    assert {agent["name"] for agent in parsed} == expected
    for agent in parsed:
        assert agent["description"]
        assert agent["developer_instructions"]
        for server in agent.get("mcp_servers", {}).values():
            assert "command" in server or "url" in server

    project = tomllib.loads((root / ".codex" / "config.toml").read_text(
        encoding="utf-8"))
    assert project["agents"]["enabled"] is True


def test_windows_role_generation_is_complete_idempotent_and_preserves_main_config(tmp_path):
    root = Path(__file__).resolve().parents[1]
    agent_dir = tmp_path / ".codex" / "agents"
    agent_dir.mkdir(parents=True)
    config = tmp_path / ".codex" / "config.toml"
    original = b"[agents]\nenabled = true\n"
    config.write_bytes(original)
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.touch()
    for role in ROLE_ACCESS:
        source = (root / ".codex" / "agents" / f"{role}.toml").read_text(encoding="utf-8")
        (agent_dir / f"{role}.toml").write_text(source, encoding="utf-8")

    configure_agents(tmp_path, python_path)
    first = {path.name: path.read_bytes() for path in agent_dir.glob("*.toml")}
    configure_agents(tmp_path, python_path)
    assert first == {path.name: path.read_bytes() for path in agent_dir.glob("*.toml")}
    assert config.read_bytes() == original
    for role, (writer, inspector) in ROLE_ACCESS.items():
        agent = tomllib.loads((agent_dir / f"{role}.toml").read_text(encoding="utf-8"))
        servers = agent["mcp_servers"]
        assert servers["catia-v5"]["enabled"] is writer
        assert servers["catia-v5-inspect"]["enabled"] is inspector
        assert servers["catia-v5"]["command"] == str(python_path.resolve())
        assert servers["catia-v5-inspect"]["args"] == [
            "-m", "catia_mcp", "--inspection-only"]


def test_role_generator_preserves_manual_mcp_configuration():
    with pytest.raises(ValueError, match="refusing to overwrite"):
        render_agent_config(
            '[mcp_servers.custom]\ncommand = "custom"\n',
            "cad_verifier", Path("python.exe"),
        )
