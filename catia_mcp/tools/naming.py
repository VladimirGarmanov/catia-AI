"""Rename exact whole model objects, not files, topology, or arbitrary COM objects.

CAA AnyObject.Name is inherited by many non-model objects too. A handle alone
is therefore insufficient: locate its current model collection before writing.
Naming is metadata-only; no Update, sketch close/open, selection, or Save occurs.
"""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.domain_support import members, verify_equal
from catia_mcp.tools.engineering import geometry_kind


PART_COLLECTIONS = (
    ("Bodies", "body"), ("HybridBodies", "geoset"),
    ("OrderedGeometricalSets", "ordered_geoset"),
    ("Relations", "relation"), ("AxisSystems", "axis_system"),
    ("Parameters", "parameter"),
)
PART_CHILDREN = {
    "body": (("Shapes", "feature"), ("Sketches", "sketch"),
             ("HybridShapes", "geometry"), ("HybridBodies", "geoset"),
             ("OrderedGeometricalSets", "ordered_geoset")),
    "geoset": (("HybridShapes", "geometry"), ("HybridSketches", "sketch"),
               ("HybridBodies", "geoset")),
    "ordered_geoset": (("HybridShapes", "geometry"), ("Sketches", "sketch"),
                       ("OrderedGeometricalSets", "ordered_geoset")),
    "sketch": (("GeometricElements", "sketch_geometry"), ("Constraints", "constraint")),
}
DRAWING_COLLECTIONS = (
    ("Texts", "drawing_text"), ("Tables", "drawing_table"),
    ("Dimensions", "drawing_dimension"), ("GDTs", "drawing_gdt"),
    ("GeometricElements", "drawing_geometry"),
)


def find_part_collection(part, target):
    remaining = 20000
    unavailable = []

    def search(owner, specifications, depth=0):
        nonlocal remaining
        if depth > 32:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Part tree exceeds rename traversal depth")
        for attribute, kind in specifications:
            try:
                collection = getattr(owner, attribute)
                count = int(collection.Count)
            except Exception as exc:
                unavailable.append(f"{attribute}: {exc}")
                continue  # Optional collections vary between CATIA container types.
            for index in range(1, count + 1):
                remaining -= 1
                if remaining < 0:
                    raise CADOperationError("CAPABILITY_UNAVAILABLE", "Part tree exceeds rename traversal limit")
                obj = collection.Item(index)
                if same_object(obj, target):
                    if kind == "sketch_geometry" and geometry_kind(obj) not in {
                        "point2d", "line2d", "circle2d", "ellipse2d", "curve",
                    }:
                        raise CADOperationError("UNSUPPORTED_OPERATION", "Built-in sketch axes/unknown geometry cannot be renamed")
                    return collection, kind
                nested = search(obj, PART_CHILDREN[kind], depth + 1) if kind in PART_CHILDREN else None
                if nested:
                    return nested
        return None

    found = search(part, PART_COLLECTIONS)
    if not found:
        detail = "; some collections were unavailable: " + "; ".join(unavailable[:3]) if unavailable else ""
        raise CADOperationError("STALE_REFERENCE", "Object is not in a supported current Part collection. Reread catia_list_objects/catia_domain_objects" + detail)
    return found


def find_product_collection(root, target):
    if same_object(root, target):
        raise CADOperationError("UNSUPPORTED_OPERATION", "Root Product naming uses PartNumber: use catia_assembly_operation mode=metadata. This tool renames component instance Name")
    # Only immediate children: nested occurrences/publications may belong to an external document.
    for getter, kind in ((lambda: root.Products, "product"),
                         (lambda: root.Connections("CATIAConstraints"), "constraint"),
                         (lambda: root.Publications, "publication")):
        try:
            collection = getter()
            collection.Count
        except Exception:
            continue
        if any(same_object(value, target) for _, value in members(collection)):
            return collection, kind
    raise CADOperationError("STALE_REFERENCE", "Object is not an immediate occurrence, constraint or publication of the active root Product")


def find_drawing_collection(drawing, target):
    for _, sheet in members(drawing.Sheets):
        if same_object(sheet, target):
            return drawing.Sheets, "sheet"
        for _, view in members(sheet.Views):
            if same_object(view, target):
                return sheet.Views, "view"
            for attribute, kind in DRAWING_COLLECTIONS:
                try:
                    collection = getattr(view, attribute)
                    collection.Count
                except Exception:
                    continue  # E.g. an unavailable GDT collection must not block Texts.
                if any(same_object(value, target) for _, value in members(collection)):
                    if kind == "drawing_geometry" and geometry_kind(target) not in {
                        "point2d", "line2d", "circle2d", "ellipse2d", "curve",
                    }:
                        raise CADOperationError("UNSUPPORTED_OPERATION", "Only explicit drawing primitives can be renamed; built-in axes/projection topology are excluded")
                    return collection, kind
    raise CADOperationError("STALE_REFERENCE", "Object no longer belongs to a supported collection in the active drawing")


def rename_object(engineering, args):
    state, conn = engineering.state, engineering.conn
    name = args["new_name"]
    if not isinstance(name, str) or not name.strip() or name != name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise CADOperationError("INVALID_ARGUMENT", "Name must be nonblank, without surrounding whitespace or control characters")
    record = state.resolve(args["handle"])
    if record.reference is not None or record.revision is not None:
        raise CADOperationError("UNSUPPORTED_OPERATION", "Use a whole-object tree handle from catia_list_objects/catia_domain_objects, not a selection/topology handle. A face Value may be its parent feature")
    obj, doc = record.value, conn.active_document
    doc_type = str(doc.Name).lower()
    if doc_type.endswith(".catpart"):
        part = conn.get_active_part()
        collection, kind = find_part_collection(part, obj)
    elif doc_type.endswith(".catproduct"):
        collection, kind = find_product_collection(doc.Product, obj)
    elif doc_type.endswith(".catdrawing"):
        collection, kind = find_drawing_collection(doc, obj)
    else:
        raise CADOperationError("WRONG_DOCUMENT_TYPE", "Rename supports CATPart, CATProduct and CATDrawing objects")

    before = str(obj.Name)
    if args.get("expected_name") is not None and before != args["expected_name"]:
        raise CADOperationError("STALE_REFERENCE", f"Object name changed: expected {args['expected_name']!r}, found {before!r}")
    if kind == "parameter":
        if not obj.IsTrueParameter or obj.ReadOnly or not same_object(obj.Context, part):
            raise CADOperationError("UNSUPPORTED_OPERATION", "Parameter must be writable and owned by this Part")
        if "local:" in name.casefold():
            raise CADOperationError("INVALID_ARGUMENT", "Parameter naming uses a global name; Local: prefixes are not accepted")
    for _, sibling in members(collection):
        if not same_object(sibling, obj) and str(sibling.Name).casefold() == name.casefold():
            raise CADOperationError("DUPLICATE_NAME", "Another object in this collection already has that name")
    method = "Parameter.Rename (global name)" if kind == "parameter" else "AnyObject.Name"
    result = {"ok": True, "handle": args["handle"], "kind": kind,
              "old_name": before, "new_name": before, "changed": False,
              "method": method, "metadata_only": True, "updated": False,
              "update_required": False, "saved": False,
              "note": "Name readback only; no geometry Update or sketch edition change. External name-based scripts may need adjustment"}
    if before == name:
        return result
    state.mutation_started = True
    if args["handle"] not in state.modified:
        state.modified.append(args["handle"])
    try:
        if kind == "parameter":
            obj.Rename(name)
        else:
            obj.Name = name
        actual = str(obj.Name)
    except Exception as exc:
        raise CADOperationError("RENAME_FAILED", f"CATIA could not rename/read {before!r} as {name!r}: {exc}. Inspect before retrying; no rollback was attempted") from exc
    verify_equal(actual, name, "Object name")
    result.update(new_name=actual, changed=True)
    if kind == "view":
        result["note"] += "; DrawingView.Name changes its prefix, not the full prefix/identifier/suffix label"
    if kind == "drawing_text":
        result["note"] += "; the displayed Text content is unchanged"
    return result
