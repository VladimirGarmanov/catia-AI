"""Local, bounded feature-request journal. No COM, UI input or network telemetry."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from catia_mcp.runtime import CADOperationError


class ToolGapJournal:
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, path=None):
        directory = Path(os.environ.get("CATIA_AI_DATA_DIR", str(Path.cwd() / ".local")))
        self.path = Path(path) if path else directory / "missing_tools.jsonl"

    def record(self, *, tool_name, reason, request_id, source="agent_report", failed_tool=None,
               error_code=None, outcome="not_attempted", action_kind=None, ui_executed=False):
        if ui_executed is not None and not isinstance(ui_executed, bool):
            raise CADOperationError("INVALID_ARGUMENT", "ui_executed must be boolean or unknown/null")
        payload = dict(tool_name=tool_name, reason=reason, request_id=request_id, source=source,
                       failed_tool=failed_tool, error_code=error_code, outcome=outcome,
                       action_kind=action_kind)
        limits = {"tool_name": 160, "reason": 1000, "request_id": 160, "source": 40,
                  "failed_tool": 160, "error_code": 80, "outcome": 80, "action_kind": 40}
        for key, value in payload.items():
            if value is None and key in {"failed_tool", "error_code", "action_kind"}:
                continue
            if not isinstance(value, str) or not value.strip() or len(value) > limits[key]:
                raise CADOperationError("INVALID_ARGUMENT", f"Invalid tool-gap {key}")
        payload["ui_executed"] = ui_executed
        # A separate prefix distinguishes explicit reports from UI calls.
        identity = (source, request_id)
        lock = self.path.with_suffix(".lock")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise CADOperationError("TOOL_GAP_LOG_BUSY", "Journal is locked; no record was claimed. If a process crashed, inspect its lock before removing it") from exc
        except OSError as exc:
            raise CADOperationError("TOOL_GAP_LOG_FAILED", "Cannot open the local journal folder/lock; no record was claimed") from exc
        try:
            os.close(descriptor)
            if self.path.exists():
                if self.path.stat().st_size > self.MAX_BYTES:
                    raise CADOperationError("TOOL_GAP_LOG_FULL", "Journal reached 8 MB; review it before collecting more events")
                with self.path.open(encoding="utf-8") as stream:
                    for line in stream:
                        row = json.loads(line)
                        if (row["source"], row["request_id"]) == identity:
                            if any(row.get(key) != value for key, value in payload.items()):
                                raise CADOperationError("INVALID_ARGUMENT", "Tool-gap request_id reused with different content")
                            return self._result(row, replayed=True)
            row = {"schema_version": 1, "event_id": uuid.uuid4().hex,
                   "timestamp_utc": datetime.now(timezone.utc).isoformat(), **payload}
            data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
            size = self.path.stat().st_size if self.path.exists() else 0
            if size + len(data) > self.MAX_BYTES:
                raise CADOperationError("TOOL_GAP_LOG_FULL", "Journal reached 8 MB; no new record written")
            with self.path.open("ab") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return self._result(row, replayed=False)
        except (ValueError, KeyError, TypeError) as exc:
            raise CADOperationError("TOOL_GAP_LOG_INVALID", "Existing journal is malformed; no entries were discarded") from exc
        except OSError as exc:
            raise CADOperationError("TOOL_GAP_LOG_FAILED", "Journal I/O failed; check the file before repeating the report") from exc
        finally:
            lock.unlink(missing_ok=True)

    def _result(self, row, *, replayed):
        return {"ok": True, "status": "recorded", "event_id": row["event_id"],
                "file_path": str(self.path.resolve()), "tool_name": row["tool_name"],
                "replayed": replayed, "cad_changed": False, "ui_executed": row["ui_executed"]}
