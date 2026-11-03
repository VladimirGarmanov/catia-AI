"""Update CATIA AI project files from the public GitHub main branch.

Launched by UPDATE.cmd with the project's existing Python. It needs no Git or
PowerShell execution-policy changes and preserves local runtime and user data.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
# Embedded Python does not add the script directory to sys.path. Resolve the
# same current project source as the launcher, not a stale installed copy.
sys.path.insert(0, str(ROOT))
from scripts.project_layout import retired_files

ARCHIVE_URL = "https://github.com/VladimirGarmanov/catia-AI/archive/refs/heads/main.zip"
PROTECTED_DIRECTORIES = {
    ".git", ".venv", ".local", "runtime", "traffic", "dist", "build",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".idea", "drawings", "models", "user_data",
}
PROTECTED_EXTENSIONS = {
    ".catpart", ".catproduct", ".catdrawing", ".pdf", ".heic", ".png",
    ".jpg", ".jpeg", ".stp", ".step", ".igs", ".iges", ".stl",
}
PRESERVED_PATHS = {".codex/config.toml", ".mcp.json", ".claude/settings.json", ".claude/settings.local.json", "update.cmd"}
MAX_ARCHIVE = 200 * 1024 * 1024
MAX_EXTRACTED = 512 * 1024 * 1024


def is_preserved(relative: Path) -> bool:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts or any(part in PROTECTED_DIRECTORIES for part in parts):
        return True
    if relative.as_posix().casefold() in PRESERVED_PATHS:
        return True
    if relative.name.casefold() == ".env" or relative.name.casefold().startswith(".env."):
        return True
    if relative.suffix.casefold() in {".pyc", ".pyo", ".log"}:
        return True
    if relative.suffix.casefold() in PROTECTED_EXTENSIONS:
        return True
    return False


def download_archive(destination: Path) -> None:
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": "CATIA-AI-Project-Updater", "Accept": "application/zip"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_ARCHIVE:
                raise RuntimeError("Project archive exceeds download size limit")
            out.write(chunk)


def extract_project(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if sum(member.file_size for member in members) > MAX_EXTRACTED:
            raise RuntimeError("Project archive exceeds extraction size limit")
        roots = {
            PurePosixPath(member.filename).parts[0]
            for member in members if PurePosixPath(member.filename).parts
        }
        if (len(roots) != 1
                or any(root in {".", "..", "/"} or ":" in root for root in roots)):
            raise RuntimeError("GitHub archive has an unexpected directory layout")
        archive_root = destination / next(iter(roots))
        resolved_root = archive_root.resolve()
        seen = set()
        for member in members:
            raw_name = member.orig_filename
            parts = PurePosixPath(raw_name).parts
            if ("\\" in raw_name or not parts or parts[0] != archive_root.name
                    or any(part in {".", ".."} or ":" in part for part in parts)):
                raise RuntimeError("GitHub archive contains a path outside the repository root")
            key = member.filename.rstrip("/").casefold()
            if key in seen:
                raise RuntimeError("Project archive has duplicate/case-colliding paths")
            seen.add(key)
            relative_parts = parts[1:]
            if not relative_parts:
                continue
            target = archive_root.joinpath(*relative_parts)
            if os.path.commonpath((str(resolved_root), str(target.resolve()))) != str(resolved_root):
                raise RuntimeError(f"Unsafe archive path: {member.filename}")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Symbolic links are not accepted: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as out:
                shutil.copyfileobj(source, out)
        return archive_root


def project_files(source_root: Path):
    for folder, directories, files in os.walk(source_root):
        folder_path = Path(folder)
        relative_folder = folder_path.relative_to(source_root)
        directories[:] = [name for name in directories
                          if not is_preserved(relative_folder / name)]
        for filename in files:
            source = folder_path / filename
            relative = source.relative_to(source_root)
            if source.is_symlink() or is_preserved(relative):
                continue
            yield source, relative


def apply_update(source_root: Path, backup_root: Path) -> int:
    changed: list[tuple[Path, Path | None]] = []
    token = uuid.uuid4().hex
    dependency_metadata_changed = False
    try:
        # Older UPDATE.cmd/Python copies also remain usable: on their first
        # update START_AI/INSTALL will perform the same bounded cleanup.
        if (source_root / "WINDOWS.md").is_file():
            retired = [(target, relative) for target, relative in retired_files(ROOT)
                       if not (source_root / relative).exists()]
            for target, relative in retired:
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                changed.append((target, backup))
                target.unlink()
        for source, relative in project_files(source_root):
            target = ROOT / relative
            candidate = target
            while candidate != ROOT:
                if candidate.is_symlink():
                    raise RuntimeError(f"Refusing to overwrite a linked project path: {relative}")
                candidate = candidate.parent
            if not target.resolve().is_relative_to(ROOT.resolve()):
                raise RuntimeError(f"Update target is outside the project: {relative}")
            if target.is_file() and target.read_bytes() == source.read_bytes():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative.as_posix().casefold() in {"pyproject.toml", "requirements.txt"}:
                dependency_metadata_changed |= (
                    not target.is_file() or target.read_bytes() != source.read_bytes()
                )
            backup: Path | None = None
            if target.is_file():
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            changed.append((target, backup))
            temporary_target = target.with_name(target.name + f".updating-{token}")
            try:
                shutil.copyfile(source, temporary_target)
                os.replace(temporary_target, target)
            finally:
                temporary_target.unlink(missing_ok=True)
    except Exception as exc:
        rollback_errors = []
        for target, backup in reversed(changed):
            try:
                if backup is not None:
                    shutil.copy2(backup, target)
                elif target.exists():
                    target.unlink()
            except OSError as rollback_error:
                rollback_errors.append(f"{target}: {rollback_error}")
        detail = ""
        if rollback_errors:
            detail = " Rollback errors: " + "; ".join(rollback_errors)
        raise RuntimeError(f"File update failed ({exc}); rollback attempted.{detail}") from exc
    # pip is not transactional. Keep applied source files if pip fails, record
    # the incomplete step, and make the next UPDATE retry it even with no diff.
    pending = ROOT / ".local" / "dependencies-pending"
    if dependency_metadata_changed or pending.exists():
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text("Run INSTALL.cmd (source ZIP) or install the newest EXE.\n", encoding="utf-8")
        environment_python = ROOT / ".venv" / "Scripts" / "python.exe"
        if not environment_python.is_file():
            raise RuntimeError("Source files updated, but bundled dependencies need the newest CATIA-AI-Setup.exe; update incomplete")
        print("Refreshing the project's .venv dependencies...", flush=True)
        result = subprocess.run(
            [str(environment_python), "-m", "pip", "install", "-e", str(ROOT) + "[drawings]"],
            cwd=ROOT, check=False, timeout=900,
        )
        if result.returncode:
            raise RuntimeError("Source files updated, but dependency installation failed; rerun UPDATE.cmd or INSTALL.cmd")
        pending.unlink()
    return len(changed)


def main() -> int:
    if not (ROOT / "catia_mcp" / "server.py").is_file() or not (ROOT / "INSTALL.cmd").is_file():
        print("STOP: run UPDATE.cmd from the CATIA AI project folder.")
        return 1
    print("Downloading latest CATIA AI project files from GitHub...", flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="catia-ai-update-") as temporary_name:
            temporary = Path(temporary_name)
            archive_path = temporary / "project.zip"
            download_archive(archive_path)
            source_root = extract_project(archive_path, temporary / "extracted")
            for required in ("catia_mcp/server.py", "pyproject.toml", "INSTALL.cmd"):
                if not (source_root / required).is_file():
                    raise RuntimeError(f"Downloaded project is incomplete: missing {required}")
            count = apply_update(source_root, temporary / "backup")
        print(f"Updated {count} project files.")
        print("Preserved .venv/runtime, .local, .codex/config.toml, traffic, and local CAD/drawing files.")
        print("Restart CATIA AI/Codex so its MCP server loads the updated code.")
        return 0
    except Exception as exc:
        print(f"STOP: {exc}")
        print("If GitHub access is blocked on this network, ask IT or update from a fresh ZIP.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
