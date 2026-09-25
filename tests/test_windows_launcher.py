"""No downloads, real Codex configuration, or CATIA operations in these tests."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import windows_launcher as launcher
from scripts.check_mcp_transport import probe_transports
from scripts.configure_codex_agents import ROLE_ACCESS, configure_agents, render_agent_config

ROOT = Path(__file__).resolve().parents[1]


def prepared_project(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    for role in ROLE_ACCESS:
        shutil.copyfile(ROOT / ".codex" / "agents" / f"{role}.toml", agents / f"{role}.toml")
    (tmp_path / ".codex" / "config.toml").write_bytes(b"# user settings\n[agents]\nenabled=true\n")
    return python


def test_role_validation_and_backup_preserve_root_config(tmp_path):
    python = prepared_project(tmp_path)
    source = (tmp_path / ".codex" / "agents" / "cad_executor.toml").read_bytes()
    config = (tmp_path / ".codex" / "config.toml").read_bytes()
    configure_agents(tmp_path, python)
    assert set(launcher.validate_roles(tmp_path, python)) == set(ROLE_ACCESS)
    backup = tmp_path / ".local" / "role-backups" / "cad_executor.toml"
    assert backup.read_bytes() == source
    configure_agents(tmp_path, python)
    assert backup.read_bytes() == source
    assert (tmp_path / ".codex" / "config.toml").read_bytes() == config


def test_all_roles_validated_before_any_write(tmp_path):
    python = prepared_project(tmp_path)
    directory = tmp_path / ".codex" / "agents"
    (directory / "cad_verifier.toml").write_text('name = "broken', encoding="utf-8")
    before = {p.name: p.read_bytes() for p in directory.glob("*.toml")}
    with pytest.raises(ValueError):
        configure_agents(tmp_path, python)
    assert before == {p.name: p.read_bytes() for p in directory.glob("*.toml")}
    assert not (tmp_path / ".local").exists()


def test_transport_is_required_only_for_enabled_roles():
    from scripts.configure_codex_agents import tomllib
    for role, flags in ROLE_ACCESS.items():
        source = (ROOT / ".codex" / "agents" / f"{role}.toml").read_text()
        result = tomllib.loads(render_agent_config(source, role, Path("C:/my project/python.exe")))
        servers = result["mcp_servers"]
        assert servers["catia-v5"]["required"] is flags[0]
        assert servers["catia-v5-inspect"]["required"] is flags[1]


def test_diagnostic_rejects_inspection_only_executor(tmp_path):
    python = prepared_project(tmp_path)
    configure_agents(tmp_path, python)
    executor = tmp_path / ".codex" / "agents" / "cad_executor.toml"
    executor.write_text(executor.read_text().replace("enabled = true", "enabled = false"))
    with pytest.raises(launcher.SetupError, match="cad_executor.toml"):
        launcher.validate_roles(tmp_path, python)


def test_discovers_double_extracted_node_without_modifying_path(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda _: None)
    node = tmp_path / "Downloads" / "node-v24.21.0-win-x64" / "node-v24.21.0-win-x64" / "node.exe"
    node.parent.mkdir(parents=True)
    node.touch()
    old_path = os.environ.get("PATH")
    assert launcher.discover_node(tmp_path / "project", {}, tmp_path) == node.resolve()
    env = launcher.child_environment(node, None)
    assert str(node.parent) in env["PATH"]
    assert os.environ.get("PATH") == old_path


def test_reuses_previous_user_local_codex(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda _: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    codex = tmp_path / "codex-cli" / "codex.cmd"
    codex.parent.mkdir()
    codex.touch()
    assert launcher.discover_codex(tmp_path / "project", {}) == codex.resolve()


def test_windows_batch_quoting_spaces_and_no_powershell():
    args = [r"C:\Users\Some User\codex.cmd", "mcp", "add", "catia-v5-inspect", "--",
            r"C:\CAD Projects\Деталь\.venv\Scripts\python.exe", "-m", "catia_mcp"]
    command = launcher.windows_command(args, "cmd.exe")
    assert command == 'cmd.exe /d /s /c "' + " ".join(f'"{arg}"' for arg in args) + '"'
    assert launcher.windows_command(["python.exe", "--version"], "cmd.exe") == [
        "python.exe", "--version"]
    with pytest.raises(launcher.SetupError, match="PowerShell"):
        launcher.windows_command(["codex.ps1"], "cmd.exe")


@pytest.mark.parametrize("path", ["bad&path", "%PATH%", "bad!path", "bad^path", "bad\npath"])
def test_cmd_rejects_shell_expansion(path):
    with pytest.raises(launcher.SetupError, match="shell-active"):
        launcher.windows_command(["codex.cmd", path], "cmd.exe")


@pytest.mark.skipif(os.name != "nt", reason="Actual cmd.exe quoting needs Windows")
def test_real_cmd_execution_with_spaces(tmp_path):
    folder = tmp_path / "folder with spaces"
    folder.mkdir()
    command = folder / "test.cmd"
    command.write_bytes(b"@echo off\r\necho [%~1]\r\necho [%~2]\r\n")
    result = subprocess.run(launcher.windows_command(
        [str(command), "argument with spaces", "plain"], os.environ["COMSPEC"]),
        capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["[argument with spaces]", "[plain]"]


def entry(python, *, enabled=True, writer=False):
    return {"name": "catia-v5-inspect", "enabled": enabled,
            "transport": {"type": "stdio", "command": str(python),
                          "args": ["-m", "catia_mcp"] + ([] if writer else ["--inspection-only"])}}


def test_existing_disabled_or_foreign_entry_is_not_silently_changed(tmp_path):
    python = tmp_path / "python.exe"
    launcher.check_entry(entry(python), python)
    with pytest.raises(launcher.SetupError, match="disabled"):
        launcher.check_entry(entry(python, enabled=False), python)
    with pytest.raises(launcher.SetupError, match="elsewhere"):
        launcher.check_entry(entry(tmp_path / "other.exe"), python)
    nested = {"config": {"enabled": False, "transport": entry(python)["transport"]}}
    assert launcher.normalize_entry(nested)["enabled"] is False


class FakeRunner:
    def __init__(self, root, entries):
        self.root = root
        self.entries = entries
        self.calls = []

    def run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if "add" in args:
            self.entries["catia-v5-inspect"] = entry(args[5])
        return SimpleNamespace(stdout=json.dumps(list(self.entries.values())), returncode=0)


def test_registration_is_idempotent_and_never_adds_writer(tmp_path):
    python = tmp_path / "python.exe"
    codex = tmp_path / "codex.cmd"
    runner = FakeRunner(tmp_path, {})
    launcher.configure_mcp(runner, codex, python)
    launcher.configure_mcp(runner, codex, python)
    additions = [args for args, _ in runner.calls if "add" in args]
    assert additions == [[str(codex), "mcp", "add", "catia-v5-inspect", "--", str(python),
                          "-m", "catia_mcp", "--inspection-only"]]
    assert not any("remove" in args for args, _ in runner.calls)
    assert all(kwargs.get("private") for args, kwargs in runner.calls if "--json" in args)


def test_conflict_stops_before_role_mutation_or_registration(tmp_path):
    python = tmp_path / "python.exe"
    runner = FakeRunner(tmp_path, {"catia-v5-inspect": entry(tmp_path / "other.exe")})
    with pytest.raises(launcher.SetupError):
        launcher.configure_mcp(runner, tmp_path / "codex.cmd", python)
    assert len(runner.calls) == 1
    with pytest.raises(launcher.SetupError, match="global full-access"):
        launcher.preflight_entries({"catia-v5": entry(python, writer=True)}, python)


def test_launcher_refuses_non_windows_before_writing(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert launcher.main(["install"]) == 1
    assert list(tmp_path.iterdir()) == []


def test_private_mcp_config_not_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout='{"env":{"TOKEN":"secret-value"}}', stderr="secret-value", returncode=0))
    runner = launcher.Runner(tmp_path, tmp_path / "log.txt")
    runner.run(["codex.exe", "mcp", "list", "--json"], private=True)
    assert "secret-value" not in runner.log.read_text()


def test_real_stdio_discovery_without_catia():
    report = asyncio.run(probe_transports())
    assert report["inspection_tools"] == 13
    assert report["full_tools"] == 81
    assert report["catia_com"] == "NOT_TESTED"
    assert report["codex_executor_tool_access"] == "NOT_TESTED"


def test_start_uses_fresh_session_and_readiness_only(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "diagnose", lambda *a: None)
    called = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda args, **kw: called.append(args) or 0)
    runner = launcher.Runner(tmp_path, tmp_path / "start.log")
    monkeypatch.setattr(runner, "run", lambda *a, **kw: SimpleNamespace(stdout="--no-daemon"))
    assert launcher.start(runner, Path("codex.exe")) == 0
    assert "--no-daemon" in called[0]
    assert "not authorization to model" in called[0][-1]
    assert "without calling them" in called[0][-1]


def test_no_windows_launcher_changes_powershell_policy():
    for name in ("INSTALL.cmd", "START_CATIA_AI.cmd", "DIAGNOSE.cmd"):
        source = (ROOT / name).read_text().lower()
        assert "powershell" not in source
        assert "bypass" not in source
        assert 'cd /d "%~dp0"' in source
