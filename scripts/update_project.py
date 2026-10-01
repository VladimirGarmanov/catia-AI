"""Update CATIA AI project files from the public GitHub main branch.

Launched by UPDATE.cmd with the project's existing Python. It needs no Git or
PowerShell execution-policy changes and preserves local runtime and user data.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_URL = "https://github.com/VladimirGarmanov/catia-AI/archive/refs/heads/main.zip"
PROTECTED_DIRECTORIES = {
    ".git", ".venv", ".local", "runtime", "traffic", "dist", "build",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".idea",
}
PROTECTED_EXTENSIONS = {
    ".catpart", ".catproduct", ".catdrawing", ".pdf", ".heic", ".png",
    ".jpg", ".jpeg", ".stp", ".step", ".igs", ".iges", ".stl",
}
PRESERVED_PATHS = {".codex/config.toml", "update.cmd", "scripts/update_project.py"}


def is_preserved(relative: Path) -> bool:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts or any(part in PROTECTED_DIRECTORIES for part in parts):
        return True
    if relative.as_posix().casefold() in PRESERVED_PATHS:
        return True
    if relative.suffix.casefold() in {".pyc", ".pyo", ".log"}:
        return True
    if relative.suffix.casefold() in PROTECTED_EXTENSIONS and (
        len(relative.parts) == 1 or parts[0] in {"drawings", "models", "user_data"}
    ):
        return True
    return False


def download_archive(destination: Path) -> None:
    request = urllib.request.Request(
        ARCHIVE_URL,
        headers={"User-Agent": "CATIA-AI-Project-Updater", "Accept": "application/zip"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def extract_project(archive_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        roots = {
            PurePosixPath(member.filename).parts[0]
            for member in members if PurePosixPath(member.filename).parts
        }
        if (len(roots) != 1
                or any(root in {".", "..", "/"} or ":" in root for root in roots)):
            raise RuntimeError("GitHub archive has an unexpected directory layout")
        archive_root = destination / next(iter(roots))
        resolved_root = archive_root.resolve()
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if (not parts or parts[0] != archive_root.name
                    or any(part in {".", ".."} or ":" in part for part in parts)):
                raise RuntimeError("GitHub archive contains a path outside the repository root")
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
        for source, relative in project_files(source_root):
            target = ROOT / relative
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
        if dependency_metadata_changed:
            environment_python = ROOT / ".venv" / "Scripts" / "python.exe"
            if environment_python.is_file():
                print("Dependency files changed; refreshing the project's .venv...", flush=True)
                result = subprocess.run(
                    [str(environment_python), "-m", "pip", "install", "-e", str(ROOT) + "[drawings]"],
                    cwd=ROOT,
                    check=False,
                    timeout=900,
                )
                if result.returncode:
                    print("Project files were updated, but dependency installation failed. "
                          "Run INSTALL.cmd to finish setup.")
            else:
                print("Dependency metadata changed. The bundled runtime is preserved; "
                      "install the latest CATIA-AI-Setup.exe to update Python dependencies.")
        return len(changed)
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
