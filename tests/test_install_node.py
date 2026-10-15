"""Offline installer checks. Never downloads or executes Windows binaries."""
import hashlib
from types import SimpleNamespace as NS
import zipfile
import pytest
from scripts import install_node as node


def make_archive(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_install_download_verify_extract_and_reuse(tmp_path, monkeypatch):
    version = "node-v24.1.0-win-x64"
    archive = tmp_path / "source.zip"
    make_archive(archive, {version + "/node.exe": b"fake", version + "/npm.cmd": b"fake npm"})
    content = archive.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    calls = []
    def download(url, destination, limit):
        calls.append(url)
        data = (f"{checksum}  {version}.zip\n".encode() if url.endswith("SHASUMS256.txt") else content)
        destination.write_bytes(data)
        return hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(node, "download", download)
    monkeypatch.setattr(node, "os", NS(name="nt", environ={"PROCESSOR_ARCHITECTURE": "AMD64"}))
    project = tmp_path / "project"
    result = node.install_node(project, lambda _: None)
    assert result == project / ".local/node/node.exe"
    assert result.read_bytes() == b"fake"
    assert node.install_node(project, lambda _: None) == result
    assert len(calls) == 2
    assert not list((project / ".local").glob("node-install-*"))


def test_hash_mismatch_never_installs(tmp_path, monkeypatch):
    def download(url, destination, limit):
        destination.write_bytes(("a" * 64 + "  node-v24.1.0-win-x64.zip\n").encode())
        return "b" * 64
    monkeypatch.setattr(node, "download", download)
    monkeypatch.setattr(node, "os", NS(name="nt", environ={"PROCESSOR_ARCHITECTURE": "AMD64"}))
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        node.install_node(tmp_path, lambda _: None)
    assert not (tmp_path / ".local/node").exists()


@pytest.mark.parametrize("name", ["../escape.exe", "node/../../escape.exe", "C:/escape.exe", "node/dir\\escape.exe"])
def test_unsafe_zip_rejected_before_extraction(tmp_path, name):
    archive = tmp_path / "bad.zip"
    make_archive(archive, {name: b"bad"})
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="Unsafe"):
        node.extract(archive, destination, "node")
    assert not list(destination.iterdir())
