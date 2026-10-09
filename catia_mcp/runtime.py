"""Session-local identity and conservative write bookkeeping (not a COM transaction).

This module is used only on the server's single COM worker thread. Live COM
objects must never leave that thread. Revisions detect our writes, not edits
made by CATIA's UI or another Automation client.
"""
from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Any


class CADOperationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def same_object(left: Any, right: Any) -> bool:
    if left is right:
        return True
    try:
        return bool(left._oleobj_ == right._oleobj_)
    except Exception:
        return False


@dataclass
class ObjectRecord:
    value: Any
    kind: str
    document_id: str
    reference: Any = None
    revision: int | None = None
    selection_index: int | None = None


class SessionState:
    def __init__(self, connection):
        self.connection = connection
        self.documents: dict[str, Any] = {}
        self.objects: dict[str, ObjectRecord] = {}
        self.revisions: dict[str, int] = {}
        self.bound_document: str | None = None
        self.requests: dict[str, tuple[str, Any]] = {}
        self.reconciliation_required = False
        self.created: list[str] = []
        self.modified: list[str] = []
        self.updated = False
        self.mutation_started = False

    def document_id(self, document=None) -> str:
        document = document if document is not None else self.connection.active_document
        for key, value in self.documents.items():
            if same_object(value, document):
                return key
        key = "doc_" + uuid.uuid4().hex
        self.documents[key] = document
        self.revisions[key] = 0
        return key

    def bind(self) -> dict:
        key = self.document_id()
        self.bound_document = key
        self.reconciliation_required = False
        return self.context(key)

    def context(self, key=None) -> dict:
        key = key or self.bound_document
        return {"document_id": key, "revision": self.revisions.get(key, 0),
                "revision_scope": "server-local; external edits are not detected",
                "reconciliation_required": self.reconciliation_required}

    def assert_document(self, requested=None, revision=None):
        current = self.document_id()
        expected = requested or self.bound_document
        if expected is None or current != expected:
            raise CADOperationError("DOCUMENT_MISMATCH",
                                    "Read model state and confirm the target document before writing")
        if revision is not None and revision != self.revisions[current]:
            raise CADOperationError("STALE_REFERENCE", "Revision changed; reread model state")
        if self.reconciliation_required:
            raise CADOperationError("PARTIAL_MUTATION", "Previous write failed; inspect model state before another write")
        self.bound_document = current
        return current

    def register(self, value, kind, *, reference=None, topology=False,
                 selection_index=None) -> str:
        doc = self.document_id()
        if not topology:
            for key, record in self.objects.items():
                if record.document_id == doc and record.kind == kind and same_object(record.value, value):
                    return key
        key = "obj_" + uuid.uuid4().hex
        self.objects[key] = ObjectRecord(value, kind, doc, reference,
                                         self.revisions[doc] if topology else None,
                                         selection_index)
        return key

    def resolve(self, handle, kinds=None) -> ObjectRecord:
        record = self.objects.get(handle)
        if record is None:
            raise CADOperationError("STALE_REFERENCE", "Unknown or invalidated handle; reread objects/selection")
        if record.document_id != self.document_id():
            raise CADOperationError("DOCUMENT_MISMATCH", "Handle belongs to another document")
        if kinds and record.kind not in kinds:
            raise CADOperationError("WRONG_GEOMETRY_TYPE", f"Expected {sorted(kinds)}, got {record.kind}")
        try:
            record.value.Name
        except Exception as exc:
            raise CADOperationError("STALE_REFERENCE", "Stored object is no longer accessible; reread model state") from exc
        if record.revision is not None:
            if record.revision != self.revisions[record.document_id]:
                raise CADOperationError("STALE_REFERENCE", "Topology changed; select again")
            # A selection snapshot is not a persistent BRep address. Compare the
            # actual current Reference; never substitute SelectedElement.Value.
            selection = self.connection.active_document.Selection
            try:
                current = selection.Item2(record.selection_index).Reference
            except Exception as exc:
                raise CADOperationError("STALE_REFERENCE", "Selection no longer available") from exc
            if not same_object(current, record.reference):
                raise CADOperationError("STALE_REFERENCE", "Exact selection reference cannot be revalidated; select again")
        return record

    def reference(self, handle, kinds=None):
        record = self.resolve(handle, kinds)
        if record.reference is not None:
            return record.reference
        return self.connection.get_active_part().CreateReferenceFromObject(record.value)

    def mark_created(self, value, kind):
        self.mutation_started = True
        handle = self.register(value, kind)
        if handle not in self.created:
            self.created.append(handle)
        return handle

    def invalidate_topology(self):
        self.objects = {k: v for k, v in self.objects.items() if v.revision is None}

    def finish_write(self, key):
        self.revisions[key] += 1
        self.invalidate_topology()


def error_details(exc, operation):
    cause = exc
    while cause.__cause__ is not None:
        cause = cause.__cause__
    return {"code": getattr(exc, "code", "INVALID_ARGUMENT" if isinstance(exc, ValueError) else "COM_ERROR"),
            "message": str(exc), "operation": operation,
            "hresult": getattr(cause, "hresult", None),
            "excepinfo": getattr(cause, "excepinfo", None)}
