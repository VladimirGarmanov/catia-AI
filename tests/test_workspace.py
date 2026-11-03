"""Multi-document orchestration doubles; this is not live Document.Activate proof."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.server import CATIAMCPServer


class Collection:
    def __init__(self, items=()):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


@pytest.fixture
def workspace():
    server = CATIAMCPServer()
    documents = []
    for name in ("Bracket", "Pin"):
        part = NS(Name=name, Bodies=Collection(), HybridBodies=Collection(), Parameters=Collection())
        documents.append(NS(Name=name + ".CATPart", FullName="", Saved=False, Part=part,
                            Selection=NS(Count2=0, Count=0, Item2=lambda _: None)))
    app = NS(Caption="Mock CATIA", Documents=Collection(documents), ActiveDocument=documents[0])
    for document in documents:
        document.Activate = Mock(side_effect=lambda d=document: setattr(app, "ActiveDocument", d))
    server.connection.app = app
    source = server._execute_serial("catia_get_model_state", {})
    assert source["ok"], source
    ids = [server.session.document_id(d) for d in documents]
    args = {"document_id": ids[0], "expected_revision": 0, "request_id": "switch-1",
            "target_document_id": ids[1]}
    yield server, app, documents, ids, args
    server.worker.shutdown()


def test_workspace_reads_multiple_documents_without_focus_or_revision_changes(workspace):
    server, app, documents, ids, _ = workspace
    result = server._execute_serial("catia_get_workspace_state", {})
    assert result["ok"] and result["total_documents"] == 2
    assert [row["document_id"] for row in result["documents"]] == ids
    assert [row["active"] for row in result["documents"]] == [True, False]
    assert result["documents"][1]["counts"] == {"bodies": 0, "parameters": 0}
    assert result["bound_document_id"] == ids[0]
    assert app.ActiveDocument is documents[0]
    for doc in documents:
        doc.Activate.assert_not_called()
    app.Documents.items.extend([
        NS(Name="Assembly.CATProduct", Product=NS(Products=Collection(documents))),
        NS(Name="Sheet.CATDrawing", Sheets=Collection([object()])),
        NS(Name="Materials.CATfct"),
    ])
    five = server._execute_serial("catia_get_workspace_state", {})
    assert five["total_documents"] == 5
    assert [row["type"] for row in five["documents"]] == ["CATPart", "CATPart", "CATProduct", "CATDrawing", "Unknown"]
    assert five["documents"][2]["counts"] == {"components": 2}
    assert five["documents"][3]["counts"] == {"sheets": 1}
    assert five["documents"][4]["unavailable"]["type"]
    limited = server._execute_serial("catia_get_workspace_state", {"max_documents": 1})
    assert len(limited["documents"]) == 1 and limited["truncated"]
    app.Documents.items.clear()
    assert server._execute_serial("catia_get_workspace_state", {})["active_document_id"] is None


def test_activate_is_idempotent_rebinds_only_after_model_read_and_does_not_change_geometry_revision(workspace):
    server, app, documents, ids, args = workspace
    topology = server.session.register(NS(Name="Face"), "face", topology=True, reference=object(), selection_index=1)
    result = server._execute_serial("catia_activate_document", args)
    assert result["ok"] and result["activated"] and result["requires_model_read"]
    assert result["active_document_id"] == ids[1] and app.ActiveDocument is documents[1]
    assert result["geometry_changed"] is False and not result["updated"]
    assert server.session.bound_document is None and server.session.reconciliation_required
    assert topology not in server.session.objects
    assert [server.session.revisions[key] for key in ids] == [0, 0]
    blocked = server._execute_serial("catia_new_part", {"request_id": "no-write-before-read"})
    assert not blocked["ok"] and blocked["code"] == "PARTIAL_MUTATION"
    read = server._execute_serial("catia_get_model_state", {})
    assert read["ok"] and read["session"]["document_id"] == ids[1]
    assert not server.session.reconciliation_required
    replay = server._execute_serial("catia_activate_document", args)
    assert replay["replayed"] and replay["ok"]
    documents[1].Activate.assert_called_once()
    documents[0].Activate.assert_not_called()


@pytest.mark.parametrize("case,code", [
    ("unknown", "STALE_REFERENCE"), ("closed", "STALE_REFERENCE"),
    ("wrong_source", "DOCUMENT_MISMATCH"), ("stale_revision", "STALE_REFERENCE"),
    ("open_sketch", "SKETCH_OPEN"), ("unbound", "MODEL_CONTEXT_REQUIRED"),
])
def test_switch_preflight_failures_do_not_activate_or_mark_partial_failure(workspace, case, code):
    server, app, documents, ids, args = workspace
    if case == "unknown":
        args["target_document_id"] = "foreign-session"
    elif case == "closed":
        app.Documents.items.remove(documents[1])
    elif case == "wrong_source":
        args["document_id"] = ids[1]
    elif case == "stale_revision":
        args["expected_revision"] = 99
    elif case == "open_sketch":
        server.sketcher_tools._active_sketch = NS(Name="Editing")
    else:
        server.session.bound_document = None
    result = server._execute_serial("catia_activate_document", args)
    assert result["code"] == code and result["status"] == "failed"
    assert not server.session.mutation_started
    documents[1].Activate.assert_not_called()


@pytest.mark.parametrize("failure", ["exception_after_switch", "wrong_active_document"])
def test_uncertain_activation_never_rolls_back_or_changes_geometry_revision(workspace, failure):
    server, app, documents, ids, args = workspace
    def bad_activate():
        if failure == "exception_after_switch":
            app.ActiveDocument = documents[1]
            raise RuntimeError("RPC failed after activation")
    documents[1].Activate.side_effect = bad_activate
    result = server._execute_serial("catia_activate_document", args)
    assert not result["ok"] and result["status"] == "partial_failure"
    assert server.session.reconciliation_required and server.session.bound_document is None
    assert [server.session.revisions[key] for key in ids] == [0, 0]
    documents[0].Activate.assert_not_called()
    replay = server._execute_serial("catia_activate_document", args)
    assert replay["replayed"] and not replay["ok"]
    documents[1].Activate.assert_called_once()


def test_already_active_is_a_noop_and_missing_guards_fail(workspace):
    server, _, documents, ids, args = workspace
    args["target_document_id"] = ids[0]
    result = server._execute_serial("catia_activate_document", args)
    assert result["ok"] and not result["activated"] and not result["requires_model_read"]
    assert server.session.bound_document == ids[0] and not server.session.reconciliation_required
    documents[0].Activate.assert_not_called()
    for key in ("document_id", "expected_revision", "request_id"):
        invalid = {k: v for k, v in args.items() if k != key}
        invalid["request_id"] = "schema-" + key if key != "request_id" else None
        assert server._execute_serial("catia_activate_document", invalid)["code"] == "INVALID_ARGUMENT"
