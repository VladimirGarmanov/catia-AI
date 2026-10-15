"""Download official portable Node LTS into the project, with checksum validation.

No PATH/registry edits, elevation, file picker, execution-policy changes or TLS bypass.
"""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile

BASE = "https://nodejs.org/dist/latest-v24.x/"
MAX_ARCHIVE = 150 * 1024 * 1024
MAX_EXTRACTED = 500 * 1024 * 1024


def download(url, destination, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "CATIA-AI-Installer"})
    total = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
        if not response.geturl().startswith(BASE):
            raise RuntimeError("Unexpected Node download redirect")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise RuntimeError("Node download exceeds size limit")
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest()


def extract(archive_path, destination, top_directory):
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if sum(i.file_size for i in infos) > MAX_EXTRACTED:
            raise RuntimeError("Node archive exceeds extraction limit")
        paths = set()
        for info in infos:
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in info.filename
                    or ":" in info.filename or not path.parts or path.parts[0] != top_directory
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise RuntimeError("Unsafe member in Node archive")
            relative = Path(*path.parts[1:])
            if not relative.parts:
                continue
            folded = str(relative).casefold()
            if folded in paths:
                raise RuntimeError("Duplicate member in Node archive")
            paths.add(folded)
        for info in infos:
            parts = PurePosixPath(info.filename).parts[1:]
            if not parts:
                continue
            target = destination.joinpath(*parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    if not (destination / "node.exe").is_file() or not (destination / "npm.cmd").is_file():
        raise RuntimeError("Official Node archive missing node.exe or npm.cmd")


def install_node(root, say=print):
    if os.name != "nt":
        raise RuntimeError("Portable Windows Node installation is Windows-only")
    architecture = os.environ.get("PROCESSOR_ARCHITEW6432", os.environ.get("PROCESSOR_ARCHITECTURE", "")).upper()
    arch = {"AMD64": "x64", "ARM64": "arm64"}.get(architecture)
    if arch is None:
        raise RuntimeError(f"Unsupported Windows architecture: {architecture}")
    local = Path(root) / ".local"
    local.mkdir(parents=True, exist_ok=True)
    target = local / "node"
    if target.exists():
        if (target / "node.exe").is_file() and (target / "npm.cmd").is_file():
            return (target / "node.exe").resolve()
        raise RuntimeError(f"Incomplete Node directory: {target}. Inspect it before replacing; nothing overwritten.")
    say(f"Downloading official portable Node 24 LTS ({arch}) into {target}")
    with tempfile.TemporaryDirectory(prefix="node-install-", dir=local) as temporary:
        staging = Path(temporary)
        sums = staging / "SHASUMS256.txt"
        download(BASE + "SHASUMS256.txt", sums, 1024 * 1024)
        matches = re.findall(r"^([0-9a-fA-F]{64})\s+(node-v24\.\d+\.\d+-win-" + arch + r"\.zip)\s*$",
                             sums.read_text(encoding="utf-8"), re.M)
        if len(matches) != 1:
            raise RuntimeError("Official checksums did not identify exactly one supported Node ZIP")
        expected, filename = matches[0]
        archive = staging / filename
        actual = download(BASE + filename, archive, MAX_ARCHIVE)
        if actual.lower() != expected.lower():
            raise RuntimeError("Node ZIP checksum mismatch; archive will not be executed")
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        extract(archive, unpacked, filename.removesuffix(".zip"))
        unpacked.rename(target)
    say("Node installed locally; Windows PATH and security policies were not changed.")
    return (target / "node.exe").resolve()
