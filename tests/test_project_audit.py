"""Cross-module regressions found by the full offline audit. No live downloads/COM."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.connection import CATIAConnection
from catia_mcp.runtime import CADOperationError
from catia_mcp.server import CATIAMCPServer
from scripts import update_project as updater
from scripts import windows_launcher as launcher


def test_mode_specific_schema_keeps_signed_distances_and_positive_tolerances():
    server = CATIAMCPServer()
    try:
        validate = Draft202012Validator(server._schemas["catia_wireframe_surface"])
        common = dict(document_id="doc", expected_revision=0, request_id="req", container_handle="gs")
        point = dict(common, mode="point_surface", surface_handle="s", direction=[1, 0, 0], distance_mm=-5)
        validate.validate(point)
        healing = dict(common, mode="healing", surface_handle="s", distance_mm=-5, tangency_deg=1)
        assert not validate.is_valid(healing)
        validate.validate(dict(healing, distance_mm=0.01))
    finally:
        server.worker.shutdown()


def test_connection_distinguishes_missing_document_from_busy_com():
    class App:
        Caption = "CATIA"
        Documents = NS(Count=0)
        @property
        def ActiveDocument(self):
            raise RuntimeError("RPC rejected")
    conn = CATIAConnection()
    conn.app = App()
    with pytest.raises(CADOperationError) as error:
        conn.active_document
    assert error.value.code == "NO_ACTIVE_DOCUMENT"
    conn.app.Documents.Count = 1
    with pytest.raises(CADOperationError) as error:
        conn.active_document
    assert error.value.code == "DOCUMENT_UNAVAILABLE"


def test_bundled_clients_use_the_updated_source_not_site_packages(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    python = tmp_path / "runtime/python/python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    from scripts.configure_codex_agents import tomllib
    overrides = tomllib.loads("\n".join(launcher.session_overrides(root)[1::2]))
    expected = [str(root / "scripts/mcp_entry.py")]
    full = overrides["mcp_servers"]["catia-v5"]
    assert full["args"] == expected
    launcher.check_entry(full, python, root=root)
    claude = json.loads(launcher.claude_session_config(root).read_text())["mcpServers"]["catia-v5"]
    assert claude["args"] == expected
    # Isolated Python does not add the script's directory to sys.path. Use fake
    # project modules to prove the same bootstrap condition as the embedded EXE.
    (root / "scripts").mkdir()
    source = Path(__file__).resolve().parents[1] / "scripts/mcp_entry.py"
    shutil.copyfile(source, root / "scripts/mcp_entry.py")
    package = root / "catia_mcp"
    package.mkdir()
    (package / "__init__.py").touch()
    (package / "server.py").write_text('def main():\n    print("PROJECT_SOURCE")\n')
    result = subprocess.run([sys.executable, "-I", *expected], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "PROJECT_SOURCE"


def test_update_preserves_user_data_and_updates_its_python_source(tmp_path, monkeypatch):
    root, source = tmp_path / "project", tmp_path / "incoming"
    monkeypatch.setattr(updater, "ROOT", root)
    paths = ["catia_mcp/example.py", "scripts/update_project.py", ".codex/config.toml", ".mcp.json",
             ".claude/settings.local.json", ".env", "work/part.CATPart", "models/notes.txt"]
    for relative in paths:
        for folder, content in ((root, "local"), (source, "incoming")):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
    assert updater.apply_update(source, tmp_path / "backup") == 2
    for relative in paths:
        assert (root / relative).read_text() == ("incoming" if relative.endswith(".py") else "local")
    assert updater.apply_update(source, tmp_path / "backup2") == 0


def test_update_pip_failure_is_not_success_and_is_retried(tmp_path, monkeypatch):
    root, source = tmp_path / "project", tmp_path / "incoming"
    monkeypatch.setattr(updater, "ROOT", root)
    python = root / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    source.mkdir()
    (source / "pyproject.toml").write_text("new metadata")
    calls = []
    monkeypatch.setattr(updater.subprocess, "run", lambda *a, **k: calls.append(a) or NS(returncode=1))
    with pytest.raises(RuntimeError, match="dependency installation failed"):
        updater.apply_update(source, tmp_path / "backup")
    assert (root / "pyproject.toml").read_text() == "new metadata"
    assert (root / ".local/dependencies-pending").is_file()
    monkeypatch.setattr(updater.subprocess, "run", lambda *a, **k: calls.append(a) or NS(returncode=0))
    assert updater.apply_update(source, tmp_path / "backup2") == 0
    assert len(calls) == 2 and not (root / ".local/dependencies-pending").exists()


def test_update_restores_replaced_files_on_copy_failure(tmp_path, monkeypatch):
    root, source = tmp_path / "project", tmp_path / "incoming"
    root.mkdir()
    source.mkdir()
    monkeypatch.setattr(updater, "ROOT", root)
    for name in ("a.py", "b.py"):
        (root / name).write_text("old")
        (source / name).write_text("new")
    monkeypatch.setattr(updater, "project_files", lambda _: [(source / n, Path(n)) for n in ("a.py", "b.py")])
    replace = updater.os.replace
    def fail_second(src, dst):
        if dst.name == "b.py":
            raise OSError("file locked")
        replace(src, dst)
    monkeypatch.setattr(updater.os, "replace", fail_second)
    with pytest.raises(RuntimeError, match="rollback attempted"):
        updater.apply_update(source, tmp_path / "backup")
    assert (root / "a.py").read_text() == (root / "b.py").read_text() == "old"


@pytest.mark.parametrize("names", [["repo/a.py", "repo/A.py"], ["repo/..\\escape.py"], ["repo/../escape.py"]])
def test_update_rejects_unsafe_windows_archive_paths(tmp_path, names):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name in names:
            stream.writestr(name, "data")
    with pytest.raises(RuntimeError):
        updater.extract_project(archive, tmp_path / "unpacked")
