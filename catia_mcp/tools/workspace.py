"""Bounded multi-document discovery and explicit serialized context switching.

CAA Document.Activate changes the active window, not the stored geometry.
Source: InfInterfaces/interface_Document_14894.htm#Activate in the CAA cache.
No save, close, duplicate or automatic switch is performed by discovery.
"""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, tool


class WorkspaceTools:
    strict_writes = True

    def __init__(self, engineering):
        self.engineering = engineering

    @property
    def conn(self):
        return self.engineering.conn

    @property
    def state(self):
        return self.engineering.state

    def get_tool_definitions(self):
        return [
            tool("catia_get_workspace_state", "Read a bounded catalog of open CATIA documents with session-local IDs, active identity, native collection counts and unavailable-field errors. Does not activate, bind, save or update any document. Read catia_get_model_state for detailed active geometry before writes.", {
                "max_documents": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            }, readonly=True),
            tool("catia_activate_document", "Explicitly activate one already-open document by its workspace document ID. document_id/expected_revision describe the currently bound SOURCE document; target_document_id identifies the destination. Rejects a server-bound open sketch. A real switch clears context: call catia_get_model_state afterward before any write. No save/close/update. Manual unadopted UI sketch edition cannot be detected; the user must close it first. This changes CATIA focus and has no rollback.", {
                "target_document_id": HANDLE,
            }, ["target_document_id"]),
        ]

    def execute(self, name, args):
        if name == "catia_get_workspace_state":
            return self.inspect(args)
        if name == "catia_activate_document":
            return self.activate(args)
        raise CADOperationError("INVALID_ARGUMENT", "Unknown workspace operation")

    def _summary(self, document, active):
        key = self.state.document_id(document)
        row = {"document_id": key, "active": same_object(document, active),
               "revision": self.state.revisions[key], "type": "Unknown", "counts": {}, "unavailable": {}}
        for field, attr, cast in (("name", "Name", str), ("path", "FullName", str), ("saved", "Saved", bool)):
            try:
                row[field] = cast(getattr(document, attr))
            except Exception as exc:
                row[field] = None
                row["unavailable"][field] = str(exc)
        # Probe document interfaces, not mutable file labels, to classify it.
        for kind, attr, counts in (("CATPart", "Part", {"bodies": "Bodies", "parameters": "Parameters"}),
                                   ("CATDrawing", "Sheets", {}),
                                   ("CATProduct", "Product", {"components": "Products"})):
            try:
                owner = getattr(document, attr)
            except Exception:
                continue
            row["type"] = kind
            if kind == "CATDrawing":
                try:
                    row["counts"]["sheets"] = int(owner.Count)
                except Exception as exc:
                    row["unavailable"]["sheets"] = str(exc)
            for label, collection in counts.items():
                try:
                    row["counts"][label] = int(getattr(owner, collection).Count)
                except Exception as exc:
                    row["unavailable"][label] = str(exc)
            break
        if row["type"] == "Unknown":
            row["unavailable"]["type"] = "No supported Part, Drawing or Product interface could be read"
        try:
            row["selection_count"] = int(document.Selection.Count2)
        except Exception as exc:
            row["selection_count"] = None
            row["unavailable"]["selection_count"] = str(exc)
        return row

    def inspect(self, args):
        limit = args.get("max_documents", 50)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise CADOperationError("INVALID_ARGUMENT", "max_documents must be an integer in 1..500")
        documents = self.conn.documents
        total = int(documents.Count)
        active = self.conn.active_document if total else None
        rows, unavailable = [], []
        for index in range(1, min(total, limit) + 1):
            try:
                rows.append(self._summary(documents.Item(index), active))
            except Exception as exc:
                unavailable.append({"position": index, "error": str(exc)})
        if int(documents.Count) != total:
            raise CADOperationError("SESSION_STATE_UNKNOWN", "Open document collection changed during inspection; reread workspace")
        if active is not None and not same_object(self.conn.active_document, active):
            raise CADOperationError("SESSION_STATE_UNKNOWN", "Active document changed during inspection; reread workspace")
        return {"ok": True, "documents": rows, "total_documents": total,
                "active_document_id": self.state.document_id(active) if active is not None else None,
                "bound_document_id": self.state.bound_document,
                "truncated": total > limit, "unavailable": unavailable,
                "revision_scope": "server-local; external edits are not detected",
                "warning": "Inventory is not geometry verification or authorization to modify every listed document"}

    def activate(self, args):
        state = self.state
        if state.bound_document != args["document_id"]:
            raise CADOperationError("MODEL_CONTEXT_REQUIRED", "Read the active model state before switching documents")
        source_key = state.assert_document(args["document_id"], args["expected_revision"])
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the bound sketch before switching documents")
        target_key = args["target_document_id"]
        source, target = state.documents[source_key], state.documents.get(target_key)
        if target is None:
            raise CADOperationError("STALE_REFERENCE", "Unknown target document ID; reread workspace")
        documents = self.conn.documents
        count = int(documents.Count)
        if count > 500:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Too many open documents to validate activation safely (limit 500)")
        open_documents = [documents.Item(i) for i in range(1, count + 1)]
        if not all(any(same_object(doc, opened) for opened in open_documents) for doc in (source, target)):
            raise CADOperationError("STALE_REFERENCE", "Source or target document is no longer open; reread workspace")
        if not same_object(self.conn.active_document, source):
            raise CADOperationError("DOCUMENT_MISMATCH", "Active document changed during activation preflight")
        if same_object(source, target):
            return {"ok": True, "activated": False, "active_document_id": source_key,
                    "requires_model_read": False, "geometry_changed": False}
        # Any error from this point means focus may have changed. Never retry or
        # restore the prior window implicitly, and do not advance geometry revisions.
        state.mutation_started = True
        state.invalidate_topology()
        state.bound_document = None
        state.reconciliation_required = True
        target.Activate()
        if not same_object(self.conn.active_document, target):
            raise CADOperationError("POSTCONDITION_FAILED", "Document.Activate did not make the exact target active; inspect before proceeding")
        return {"ok": True, "activated": True, "previous_document_id": source_key,
                "active_document_id": target_key, "requires_model_read": True,
                "geometry_changed": False,
                "next_tool": "catia_get_model_state"}
