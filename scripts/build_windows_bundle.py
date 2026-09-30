"""Assemble the self-contained Windows payload used by CATIA-AI-Setup.exe.

Run on Windows with CPython 3.13.3 x64. The final user machine receives a
portable Python runtime with dependencies, plus the official native Codex CLI;
it does not need Node, Git, PowerShell scripts, or a preinstalled Python.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = "3.13.3"
CODEX_VERSION = os.environ.get("CATIA_AI_CODEX_VERSION", "0.159.1")
CODEX_ASSET = "codex-x86_64-pc-windows-msvc.exe.zip"
OUTPUT = ROOT / "dist" / "windows-full"
APP = OUTPUT / "CATIA-AI"
PROJECT = APP / "project"
RUNTIME = APP / "runtime"


def download(url: str, destination: Path) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CATIA-AI-Windows-Builder"})
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def copy_project() -> None:
    ignored = shutil.ignore_patterns(
        ".git", ".venv", ".local", ".pytest_cache", ".ruff_cache", "__pycache__",
        "*.pyc", "*.egg-info", "tests", "dist", "build", ".claude", ".github",
        "installer", "build_windows_bundle.py",
    )
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    shutil.copytree(ROOT, PROJECT, ignore=ignored)


def install_python_runtime(temporary: Path) -> dict[str, str]:
    if sys.platform != "win32" or sys.version_info[:3] != (3, 13, 3):
        raise RuntimeError("Build this installer on Windows with CPython 3.13.3 x64.")
    python_zip = temporary / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    python_url = (
        f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
        f"python-{PYTHON_VERSION}-embed-amd64.zip"
    )
    python_sha = download(python_url, python_zip)
    python_dir = RUNTIME / "python"
    python_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(python_zip) as archive:
        archive.extractall(python_dir)

    pth = python_dir / "python313._pth"
    pth.write_text(
        "python313.zip\n.\nLib\\site-packages\nimport site\n", encoding="utf-8"
    )
    site_packages = python_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--upgrade", "--target", str(site_packages), str(ROOT / ".[drawings]"),
        ],
        cwd=ROOT,
        check=True,
        timeout=900,
    )
    return {"python": PYTHON_VERSION, "python_embed_sha256": python_sha}


def install_codex(temporary: Path) -> dict[str, str]:
    release_url = f"https://api.github.com/repos/openai/codex/releases/tags/rust-v{CODEX_VERSION}"
    request = urllib.request.Request(
        release_url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CATIA-AI-Windows-Builder"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        release = json.load(response)
    asset = next((item for item in release.get("assets", []) if item["name"] == CODEX_ASSET), None)
    if asset is None:
        raise RuntimeError(f"Official Codex release {CODEX_VERSION} has no {CODEX_ASSET} asset.")
    expected_sha = asset.get("digest", "")
    if not expected_sha.startswith("sha256:"):
        raise RuntimeError("GitHub release metadata did not provide the Codex SHA-256 digest.")

    archive_path = temporary / CODEX_ASSET
    actual_sha = download(asset["browser_download_url"], archive_path)
    if actual_sha.lower() != expected_sha.removeprefix("sha256:").lower():
        raise RuntimeError("Downloaded Codex archive failed the official SHA-256 check.")

    codex_dir = RUNTIME / "codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        matches = [name for name in archive.namelist() if Path(name).name.lower() == CODEX_ASSET.removesuffix(".zip").lower()]
        if len(matches) != 1:
            raise RuntimeError("Codex archive did not contain exactly one expected Windows executable.")
        with archive.open(matches[0]) as source, (codex_dir / "codex.exe").open("wb") as target:
            shutil.copyfileobj(source, target)
    license_path = APP / "licenses" / "CODEX-LICENSE.txt"
    download(
        f"https://raw.githubusercontent.com/openai/codex/rust-v{CODEX_VERSION}/LICENSE",
        license_path,
    )
    return {"codex": CODEX_VERSION, "codex_archive_sha256": actual_sha}


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    copy_project()
    temporary = OUTPUT / ".downloads"
    temporary.mkdir()
    try:
        manifest = install_python_runtime(temporary)
        manifest.update(install_codex(temporary))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    (APP / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    licenses = APP / "THIRD_PARTY_NOTICES.txt"
    licenses.write_text(
        "CATIA AI bundles the following third-party runtimes:\n"
        f"- CPython {PYTHON_VERSION}, PSF License; see runtime/python/LICENSE.txt.\n"
        f"- OpenAI Codex CLI {CODEX_VERSION}, Apache-2.0; see licenses/CODEX-LICENSE.txt.\n"
        "- Python MCP dependencies retain their license metadata under "
        "runtime/python/Lib/site-packages/*.dist-info/licenses.\n",
        encoding="utf-8",
    )
    print(f"Prepared self-contained x64 payload at {APP}")
    print("The payload includes Python, pywin32/MCP dependencies and native Codex; Node is not needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
