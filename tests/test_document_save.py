"""Disk/COM doubles: native Windows Save/SaveAs behavior is not established here."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.document_save import output_path
from catia_mcp.server import CATIAMCPServer


@pytest.fixture
def saver():
    server = CATIAMCPServer()
    doc = NS(Name="Part1.CATPart", FullName="Part1.CATPart", Saved=False, ReadOnly=False,
             Part=NS(Name="Part1"))
    documents = [doc]
    app = NS(Caption="Mock", ActiveDocument=doc,
             Documents=NS(Count=1, Item=lambda i: documents[i-1]))
    server.connection.app = app
    server.session.bind()
    def save_as(path):
        Path(path).write_bytes(b"mock CATIA file")
        doc.FullName, doc.Saved = path, True
        doc.Name = Path(path).name
    doc.SaveAs = Mock(side_effect=save_as)
    doc.Save = Mock(side_effect=lambda: save_as(doc.FullName))
    yield server, doc, app, documents
    server.worker.shutdown()


def call(server, path, request="save-1", **kwargs):
    return server._execute_serial("catia_save_document", {"file_path": str(path), "request_id": request, **kwargs})


@pytest.mark.parametrize("kind,interface", [("CATPart", "Part"), ("CATProduct", "Product"), ("CATDrawing", "Sheets")])
def test_first_save_and_in_place_save_verify_disk_and_are_deduplicated(saver, tmp_path, kind, interface):
    server, doc, _, _ = saver
    del doc.Part
    setattr(doc, interface, NS())
    doc.FullName = "Untitled." + kind
    path = tmp_path / "new folder" / "Кронштейн R25 (01)"
    first = call(server, path, create_directories=True)
    assert first["ok"] and first["method"] == "SaveAs" and first["save_verified"]
    actual = path.with_suffix("." + kind)
    assert actual.is_file() and first["bytes"] == len(actual.read_bytes())
    assert first["file_name"] == first["document_name"] == actual.name
    assert call(server, path, create_directories=True)["replayed"]
    doc.SaveAs.assert_called_once_with(str(actual))
    doc.Saved = False
    second = call(server, actual, "save-2", allow_overwrite=True)
    assert second["ok"] and second["method"] == "Save" and second["overwrote_existing"]
    doc.Save.assert_called_once_with()


def test_save_preflight_preserves_files_and_does_not_mark_cad_partial(saver, tmp_path):
    server, doc, app, docs = saver
    existing = tmp_path / "Existing.CATPart"
    existing.write_bytes(b"user data")
    cases = [(existing, {}, "OVERWRITE_NOT_ALLOWED"),
             (tmp_path / "missing" / "new.CATPart", {}, "DIRECTORY_NOT_FOUND"),
             (tmp_path / "wrong.CATDrawing", {}, "WRONG_FILE_TYPE"),
             ("relative.CATPart", {}, "INVALID_PATH")]
    for i, (path, args, code) in enumerate(cases):
        result = call(server, path, str(i), **args)
        assert result["code"] == code and result["status"] == "failed"
        assert not server.session.reconciliation_required
    other = NS(FullName=str(existing))
    docs.append(other)
    app.Documents.Count = 2
    assert call(server, existing, "other", allow_overwrite=True)["code"] == "TARGET_DOCUMENT_OPEN"
    docs.pop()
    app.Documents.Count = 1
    doc.FullName, doc.ReadOnly = str(existing), True
    assert call(server, existing, "readonly", allow_overwrite=True)["code"] == "DOCUMENT_READ_ONLY"
    server.sketcher_tools._active_sketch = NS()
    assert call(server, tmp_path / "New.CATPart", "sketch")["code"] == "SKETCH_OPEN"
    assert existing.read_bytes() == b"user data"
    doc.SaveAs.assert_not_called()
    doc.Save.assert_not_called()
    assert not server.session.reconciliation_required


@pytest.mark.parametrize("failure", ["com", "missing_file", "wrong_path", "dirty"])
def test_save_failure_is_not_success_and_is_never_retried(saver, tmp_path, failure):
    server, doc, _, _ = saver
    path = tmp_path / "Result.CATPart"
    def bad_save(output):
        if failure == "com":
            raise RuntimeError("SaveAs failed")
        doc.FullName = output if failure != "wrong_path" else str(tmp_path / "Elsewhere.CATPart")
        doc.Saved = failure != "dirty"
        if failure != "missing_file":
            path.write_bytes(b"partial or completed file")
    doc.SaveAs.side_effect = bad_save
    first = call(server, path)
    assert not first["ok"] and first["status"] == "partial_failure"
    assert first["code"] == ("SAVE_FAILED" if failure == "com" else "SAVE_VERIFICATION_FAILED")
    assert server.session.reconciliation_required
    replay = call(server, path)
    assert replay["replayed"] and not replay["ok"]
    doc.SaveAs.assert_called_once()


def test_windows_invalid_names_are_rejected_before_com(tmp_path):
    for name in ("CON.CATPart", "bad?.CATPart", "bad .", "control\n.CATPart", "NUL", "LPT1.any"):
        with pytest.raises(Exception) as error:
            output_path(str(tmp_path / name), "CATPart")
        assert error.value.code == "INVALID_PATH"
