"""Read-only live CATIA selection probe for the later Windows validation.

Run with .venv\\Scripts\\python.exe scripts\\selection_probe.py while CATIA is open.
This never clears the selection or modifies a document. Display names are not IDs.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def optional_text(obj: Any, attribute: str) -> str | None:
    try:
        value = getattr(obj, attribute)
    except Exception:
        return None
    return str(value) if value is not None else None


def inspect_selection(app: Any) -> dict[str, Any]:
    doc = app.ActiveDocument
    selection = doc.Selection
    try:
        count, item_at = selection.Count2, selection.Item2
    except AttributeError:
        count, item_at = selection.Count, selection.Item

    items = []
    for position in range(1, count + 1):
        selected = item_at(position)
        item: dict[str, Any] = {
            "position": position,
            "selection_type": optional_text(selected, "Type"),
        }
        try:
            value = selected.Value
            item["value_name"] = optional_text(value, "Name")
            item["value_type"] = optional_text(value, "Type")
        except Exception as exc:
            item["value_error"] = str(exc)
        try:
            owner = selected.Document
            item["owner_document"] = optional_text(owner, "FullName")
        except Exception as exc:
            item["owner_error"] = str(exc)
        try:
            reference = selected.Reference
            item["reference_available"] = reference is not None
            if reference is not None:
                item["reference_display_name"] = optional_text(
                    reference, "DisplayName"
                )
        except Exception as exc:
            item["reference_available"] = False
            item["reference_error"] = str(exc)
        items.append(item)
    return {
        "document": optional_text(doc, "FullName") or optional_text(doc, "Name"),
        "count": count,
        "items": items,
        "note": (
            "This observes the current selection only. Display names and positions "
            "are not persistent topology identifiers or proof of exact feature targeting."
        ),
    }


def main() -> int:
    try:
        from win32com.client import GetActiveObject

        app = GetActiveObject("CATIA.Application")
        report = inspect_selection(app)
    except Exception as exc:
        print(f"CATIA selection probe failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
