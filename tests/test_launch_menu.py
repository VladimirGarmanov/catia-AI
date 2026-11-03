"""Launcher/menu and bounded upgrade regressions; no downloads, login or CATIA."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

from scripts import windows_launcher as launcher
from scripts import update_project as updater
from scripts import build_windows_bundle as bundle
from scripts.project_layout import RETIRED_PATHS, cleanup_retired

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("choices,client,mode", [
    (["1", "1"], "codex", "chat"), (["1", "2"], "codex", "drawing"),
    (["2", "3"], "claude", "team"), (["1", "4"], "codex", "smart"),
])
def test_menu_reaches_the_existing_client_and_input_pipeline(tmp_path, monkeypatch, choices, client, mode):
    replies = iter(choices)
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "os", NS(name="nt"))
    monkeypatch.setattr(launcher, "child_environment", lambda *args: {})
    python = tmp_path / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(launcher, "get_runtime", lambda *a, **kw: (None, Path(kw["client"] + ".exe")))
    from scripts import drawing_inputs
    inputs = [tmp_path / "part a.pdf", tmp_path / "part b.png"]
    monkeypatch.setattr(drawing_inputs, "choose_drawing", lambda: inputs[0])
    monkeypatch.setattr(drawing_inputs, "choose_drawings", lambda: inputs)
    calls = []
    def start(runner, executable, drawing, **kwargs):
        calls.append((executable, drawing, kwargs))
        return 0
    monkeypatch.setattr(launcher, "start", start)
    monkeypatch.setattr(launcher, "start_claude", start)
    assert launcher.main(["start"]) == 0
    executable, drawing, flags = calls.pop()
    assert executable.name == client + ".exe"
    assert drawing == ([] if mode == "chat" else inputs if mode == "team" else inputs[:1])
    assert flags["team"] == (mode == "team")
    assert flags.get("smart", False) == (mode == "smart")
    assert not calls


def test_explicit_options_do_not_prompt_and_bad_combinations_fail(monkeypatch):
    def forbidden(_):
        raise AssertionError("Explicit CLI flags must not open a menu")
    monkeypatch.setattr("builtins.input", forbidden)
    for argv in (["install", "--client", "both"], ["diagnose", "--client", "claude"],
                 ["start", "--client", "codex", "--mode", "team", "--drawing", "a.pdf", "--drawing", "b.pdf"]):
        args = launcher.parse_arguments(argv)
        assert launcher.select_options(args)
    assert args.team and not args.choose_drawings
    for argv in (["start", "--client", "claude", "--mode", "smart"],
                 ["start", "--mode", "chat", "--drawing", "a.pdf"],
                 ["start", "--mode", "team", "--smart-drawing"],
                 ["start", "--choose-drawing", "--drawing", "a.pdf"]):
        with pytest.raises(SystemExit) as exc:
            launcher.parse_arguments(argv)
        assert exc.value.code == 2


def test_install_choice_and_cancel_do_not_start_work(monkeypatch):
    replies = iter(["bad", "3", "1", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    args = launcher.parse_arguments(["install"])
    assert launcher.select_options(args) and args.client == "both"
    assert not launcher.select_options(launcher.parse_arguments(["start"]))
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError()))
    assert not launcher.select_options(launcher.parse_arguments(["diagnose"]))


def test_file_choice_without_tk_needs_no_new_command(monkeypatch):
    from scripts import drawing_inputs
    monkeypatch.setitem(sys.modules, "tkinter", None)
    replies = iter(['"C:/my drawings/a.pdf"', '"C:/my drawings/a.pdf"', 'C:/b.png', '', '0'])
    monkeypatch.setattr("builtins.input", lambda _: next(replies))
    assert drawing_inputs.choose_drawing() == Path("C:/my drawings/a.pdf")
    assert drawing_inputs.choose_drawings() == [Path("C:/my drawings/a.pdf"), Path("C:/b.png")]
    assert drawing_inputs.choose_drawings() == []


def test_cleanup_only_removes_known_retired_files(tmp_path):
    keep = ["START_AI.cmd", "my-launcher.cmd", ".local/handoffs/BRIEF.md",
            ".venv/Scripts/python.exe", ".codex/config.toml", "part.CATPart"]
    for relative in [*keep, *RETIRED_PATHS]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("keep exact content")
    assert set(cleanup_retired(tmp_path)) == set(RETIRED_PATHS)
    assert cleanup_retired(tmp_path) == []
    for relative in keep:
        assert (tmp_path / relative).read_text() == "keep exact content"
    assert {p.name for p in ROOT.glob("*.cmd")} == {"INSTALL.cmd", "START_AI.cmd", "DIAGNOSE.cmd", "UPDATE.cmd"}
    assert not list(ROOT.glob("*.ps1"))
    installer = (ROOT / "installer/CATIA-AI.iss").read_text()
    for relative in RETIRED_PATHS:
        assert '{app}\\project\\' + relative.replace("/", "\\") in installer


def test_cleanup_refuses_directory_replacements_before_deleting(tmp_path):
    first = tmp_path / RETIRED_PATHS[0]
    first.write_text("old launcher")
    (tmp_path / RETIRED_PATHS[1]).mkdir()
    with pytest.raises(OSError, match="directory"):
        cleanup_retired(tmp_path)
    assert first.read_text() == "old launcher"


def test_update_retires_launchers_and_rolls_deletions_back_on_failure(tmp_path, monkeypatch):
    root, source = tmp_path / "installed", tmp_path / "incoming"
    root.mkdir()
    source.mkdir()
    monkeypatch.setattr(updater, "ROOT", root)
    old = root / RETIRED_PATHS[0]
    old.write_text("old launcher")
    (root / "mine.cmd").write_text("user file")
    (source / "WINDOWS.md").write_text("new guide")
    (source / "START_AI.cmd").write_text("new menu")
    replace = updater.os.replace
    def fail(*args):
        raise OSError("file locked")
    monkeypatch.setattr(updater.os, "replace", fail)
    with pytest.raises(RuntimeError, match="rollback attempted"):
        updater.apply_update(source, tmp_path / "failed-backup")
    assert old.read_text() == "old launcher"
    monkeypatch.setattr(updater.os, "replace", replace)
    assert updater.apply_update(source, tmp_path / "backup") == 3
    assert not old.exists()
    assert (root / "mine.cmd").read_text() == "user file"
    assert updater.apply_update(source, tmp_path / "backup2") == 0


def test_bundle_does_not_ship_old_builds_or_root_user_files(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "payload"
    for relative in bundle.PROJECT_ENTRIES:
        target = source / relative
        if relative in {"catia_mcp", "CATIA_AGENT_CODEX_PACKAGE", "scripts", ".codex/agents"}:
            target.mkdir(parents=True)
            (target / "example.py").write_text("application code")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("application input")
    for relative in (".local/secrets.json", ".idea/workspace.xml", "build/old.py", "drawing.pdf", "catia_mcp.log"):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("must not ship")
    monkeypatch.setattr(bundle, "ROOT", source)
    monkeypatch.setattr(bundle, "PROJECT", destination)
    bundle.copy_project()
    assert all((destination / relative).exists() for relative in bundle.PROJECT_ENTRIES)
    assert not any(p.name in {".local", ".idea", "build", "drawing.pdf", "catia_mcp.log"} for p in destination.rglob("*"))


def test_isolated_python_loads_current_update_helpers_without_running_update(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-c",
         "import runpy,sys; data=runpy.run_path(sys.argv[1]); "
         "assert callable(data['retired_files']); print('IMPORTED_WITHOUT_UPDATE')",
         str(ROOT / "scripts/update_project.py")],
        cwd=tmp_path, capture_output=True, text=True, check=True, timeout=30,
    )
    assert result.stdout.strip() == "IMPORTED_WITHOUT_UPDATE"
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(os.name != "nt", reason="Requires real Windows cmd.exe")
def test_windows_entry_points_forward_help_without_installing(tmp_path):
    root = tmp_path / "project with spaces"
    (root / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/windows_launcher.py", root / "scripts/windows_launcher.py")
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")], check=True, timeout=60)
    for name in ("INSTALL.cmd", "START_AI.cmd", "DIAGNOSE.cmd"):
        shutil.copyfile(ROOT / name, root / name)
        command = launcher.windows_command([str(root / name), "--help"], os.environ.get("COMSPEC", "cmd.exe"))
        result = subprocess.run(command, cwd=root, input="\n", capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "--client" in result.stdout and "--mode" in result.stdout
    assert not (root / ".local").exists()
