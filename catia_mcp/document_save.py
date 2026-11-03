"""Native Document.Save/SaveAs with explicit paths and observable postconditions.

CAA InfInterfaces/Document defines Save(), SaveAs(fileName), FullName and Saved.
Saved is a dirty-state flag, not proof of a disk file or valid geometry.
"""
import os
from pathlib import Path
import re

from catia_mcp.runtime import CADOperationError, same_object


def same_path(left, right):
    return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))


def document_kind(document):
    for kind, member in (("CATPart", "Part"), ("CATDrawing", "Sheets"), ("CATProduct", "Product")):
        try:
            if getattr(document, member) is not None:
                return kind
        except Exception:
            continue
    raise CADOperationError("WRONG_DOCUMENT_TYPE", "Save supports CATPart, CATProduct and CATDrawing documents")


def output_path(value, kind):
    if not isinstance(value, str) or not value.strip():
        raise CADOperationError("INVALID_ARGUMENT", "An explicit absolute file_path is required")
    if value.endswith(("/", "\\")):
        raise CADOperationError("INVALID_PATH", "file_path must include a filename, not end with a separator")
    path = Path(value)
    if not path.is_absolute():
        raise CADOperationError("INVALID_PATH", "Use a full absolute path, not a relative path, ~ or an environment-variable placeholder")
    # Enforce Windows filename rules on every platform so offline tests cover
    # the native failure before CATIA can open an error dialog.
    for component in path.parts[1:]:
        if (component in {".", ".."} or component.endswith((" ", "."))
                or any(ord(c) < 32 or c in '<>:"|?*' for c in component)
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", component)):
            raise CADOperationError("INVALID_PATH", f"Invalid Windows path component: {component!r}")
    if not path.name:
        raise CADOperationError("INVALID_PATH", "file_path must include a filename")
    if not path.suffix:
        path = path.with_suffix("." + kind)
    elif path.suffix.casefold() != "." + kind.casefold():
        raise CADOperationError("WRONG_FILE_TYPE", f"A {kind} must use .{kind}; use catia_export for other formats")
    return path


def save_document(connection, file_path, *, allow_overwrite=False, create_directories=False):
    document = connection.active_document
    kind = document_kind(document)
    target = output_path(file_path, kind)
    if target.exists() and not target.is_file():
        raise CADOperationError("INVALID_PATH", "Output path is a directory or non-regular file")
    existed = target.is_file()
    if existed and not allow_overwrite:
        raise CADOperationError("OVERWRITE_NOT_ALLOWED", "File already exists; pass allow_overwrite=true only after explicit overwrite instruction")
    if not target.parent.is_dir() and not create_directories:
        raise CADOperationError("DIRECTORY_NOT_FOUND", "Output folder does not exist; choose an existing folder or explicitly set create_directories=true")
    try:
        current_path = str(document.FullName)
        documents = connection.documents
        count = int(documents.Count)
        if not 1 <= count <= 500:
            raise ValueError("Cannot validate the open-document collection (expected 1..500)")
        current_is_open = False
        for index in range(1, count + 1):
            opened = documents.Item(index)
            if same_object(opened, document):
                current_is_open = True
                continue
            other_path = str(opened.FullName)
            if os.path.isabs(other_path) and same_path(other_path, target):
                raise CADOperationError("TARGET_DOCUMENT_OPEN", "Output belongs to another open document; choose another path")
        if not current_is_open:
            raise CADOperationError("DOCUMENT_MISMATCH", "Active document is no longer in the open-document collection")
        in_place = os.path.isabs(current_path) and same_path(current_path, target)
        if in_place and bool(document.ReadOnly):
            raise CADOperationError("DOCUMENT_READ_ONLY", "Current document is read-only; choose a new path for SaveAs")
    except CADOperationError:
        raise
    except Exception as exc:
        raise CADOperationError("DOCUMENT_STATE_UNAVAILABLE", f"Cannot validate save target: {exc}") from exc
    if not same_object(connection.active_document, document):
        raise CADOperationError("DOCUMENT_MISMATCH", "Active document changed before saving")
    if create_directories:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CADOperationError("DIRECTORY_CREATE_FAILED", str(exc)) from exc
    if not allow_overwrite and target.exists():
        raise CADOperationError("OVERWRITE_NOT_ALLOWED", "Output appeared before SaveAs; no file was replaced")
    if not same_object(connection.active_document, document):
        raise CADOperationError("DOCUMENT_MISMATCH", "Active document changed before saving")
    method = "Save" if in_place else "SaveAs"
    state = getattr(connection, "session", None)
    if state is not None:
        state.mutation_started = True
    try:
        document.Save() if in_place else document.SaveAs(str(target))
    except Exception as exc:
        raise CADOperationError("SAVE_FAILED", f"{method} failed for {target}: {exc}. Disk/model state may have changed; inspect before retrying") from exc
    try:
        actual_path = str(document.FullName)
        saved = bool(document.Saved)
        size = target.stat().st_size if target.is_file() else 0
        if not same_object(connection.active_document, document):
            raise ValueError("Active document changed during save")
        if not os.path.isabs(actual_path) or not same_path(actual_path, target):
            raise ValueError(f"CATIA FullName is {actual_path!r}, not the requested output")
        if not saved or size <= 0:
            raise ValueError(f"Saved={saved}, output size={size}; save was not confirmed")
    except Exception as exc:
        raise CADOperationError("SAVE_VERIFICATION_FAILED", f"{method} returned, but verification failed: {exc}. Inspect {target}; do not repeat automatically") from exc
    names, unavailable = {}, {}
    for label, getter in (("document_name", lambda: document.Name),
                          ("model_name", lambda: document.Part.Name if kind == "CATPart" else document.Product.Name if kind == "CATProduct" else None)):
        try:
            value = getter()
            names[label] = str(value) if value is not None else None
        except Exception as exc:
            names[label] = None
            unavailable[label] = str(exc)
    return {"ok": True, "method": method, "requested_path": file_path,
            "file_path": str(target), "file_name": target.name,
            "document_full_name": actual_path, **names, "unavailable": unavailable,
            "document_type": kind, "saved": saved, "file_exists": True,
            "bytes": size, "overwrote_existing": existed, "save_verified": True,
            "warnings": ["Only the active document was explicitly saved. Referenced assembly/drawing source files require their own save instructions.",
                         "File presence and Saved do not validate geometry or the portability of external links."]}
