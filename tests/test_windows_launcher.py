"""No downloads, real Codex configuration, or CATIA operations in these tests."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import windows_launcher as launcher
from scripts.check_mcp_transport import probe_transports
try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]


def prepared_project(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    for role_file in (ROOT / ".codex" / "agents").glob("*.toml"):
        shutil.copyfile(role_file, agents / role_file.name)
    (tmp_path / ".codex" / "config.toml").write_bytes(b"# user settings\n[agents]\nenabled=true\n")
    return python


def test_roles_do_not_claim_independent_mcp_access():
    for role_file in (ROOT / ".codex" / "agents").glob("*.toml"):
        result = tomllib.loads(role_file.read_text())
        assert "mcp_servers" not in result and "sandbox_mode" not in result
        assert "Never call CATIA" in " ".join(result["developer_instructions"].split())


@pytest.mark.parametrize("team", [False, True])
def test_session_overrides_are_complete_and_do_not_write_config(tmp_path, team):
    python = prepared_project(tmp_path)
    config = tmp_path / ".codex" / "config.toml"
    original = config.read_bytes()
    args = launcher.session_overrides(tmp_path, team=team)
    data = tomllib.loads("\n".join(args[1::2]))
    assert data["agents"]["enabled"] is team
    if team:
        assert data["agents"]["max_concurrent_threads_per_session"] == 5
    full = data["mcp_servers"]["catia-v5"]
    assert full["command"] == str(python.resolve())
    assert full["enabled"] is full["required"] is True
    assert full["args"] == ["-m", "catia_mcp"]
    assert full["default_tools_approval_mode"] == "approve"
    assert "approval_policy" not in data and "sandbox_mode" not in data
    inspect = data["mcp_servers"]["catia-v5-inspect"]
    assert inspect["enabled"] is inspect["required"] is False
    assert inspect["command"] == str(python.resolve())
    assert inspect["args"] == ["-m", "catia_mcp", "--inspection-only"]
    # Values must also be accepted by the npm batch launcher.
    launcher.windows_command(["codex.cmd", *args], "cmd.exe")
    assert config.read_bytes() == original
    assert not (tmp_path / ".local").exists()


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
    command.write_bytes(b"@echo off\r\necho [%~1]\r\necho [%~2]\r\necho [%~3]\r\n")
    setting = launcher.session_overrides(folder)[-1]
    result = subprocess.run(launcher.windows_command(
        [str(command), "argument with spaces", "plain", setting], os.environ["COMSPEC"]),
        capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["[argument with spaces]", "[plain]", f"[{setting}]"]


def entry(python, *, enabled=True, writer=True):
    return {"name": "catia-v5" if writer else "catia-v5-inspect", "enabled": enabled,
            "transport": {"type": "stdio", "command": str(python),
                          "args": ["-m", "catia_mcp"] + ([] if writer else ["--inspection-only"])}}


def test_existing_disabled_or_foreign_entry_is_not_silently_changed(tmp_path):
    python = tmp_path / "python.exe"
    launcher.check_entry(entry(python), python)
    with pytest.raises(launcher.SetupError, match="disabled"):
        launcher.check_entry(entry(python, enabled=False), python)
    with pytest.raises(launcher.SetupError, match="differ"):
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
        return SimpleNamespace(stdout=json.dumps(list(self.entries.values())), returncode=0)


def test_diagnose_without_roles_or_global_registration(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    runner = FakeRunner(tmp_path, {"catia-v5": entry(python),
        "catia-v5-inspect": entry(python, writer=False, enabled=False)})
    runner.say = lambda _: None
    launcher.diagnose(runner, tmp_path / "codex.cmd")
    assert len(runner.calls) == 2
    args, kwargs = runner.calls[0]
    assert "agents.enabled=false" in args
    assert kwargs["private"]
    assert not any("add" in args or "remove" in args for args, _ in runner.calls)
    assert not any("configure_codex_agents.py" in str(args) for args, _ in runner.calls)
    assert not list(tmp_path.iterdir())


def test_wrong_effective_session_is_rejected(tmp_path):
    python = tmp_path / "python.exe"
    for entries in ({}, {"catia-v5": entry(tmp_path / "other.exe")},
                    {"catia-v5": entry(python, enabled=False)},
                    {"catia-v5": entry(python), "catia-v5-inspect": entry(python, writer=False)}):
        with pytest.raises(launcher.SetupError):
            launcher.validate_session(entries, python)


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
    assert report["full_tools"] == 163
    assert report["catia_com"] == "NOT_TESTED"
    assert report["codex_session_tool_access"] == "NOT_TESTED"


def test_start_uses_fresh_session_and_readiness_only(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "diagnose", lambda *a, **kw: None)
    called = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda args, **kw: called.append(args) or 0)
    runner = launcher.Runner(tmp_path, tmp_path / "start.log")
    monkeypatch.setattr(runner, "run", lambda *a, **kw: SimpleNamespace(stdout="--no-daemon"))
    assert launcher.start(runner, Path("codex.exe")) == 0
    assert "--no-daemon" in called[0]
    assert "not authorization to model" in called[0][-1]
    assert "without calling them" in called[0][-1]
    assert "agents.enabled=false" in called[0]
    assert "do not spawn" in called[0][-1]


@pytest.mark.parametrize("client", ["codex", "claude"])
def test_team_batch_launch_keeps_one_cad_caller_and_bounded_overview(tmp_path, monkeypatch, client):
    inputs = [tmp_path / f"part-{i}.pdf" for i in range(5)]
    pages = [tmp_path / f"part-{i}-page-{j}.png" for i in range(5) for j in range(3)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"files": [
        {"source": str(source), "pages": list(map(str, pages[i*3:(i+1)*3]))}
        for i, source in enumerate(inputs)]}))
    received = []
    def prepare_bundle(sources, output_root):
        received.append((sources, output_root))
        return manifest
    monkeypatch.setitem(sys.modules, "scripts.cad_team", SimpleNamespace(prepare_bundle=prepare_bundle))
    monkeypatch.setattr(launcher, "diagnose", lambda *a, **kw: None)
    monkeypatch.setattr(launcher, "diagnose_claude", lambda *a: tmp_path / "claude.json")
    calls = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda args, **kw: calls.append(args) or 0)
    runner = launcher.Runner(tmp_path, tmp_path / "start.log")
    monkeypatch.setattr(runner, "run", lambda *a, **kw: SimpleNamespace(stdout="--no-daemon"))
    start = launcher.start if client == "codex" else launcher.start_claude
    assert start(runner, Path(client + ".exe"), inputs, team=True) == 0
    assert received[0][0] == inputs
    argv = calls[0]
    prompt = argv[-1]
    assert str(manifest) in prompt and "NOT the complete batch" in prompt
    assert "NO CATIA calls" in prompt and "FIVE parallel" in prompt
    assert "not authorization to model" in prompt and "Fix and AutoConstraint" in prompt
    assert "whole-desktop UI input" not in prompt and "--model" not in argv
    if client == "codex":
        assert "agents.enabled=true" in argv
        assert "agents.max_concurrent_threads_per_session=5" in argv
        attached = [argv[i+1] for i, arg in enumerate(argv) if arg == "--image"]
        assert attached == list(map(str, pages[:5]))
    launcher.windows_command([client + ".cmd", *argv[1:]], "cmd.exe")


def test_single_or_smart_mode_cannot_silently_consume_a_batch(tmp_path):
    with pytest.raises(launcher.SetupError, match="Multiple inputs"):
        launcher.launch_inputs([tmp_path / "one.pdf", tmp_path / "two.pdf"], team=False)
    with pytest.raises(launcher.SetupError, match="cannot combine"):
        launcher.start(None, Path("codex.exe"), smart=True, team=True)


def test_no_windows_launcher_changes_powershell_policy():
    for name in ("INSTALL.cmd", "START_AI.cmd", "DIAGNOSE.cmd", "UPDATE.cmd"):
        source = (ROOT / name).read_text().lower()
        if name == "INSTALL.cmd":
            ps_lines = [line for line in source.splitlines() if line.startswith("powershell.exe")]
            assert len(ps_lines) == 1 and "get-authenticodesignature" in ps_lines[0]
            assert "python software foundation" in ps_lines[0]
        else:
            assert "powershell" not in source
        assert "-executionpolicy" not in source
        assert "set-executionpolicy" not in source
        assert "unblock-file" not in source
        assert "bypass" not in source
        assert 'cd /d "%~dp0"' in source


def test_start_attaches_all_drawing_images_without_modeling(tmp_path, monkeypatch):
    from scripts import drawing_inputs
    monkeypatch.setattr(launcher, "diagnose", lambda *a, **kw: None)
    pages = [tmp_path / "page-001.png", tmp_path / "page-002.png"]
    monkeypatch.setattr(drawing_inputs, "prepare_drawing", lambda *a: pages)
    captured = []
    monkeypatch.setattr(launcher.subprocess, "call", lambda args, **kw: captured.append(args) or 0)
    runner = launcher.Runner(tmp_path, tmp_path / "log")
    monkeypatch.setattr(runner, "run", lambda *a, **kw: SimpleNamespace(stdout=""))
    launcher.start(runner, Path("codex.exe"), tmp_path / "drawing.pdf")
    args = captured[0]
    assert [args[i + 1] for i, arg in enumerate(args) if arg == "--image"] == list(map(str, pages))
    assert "Do not model yet" in args[-1]


@pytest.mark.skipif(shutil.which("codex") is None, reason="Optional local Codex config parser")
@pytest.mark.parametrize("team", [False, True])
def test_real_codex_parses_session_overrides_without_registering(tmp_path, team):
    # list only: no model request, authentication or CATIA server startup.
    # Never print the returned JSON: unrelated user MCP entries may have secrets.
    result = subprocess.run([shutil.which("codex"), *launcher.session_overrides(tmp_path, team=team),
                             "mcp", "list", "--json"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, "Codex could not parse scoped overrides"
    entries = {entry["name"]: entry for entry in json.loads(result.stdout)}
    launcher.validate_session(entries, tmp_path / ".venv" / "Scripts" / "python.exe")


def test_install_no_longer_mutates_roles_or_global_mcp(tmp_path, monkeypatch):
    prepared_project(tmp_path)
    before = {str(p): p.read_bytes() for p in (tmp_path / ".codex").rglob("*.toml")}
    (tmp_path / ".local").mkdir()
    runner = FakeRunner(tmp_path, {})
    runner.say = lambda _: None
    monkeypatch.setattr(launcher, "get_runtime", lambda *a, **kw: (None, tmp_path / "codex.exe"))
    launcher.install_project(runner)
    launcher.install_project(runner)
    assert before == {str(p): p.read_bytes() for p in (tmp_path / ".codex").rglob("*.toml")}
    assert not any("configure_codex_agents.py" in str(args) for args, _ in runner.calls)
    assert not any("mcp" in args for args, _ in runner.calls)
    assert any(str(tmp_path) + "[drawings]" in args for args, _ in runner.calls)


def test_session_override_rejects_unrepresentable_path(tmp_path):
    with pytest.raises(launcher.SetupError, match="apostrophes"):
        launcher.session_overrides(tmp_path / "someone's project")
    with pytest.raises(launcher.SetupError, match="too long"):
        launcher.windows_command(["codex.cmd", "x" * 8100], "cmd.exe")
