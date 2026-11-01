"""Claude session configuration/launch contracts, without installing or logging in."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

from scripts import windows_launcher as launcher


def project(tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    (tmp_path / ".local").mkdir()
    return python


def test_claude_config_is_scoped_absolute_and_keeps_user_settings(tmp_path):
    python = project(tmp_path)
    settings = tmp_path / ".mcp.json"
    settings.write_text('{"mcpServers":{"other":{}}}')
    before = settings.read_bytes()
    first = launcher.claude_session_config(tmp_path)
    second = launcher.claude_session_config(tmp_path)
    assert first == second
    config = json.loads(first.read_text())
    assert set(config["mcpServers"]) == {"catia-v5"}
    full = config["mcpServers"]["catia-v5"]
    assert full["command"] == str(python.resolve())
    assert full["args"] == ["-m", "catia_mcp"] and full["type"] == "stdio"
    assert settings.read_bytes() == before


def test_claude_drawing_launch_uses_manifest_and_keeps_permissions(tmp_path, monkeypatch):
    project(tmp_path)
    image = tmp_path / "a page.png"
    image.touch()
    runner = NS(root=tmp_path, env={"COMSPEC": "cmd.exe"}, say=lambda _: None)
    monkeypatch.setattr(launcher, "diagnose_claude", lambda r, c: launcher.claude_session_config(r.root))
    monkeypatch.setattr("scripts.drawing_inputs.prepare_drawing", lambda *args: [image])
    calls = []
    monkeypatch.setattr(subprocess, "call", lambda *a, **kw: calls.append((a, kw)) or 0)
    assert launcher.start_claude(runner, Path("claude.exe"), tmp_path / "drawing.pdf") == 0
    argv = calls[0][0][0]
    assert "--strict-mcp-config" in argv and "--append-system-prompt-file" in argv
    assert not any("skip-permissions" in arg for arg in argv)
    assert "--image" not in argv and "Do not model yet" in argv[-1]
    assert json.loads((tmp_path / ".local" / "claude-drawing.json").read_text())["pages"] == [str(image)]
    launcher.windows_command(["claude.cmd", *argv[1:]], "cmd.exe")


def test_install_both_preserves_clients_and_local_runtime_state(tmp_path, monkeypatch):
    project(tmp_path)
    state_file = tmp_path / ".local" / "windows-runtime.json"
    state_file.write_text('{"custom_note":"keep"}')
    calls = []
    runner = NS(root=tmp_path, say=lambda _: None, run=lambda args, **kw: calls.append(args))
    clients = []
    def runtime(runner, *, install, client):
        assert install
        clients.append(client)
        return tmp_path / "node.exe", tmp_path / (client + ".exe")
    monkeypatch.setattr(launcher, "get_runtime", runtime)
    launcher.install_project(runner, "both")
    assert clients == ["codex", "claude"]
    state = json.loads(state_file.read_text())
    assert state["custom_note"] == "keep" and all(state[k].endswith(k+".exe") for k in clients)
    assert [args[-1] for args in calls if "diagnose" in args] == clients
    assert not (tmp_path / ".mcp.json").exists()


def test_claude_only_runtime_does_not_require_codex(tmp_path, monkeypatch):
    project(tmp_path)
    executable = tmp_path / "claude.exe"
    executable.touch()
    monkeypatch.setattr(launcher, "discover_claude", lambda *args: executable)
    monkeypatch.setattr(launcher, "discover_node", lambda *args: None)
    def forbidden(*args):
        raise AssertionError("Claude must not depend on Codex discovery")
    monkeypatch.setattr(launcher, "discover_codex", forbidden)
    commands = []
    runner = NS(root=tmp_path, run=lambda args: commands.append(args), say=lambda _: None)
    assert launcher.get_runtime(runner, install=False, client="claude") == (None, executable)
    assert commands == [[str(executable), "--version"]]
