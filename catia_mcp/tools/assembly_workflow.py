"""Typed assembly workflows over CAA Products, Position and Publications.

All writes address immediate occurrences of the bound assembly. Patterns are
explicit instances sharing a reference, not associative CATIA pattern features.
No save, activation, Fix, scripts, implicit constraint suppression or rollback.
"""
import math

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.assembly_management import AssemblyManagementTools
from catia_mcp.tools.domain_support import members, member_index, read_properties, verify_equal
from catia_mcp.tools.engineering import HANDLE, NUMBER, tool
from catia_mcp.tools.operations import BOOL, VECTOR, array, group, unit_vector


READ_TOOLS = frozenset({
    "catia_assembly_component_details", "catia_assembly_bom",
    "catia_assembly_constraint_status", "catia_assembly_get_positions",
})
POSE = array(NUMBER, 12, 12)
NAME = {"type": "string", "minLength": 1, "maxLength": 128}
HANDLES = {**array(HANDLE, 1, 100), "uniqueItems": True}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 2000}
STATUS_LABELS = {
    0: "satisfied", 1: "strongly_not_satisfied", 2: "wrong_orientation_or_side",
    3: "wrong_value", 4: "wrong_geometry_type", 5: "broken",
}
METADATA = {
    "part_number": ("PartNumber", NAME), "revision": ("Revision", {"type": "string"}),
    "definition": ("Definition", {"type": "string"}),
    "nomenclature": ("Nomenclature", {"type": "string"}),
    "description": ("DescriptionRef", {"type": "string"}),
    "source": ("Source", {"enum": ["unknown", "made", "bought"]}),
}


def record_schema(fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def rotate_vector(vector, axis, angle_deg):
    """Right-handed Rodrigues rotation in assembly parent coordinates."""
    u = unit_vector(axis)
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    cross = [u[1]*vector[2]-u[2]*vector[1], u[2]*vector[0]-u[0]*vector[2],
             u[0]*vector[1]-u[1]*vector[0]]
    dot = sum(x*y for x, y in zip(u, vector))
    return [c*vector[i]+s*cross[i]+(1-c)*dot*u[i] for i in range(3)]


def rotated_pose(pose, axis, pivot, angle_deg, rotate_orientation=True):
    result = list(pose)
    offset = [pose[9+i]-pivot[i] for i in range(3)]
    result[9:] = [x+y for x, y in zip(rotate_vector(offset, axis, angle_deg), pivot)]
    if rotate_orientation:
        for start in (0, 3, 6):
            result[start:start+3] = rotate_vector(pose[start:start+3], axis, angle_deg)
    return result


class AssemblyWorkflowTools(AssemblyManagementTools):
    def get_tool_definitions(self):
        return [
            tool("catia_assembly_component_details", "Read a root/occurrence handle, reference metadata, source document and publication handles. No activation, Update or source edits. Missing COM fields are explicit.",
                 {"component_handle": HANDLE, "max_publications": LIMIT}, ["component_handle"], True),
            tool("catia_assembly_bom", "Read structured BOM grouped by actual ReferenceProduct identity, never just PartNumber. leaf counts terminal occurrences; top counts root children; all counts every level. Truncation means quantities are incomplete. No files written.",
                 {"scope": {"enum": ["leaf", "top", "all"]}, "max_occurrences": LIMIT}, readonly=True),
            tool("catia_assembly_constraint_status", "Read root constraints, native broken/unupdated counts and problem handles without Update. Satisfaction does not prove a fully constrained assembly; DOF stays unknown. require_satisfied returns an error for bad, empty or incomplete evidence.",
                 {"max_constraints": LIMIT, "require_satisfied": BOOL}, readonly=True),
            tool("catia_assembly_get_positions", "Read exact immediate-occurrence poses for later explicit restore. Axes are columns, origin in parent-frame mm. This is not a persisted snapshot or an Undo operation.",
                 {"component_handles": HANDLES}, ["component_handles"], True),
            tool("catia_assembly_insert_document", "Insert one reference to an already-open CATPart/CATProduct by workspace document ID using Products.AddComponent. Does not activate or save the source. Unsaved source links are session-only until explicitly saved. Rejects cycles; supply final parent-frame pose and unique instance name.",
                 {"source_document_id": HANDLE, "instance_name": NAME, "axis_components": POSE},
                 ["source_document_id", "instance_name", "axis_components"]),
            tool("catia_assembly_duplicate_component", "Add one immediate occurrence sharing the seed ReferenceProduct. Not an independent file copy; geometry edits affect all instances. No constraints copied. Supply absolute final pose and a new unique instance name.",
                 {"component_handle": HANDLE, "instance_name": NAME, "axis_components": POSE},
                 ["component_handle", "instance_name", "axis_components"]),
            tool("catia_assembly_replace_component", "Replace one immediate occurrence with an already-open document reference. Uses ReplaceProduct with multi-instances=false. Preserves name; optionally preserves parent-frame pose. Verifies sibling references/count and resulting constraint status; broken mates are an error with no automatic rollback.",
                 {"component_handle": HANDLE, "source_document_id": HANDLE, "preserve_position": BOOL},
                 ["component_handle", "source_document_id", "preserve_position"]),
            group("catia_assembly_pattern", "Create explicit shared-reference occurrences from one immediate seed. count includes the unchanged seed (2..50). Not an associative native pattern; no constraints copied. Linear step is parent-frame mm. Circular rotates about an explicit parent-frame axis/pivot; full turns that duplicate the seed are rejected. Created handles are journaled when discoverable; partial failure has no rollback.", {
                "linear": {"step_mm": VECTOR},
                "circular": {"axis": VECTOR, "pivot_mm": VECTOR, "angle_step_deg": NUMBER,
                             "rotate_orientation": BOOL},
            }, {"component_handle": HANDLE, "count": {"type": "integer", "minimum": 2, "maximum": 50},
                "name_prefix": {"type": "string", "minLength": 1, "maxLength": 110}}),
            group("catia_assembly_transform", "Set/translate/rotate multiple immediate occurrences. Preflights all targets and poses before writing, updates once and reads every resulting pose. Rotation uses parent-frame axis and pivot, including orbit of component origins. Returns before/after poses; solver displacement is a failure. No rollback or constraint suppression.", {
                "set_positions": {"positions": array(record_schema({"component_handle": HANDLE, "axis_components": POSE}), 1, 100)},
                "translate": {"component_handles": HANDLES, "translation_mm": VECTOR},
                "rotate": {"component_handles": HANDLES, "axis": VECTOR, "pivot_mm": VECTOR, "angle_deg": NUMBER},
            }),
            tool("catia_assembly_explode", "Apply explicit parent-frame offsets to immediate occurrences for an exploded layout. Changes actual positions, not a scene. Returns original poses for catia_assembly_transform(set_positions) restore. No automatic spacing or constraint suppression; solver returning a component is an error.",
                 {"offsets": array(record_schema({"component_handle": HANDLE, "translation_mm": VECTOR}), 1, 100)}, ["offsets"]),
            tool("catia_assembly_set_metadata", "Edit only the active root Product reference metadata with readback. Does not rename files, edit external references, save or run geometry Update. Supply only fields to change.",
                 {"properties": {"type": "object", "properties": {k: v[1] for k, v in METADATA.items()},
                                 "minProperties": 1, "additionalProperties": False}}, ["properties"]),
            tool("catia_assembly_publication_relay", "Create a new root publication relaying an existing publication of an immediate component. Exact owner/publication handles required. Uses the CAA SetRelay Publications argument; verifies readable valuation identity. Native release behavior needs Windows validation. No external publication changes or replacement.",
                 {"component_handle": HANDLE, "publication_handle": HANDLE, "name": NAME},
                 ["component_handle", "publication_handle", "name"]),
        ]

    def execute(self, name, args):
        if name not in READ_TOOLS and self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the edited sketch before assembly writes")
        handlers = {
            "catia_assembly_component_details": self.details, "catia_assembly_bom": self.bom,
            "catia_assembly_constraint_status": self.constraint_status,
            "catia_assembly_get_positions": self.get_positions,
            "catia_assembly_insert_document": self.insert_document,
            "catia_assembly_duplicate_component": self.duplicate,
            "catia_assembly_replace_component": self.replace,
            "catia_assembly_pattern": self.pattern, "catia_assembly_transform": self.transform,
            "catia_assembly_explode": self.explode, "catia_assembly_set_metadata": self.metadata,
            "catia_assembly_publication_relay": self.relay,
        }
        return handlers[name](args)

    def _children(self, product):
        if int(product.Products.Count) > 2000:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Collection exceeds 2000 occurrences; use a smaller active assembly")
        return [value for _, value in members(product.Products)]

    def _tree(self, limit=2000):
        root = self.product()
        pending = [(child, 1, []) for child in reversed(self._children(root))]
        rows, truncated = [], False
        while pending and len(rows) < limit:
            value, depth, ancestors = pending.pop()
            if any(same_object(value, old) for old in ancestors):
                raise CADOperationError("INVALID_ASSEMBLY", "Occurrence cycle detected")
            children = self._children(value)
            rows.append((value, depth, len(children), ancestors))
            if depth >= 30:
                truncated |= bool(children)
            else:
                pending.extend((child, depth+1, [*ancestors, value]) for child in reversed(children))
        return rows, truncated or bool(pending)

    def _member(self, handle):
        value = self.obj(handle, {"product"})
        root = self.product()
        if same_object(value, root):
            return value
        rows, _ = self._tree()
        if not any(same_object(value, row[0]) for row in rows):
            raise CADOperationError("STALE_REFERENCE", "Occurrence is not in the current bounded assembly tree")
        return value

    def _active(self, document):
        if not same_object(self.conn.active_document, document):
            raise CADOperationError("DOCUMENT_MISMATCH", "Active document changed during assembly operation; inspect the workspace")

    def _bound_document(self):
        document = self.conn.active_document
        if self.state.bound_document != self.state.document_id(document):
            raise CADOperationError("DOCUMENT_MISMATCH", "Active document differs from the bound assembly")
        self.product()  # Verify CATProduct before taking its root interface.
        return document

    def _pose(self, value):
        pose = read_array(value.Position.GetComponents, 12)
        self.validate_pose(pose)
        return pose

    def _targets(self, handles):
        if not handles or len(handles) > 100 or len(handles) != len(set(handles)):
            raise CADOperationError("INVALID_ARGUMENT", "Supply 1..100 distinct occurrence handles")
        result = []
        for handle in handles:
            obj, _ = self.occurrence(handle)
            if any(same_object(obj, old[1]) for old in result):
                raise CADOperationError("INVALID_ARGUMENT", "The same occurrence was supplied more than once")
            result.append((handle, obj, self._pose(obj)))
        return result

    def _names(self, names):
        if len(names) != len(set(names)) or any(not n.strip() or any(ord(c) < 32 for c in n) for n in names):
            raise CADOperationError("INVALID_ARGUMENT", "Instance names must be distinct, nonblank and contain no control characters")
        existing = {str(obj.Name) for obj in self._children(self.product())}
        if existing.intersection(names):
            raise CADOperationError("INVALID_ARGUMENT", "An instance with a requested name already exists")

    def _source(self, identity):
        document = self.state.documents.get(identity)
        opened = self.conn.app.Documents
        if int(opened.Count) > 500:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Too many open documents to validate source")
        if document is None or not any(same_object(document, doc) for _, doc in members(opened)):
            raise CADOperationError("STALE_REFERENCE", "Source document is not open; reread workspace IDs")
        if not str(document.Name).lower().endswith((".catpart", ".catproduct")):
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "Source must be a CATPart or CATProduct")
        reference = document.Product
        root = self.product()
        pending, visited = [reference], []
        while pending:
            obj = pending.pop()
            if same_object(obj, root):
                raise CADOperationError("INVALID_ARGUMENT", "Inserting this reference would create an assembly cycle")
            if any(same_object(obj, old) for old in visited):
                continue
            visited.append(obj)
            if len(visited) > 2000:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", "Source graph too large to check cycles")
            pending.extend(child.ReferenceProduct for child in self._children(obj))
        return reference

    def _capture_new(self, collection, before, kind):
        for _, value in members(collection):
            if not any(same_object(value, old) for old in before):
                self.state.mark_created(value, kind)

    def _add(self, reference, name):
        document = self._bound_document()
        root = document.Product
        before = self._children(root)
        if len(before) >= 2000:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Target assembly occurrence limit reached")
        self.state.mutation_started = True
        try:
            obj = root.Products.AddComponent(reference)
        finally:
            self._active(document)
            self._capture_new(root.Products, before, "product")
        verify_equal(int(root.Products.Count), len(before)+1, "Occurrence count")
        member_index(root.Products, obj)
        if any(same_object(obj, old) for old in before):
            raise CADOperationError("POSTCONDITION_FAILED", "AddComponent returned an existing occurrence")
        handle = self.state.mark_created(obj, "product")
        obj.Name = name
        verify_equal(str(obj.Name), name, "Instance name")
        if not same_object(obj.ReferenceProduct, reference):
            raise CADOperationError("POSTCONDITION_FAILED", "Created occurrence has the wrong reference")
        return handle, obj

    def _apply(self, targets, poses):
        for pose in poses:
            self.validate_pose(pose)
        document = self._bound_document()
        root = document.Product
        for (handle, obj, _), pose in zip(targets, poses):
            self._active(document)
            self.changed(handle)
            obj.Position.SetComponents(tuple(pose))
        self._active(document)
        result = self.update(root)
        self._active(document)
        after = []
        for (handle, obj, _), pose in zip(targets, poses):
            member_index(root.Products, obj)
            actual = self._pose(obj)
            for index, expected in enumerate(pose):
                verify_equal(actual[index], expected, f"Solved pose[{index}]")
            after.append({"component_handle": handle, "axis_components": actual})
        return {**result, "positions": after,
                "before_positions": [{"component_handle": h, "axis_components": p} for h, _, p in targets],
                "position_frame": "parent; axes as columns, translation in mm",
                "constraints_copied": False}

    def details(self, a):
        obj = self._member(a["component_handle"])
        root = self.product()
        reference = obj if same_object(obj, root) else obj.ReferenceProduct
        data = read_properties(reference, {"PartNumber": str, "Revision": str, "Nomenclature": str,
                                          "Definition": str, "DescriptionRef": str, "Source": int})
        source = {}
        try:
            owner = reference.Parent
            source = read_properties(owner, {"Name": str, "FullName": str, "Saved": bool})
            for _, opened in members(self.conn.app.Documents):
                if same_object(owner, opened):
                    source["document_id"] = self.state.document_id(opened)
                    break
        except Exception as exc:
            source["unavailable"] = str(exc)
        publications, limit = [], a.get("max_publications", 100)
        collection = obj.Publications
        for i in range(1, min(int(collection.Count), limit)+1):
            pub = collection.Item(i)
            publications.append({"handle": self.state.register(pub, "publication"), "name": str(pub.Name)})
        return {"ok": True, "component_handle": a["component_handle"], "name": str(obj.Name),
                "reference": data, "source_document": source, "publications": publications,
                "publications_truncated": int(collection.Count) > limit,
                "children_count": int(obj.Products.Count),
                "warning": "Reference metadata is shared across occurrences; unsaved paths are not durable links"}

    def bom(self, a):
        rows, truncated = self._tree(a.get("max_occurrences", 1000))
        scope = a.get("scope", "leaf")
        groups, references = [], []
        for obj, depth, child_count, ancestors in rows:
            if (scope == "leaf" and child_count) or (scope == "top" and depth != 1):
                continue
            reference = obj.ReferenceProduct
            index = next((i for i, value in enumerate(references) if same_object(value, reference)), None)
            if index is None:
                index = len(references)
                references.append(reference)
                groups.append({"reference_handle": self.state.register(reference, "product_reference"),
                               **read_properties(reference, {"PartNumber": str, "Nomenclature": str, "Revision": str}),
                               "quantity": 0, "occurrences": []})
            groups[index]["quantity"] += 1
            groups[index]["occurrences"].append({"handle": self.state.register(obj, "product"),
                "name_path": [str(v.Name) for v in ancestors] + [str(obj.Name)], "depth": depth})
        return {"ok": True, "scope": scope, "items": groups, "truncated": truncated,
                "quantities_complete": not truncated, "visited_occurrences": len(rows),
                "warning": "Names are labels only; distinct references with equal PartNumber remain separate rows"}

    def constraint_status(self, a):
        collection = self.product().Connections("CATIAConstraints")
        total, limit = int(collection.Count), a.get("max_constraints", 500)
        rows = []
        for i in range(1, min(total, limit)+1):
            obj = collection.Item(i)
            data = self.constraint_data(obj)
            rows.append({"handle": self.state.register(obj, "constraint"), **data,
                         "status_label": STATUS_LABELS.get(data["Status"], "unknown")})
        native = read_properties(collection, {"BrokenConstraintsCount": int, "UnUpdatedConstraintsCount": int})
        active = [row for row in rows if row["inactive"] is False]
        problems = [row["handle"] for row in active if row["Status"] not in (None, 0)]
        complete = total <= limit and all(row["inactive"] is not None and
                   (row["inactive"] or row["Status"] in STATUS_LABELS) for row in rows)
        satisfied = None
        if problems or (native["BrokenConstraintsCount"] or 0) > 0:
            satisfied = False
        elif complete and active and native["BrokenConstraintsCount"] == 0 and native["UnUpdatedConstraintsCount"] == 0:
            satisfied = True
        result = {"ok": True, "constraints": rows, "total": total, "native_counts": native,
                  "problem_handles": problems, "truncated": total > limit,
                  "all_active_satisfied": satisfied, "fully_constrained": None, "remaining_dof": None,
                  "warning": "No Update performed; satisfaction is not solver rank or complete assembly restraint"}
        if a.get("require_satisfied") and satisfied is not True:
            result.update(ok=False, code="CONSTRAINTS_NOT_SATISFIED" if satisfied is False else "CONSTRAINT_STATUS_UNVERIFIED")
        return result

    def get_positions(self, a):
        return {"ok": True, "positions": [{"component_handle": h, "axis_components": pose}
                for h, _, pose in self._targets(a["component_handles"])],
                "position_frame": "parent; axes as columns, translation in mm"}

    def _insert(self, reference, a):
        self._names([a["instance_name"]])
        self.validate_pose(a["axis_components"])
        handle, obj = self._add(reference, a["instance_name"])
        # Reading the created pose can fail: its handle is already in the journal.
        result = self._apply([(handle, obj, self._pose(obj))], [a["axis_components"]])
        result.update(handle=handle, shared_reference=True)
        return result

    def insert_document(self, a):
        result = self._insert(self._source(a["source_document_id"]), a)
        result["source_document_id"] = a["source_document_id"]
        result["warning"] = "Source was not saved; save source documents explicitly before relying on disk links"
        return result

    def duplicate(self, a):
        obj, _ = self.occurrence(a["component_handle"])
        self._pose(obj)  # Preflight array binding before creating an instance.
        return self._insert(obj.ReferenceProduct, a)

    def replace(self, a):
        document = self._bound_document()
        root = document.Product
        old, _ = self.occurrence(a["component_handle"])
        reference = self._source(a["source_document_id"])
        if same_object(old.ReferenceProduct, reference):
            raise CADOperationError("INVALID_ARGUMENT", "Occurrence already uses this reference")
        before = self._children(root)
        siblings = [(v, v.ReferenceProduct) for v in before if not same_object(v, old)]
        pose = self._pose(old) if a["preserve_position"] else None
        name = str(old.Name)
        self.changed(a["component_handle"])
        try:
            new = root.Products.ReplaceProduct(old, reference, False)
        finally:
            self._active(document)
            self._capture_new(root.Products, before, "product")
        member_index(root.Products, new)
        handle = a["component_handle"] if same_object(old, new) else self.state.mark_created(new, "product")
        if not same_object(old, new):
            self.state.objects.pop(a["component_handle"], None)
        new.Name = name
        if pose is not None:
            new.Position.SetComponents(tuple(pose))
        result = self.update(root)
        self._active(document)
        verify_equal(int(root.Products.Count), len(before), "Replacement occurrence count")
        verify_equal(str(new.Name), name, "Replacement instance name")
        if not same_object(new.ReferenceProduct, reference):
            raise CADOperationError("POSTCONDITION_FAILED", "Replacement reference differs from requested source")
        for sibling, original in siblings:
            member_index(root.Products, sibling)
            if not same_object(sibling.ReferenceProduct, original):
                raise CADOperationError("POSTCONDITION_FAILED", "Replacement changed another occurrence reference")
        if pose is not None:
            for actual, expected in zip(self._pose(new), pose):
                verify_equal(actual, expected, "Replacement pose")
        report = self.constraint_status({})
        if report["all_active_satisfied"] is False:
            raise CADOperationError("POSTCONDITION_FAILED", "Replacement left unsatisfied/broken constraints; inspect, do not retry")
        return {**result, "handle": handle, "source_document_id": a["source_document_id"],
                "constraint_report": report, "warning": "Unknown constraint status is not a verified mate; no file was saved"}

    def pattern(self, a):
        seed, _ = self.occurrence(a["component_handle"])
        initial = self._pose(seed)
        count = a["count"]
        if int(self.product().Products.Count) + count - 1 > 2000:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Pattern would exceed 2000 immediate occurrences")
        names = [f'{a["name_prefix"]}_{i:02d}' for i in range(2, count+1)]
        self._names(names)
        if a["mode"] == "linear":
            step = a["step_mm"]
            if sum(x*x for x in step) < 1e-16:
                raise CADOperationError("INVALID_ARGUMENT", "Linear pattern step must be nonzero")
            poses = [initial[:9]+[initial[9+j]+i*step[j] for j in range(3)] for i in range(1, count)]
        else:
            unit_vector(a["axis"])
            angle = a["angle_step_deg"]
            if not math.isfinite(angle) or abs(angle) < 1e-9 or abs(angle)*(count-1) >= 360-1e-8:
                raise CADOperationError("INVALID_ARGUMENT", "Circular span must be nonzero and less than 360 degrees; for a full ring use step=360/count")
            poses = [rotated_pose(initial, a["axis"], a["pivot_mm"], angle*i, a["rotate_orientation"])
                     for i in range(1, count)]
        for pose in poses:
            self.validate_pose(pose)
        targets = []
        reference = seed.ReferenceProduct
        for name in names:
            handle, obj = self._add(reference, name)
            targets.append((handle, obj, self._pose(obj)))
        result = self._apply(targets, poses)
        for actual, expected in zip(self._pose(seed), initial):
            verify_equal(actual, expected, "Unchanged pattern seed")
        result.update(total_count_including_seed=count, created_count=len(targets), associative=False,
                      seed_handle=a["component_handle"], shared_reference=True)
        return result

    def transform(self, a):
        mode = a["mode"]
        handles = [row["component_handle"] for row in a["positions"]] if mode == "set_positions" else a["component_handles"]
        targets = self._targets(handles)
        if mode == "set_positions":
            poses = [row["axis_components"] for row in a["positions"]]
        elif mode == "translate":
            poses = [p[:9]+[p[9+i]+a["translation_mm"][i] for i in range(3)] for _, _, p in targets]
        else:
            poses = [rotated_pose(p, a["axis"], a["pivot_mm"], a["angle_deg"]) for _, _, p in targets]
        return self._apply(targets, poses)

    def explode(self, a):
        targets = self._targets([row["component_handle"] for row in a["offsets"]])
        poses = [p[:9]+[p[9+i]+row["translation_mm"][i] for i in range(3)]
                 for (_, _, p), row in zip(targets, a["offsets"])]
        result = self._apply(targets, poses)
        result["restore"] = {"tool": "catia_assembly_transform", "mode": "set_positions",
                             "positions": result["before_positions"],
                             "instruction": "Reread model context and use fresh revision/request_id; never replay the explode call"}
        return result

    def metadata(self, a):
        document = self._bound_document()
        root = document.Product
        requested = {METADATA[key][0]: ({"unknown": 0, "made": 1, "bought": 2}[value] if key == "source" else value)
                     for key, value in a["properties"].items()}
        previous = {key: getattr(root, key) for key in requested}
        self.changed(self.state.register(root, "product"))
        for key, value in requested.items():
            self._active(document)
            setattr(root, key, value)
        readback = {key: getattr(root, key) for key in requested}
        for key, value in requested.items():
            verify_equal(readback[key], value, key)
        return {"ok": True, "previous": previous, "readback": readback, "geometry_updated": False}

    def relay(self, a):
        document = self._bound_document()
        root = document.Product
        component, _ = self.occurrence(a["component_handle"])
        source = self.obj(a["publication_handle"], {"publication"})
        member_index(component.Publications, source)
        expected = source.Valuation
        publications = root.Publications
        before = [obj for _, obj in members(publications)]
        if any(str(obj.Name) == a["name"] for obj in before):
            raise CADOperationError("INVALID_ARGUMENT", "Root publication name already exists")
        self.state.mutation_started = True
        try:
            created = publications.Add(a["name"])
        finally:
            self._active(document)
            self._capture_new(publications, before, "publication")
        handle = self.state.mark_created(created, "publication")
        # The CAA signature takes Publications, despite its prose saying Product.
        publications.SetRelay(a["name"], component.Publications, str(source.Name))
        result = self.update(root)
        self._active(document)
        verify_equal(int(publications.Count), len(before)+1, "Publication count")
        verify_equal(str(created.Name), a["name"], "Publication name")
        if not same_object(created.Valuation, expected):
            raise CADOperationError("POSTCONDITION_FAILED", "Relay valuation identity could not be verified; inspect publication in CATIA")
        return {**result, "handle": handle, "source_publication_handle": a["publication_handle"]}
