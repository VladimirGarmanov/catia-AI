"""Existing-sketch editing. InWorkObject is NOT proof of a UI edition state."""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, tool, dimension
from catia_mcp.tools.operations import OperationTools


class SketchSessionTools(OperationTools):
    def sketches(self):
        part, result = self.conn.get_active_part(), []
        def collect(collection):
            for i in range(1, collection.Count + 1):
                sketch = collection.Item(i)
                if not any(same_object(sketch, old) for old in result):
                    result.append(sketch)
        def visit(collection, depth=0):
            if depth > 30:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", "Geometrical-set nesting exceeds limit")
            for i in range(1, collection.Count + 1):
                body = collection.Item(i)
                collect(body.HybridSketches)
                visit(body.HybridBodies, depth + 1)
        for i in range(1, part.Bodies.Count + 1):
            collect(part.Bodies.Item(i).Sketches)
        visit(part.HybridBodies)
        return result

    def get_tool_definitions(self):
        return [
            tool("catia_sketch_set_construction", "Set existing geometry in the bound open sketch to construction=true or standard=false. Use a fresh handle from catia_sketch_get_geometry. Preserves geometry and constraints; Evaluate/readback checks the flag, not full constraint rank. To make the revolution centerline standard, first assign a different axis explicitly.", {
                "geometry_handle": HANDLE, "construction": {"type": "boolean"},
            }, ["geometry_handle", "construction"]),
            tool("catia_sketch_constraints", "Read exact constraint handles, types, modes, statuses and available dimension values in the bound sketch; no solver call.", {}, readonly=True),
            tool("catia_sketch_edit_constraint", "Edit one exact existing constraint in the bound sketch: explicit dimension in mm/deg, driving/reference mode, activation, or explicit remove. Removal deletes only this constraint. Evaluate and read status; no automatic repair.", {
                "constraint_handle": HANDLE, "action": {"enum": ["dimension", "driving", "reference", "activate", "deactivate", "remove"]},
                "value": NUMBER, "unit": {"enum": ["mm", "deg"]},
            }, ["constraint_handle", "action"]),
            tool("catia_sketch_context", "Read existing sketches and exact selection/InWorkObject candidates without opening or closing edition. UI editing cannot be inferred from InWorkObject alone.", {}, readonly=True),
            tool("catia_sketch_begin_edit", "Bind existing sketch: open calls OpenEdition; adopt_user_open uses Factory2D without reopening, requiring explicit confirmation that the user already opened this sketch. Never creates geometry.", {
                "source": {"enum": ["handle", "selection", "in_work"]}, "sketch_handle": HANDLE,
                "mode": {"enum": ["open", "adopt_user_open"]},
                "user_confirmed_open": {"type": "boolean"},
            }, ["source", "mode"]),
        ]

    def execute(self, name, a):
        if name == "catia_sketch_set_construction":
            return self.set_construction(a)
        if name in {"catia_sketch_constraints", "catia_sketch_edit_constraint"}:
            return self.constraints(name, a)
        sketches = self.sketches()
        in_work = self.conn.get_active_part().InWorkObject
        selection = self.conn.active_document.Selection
        selected = [selection.Item2(i).Value for i in range(1, selection.Count2 + 1)]
        editor = self.engineering.sketcher
        if name == "catia_sketch_context":
            return {"ok": True, "ui_edition": "unknown", "server_bound": editor._active_sketch is not None,
                "sketches": [{"handle": self.state.register(s, "sketch"), "name": str(s.Name),
                    "in_work": same_object(s, in_work), "selected": any(same_object(s, o) for o in selected),
                    "geometry_count": int(s.GeometricElements.Count), "constraint_count": int(s.Constraints.Count)} for s in sketches],
                "warning": "If selection and InWorkObject differ, clarify the intended sketch before writing"}
        if (a["source"] == "handle") != ("sketch_handle" in a):
            raise CADOperationError("INVALID_ARGUMENT", "sketch_handle is required only for source=handle")
        if a["mode"] == "adopt_user_open" and a.get("user_confirmed_open") is not True:
            raise CADOperationError("INVALID_ARGUMENT", "Adoption requires user confirmation of the already-open sketch")
        if a["mode"] == "open" and a.get("user_confirmed_open"):
            raise CADOperationError("INVALID_ARGUMENT", "Use adopt_user_open for a UI-open sketch")
        if a["source"] == "handle":
            target = self.obj(a["sketch_handle"], {"sketch"})
        elif a["source"] == "in_work":
            target = in_work
        else:
            if len(selected) != 1:
                raise CADOperationError("AMBIGUOUS_REFERENCE", "Select exactly one whole sketch")
            # Sub-element Value can be its parent: require the selection itself to be a Sketch.
            if str(selection.Item2(1).Type) != "Sketch":
                raise CADOperationError("WRONG_GEOMETRY_TYPE", "Selection must be a whole Sketch, not a sub-element")
            target = selected[0]
        if not any(same_object(target, sketch) for sketch in sketches):
            raise CADOperationError("WRONG_GEOMETRY_TYPE", "Target is not a sketch in a supported container of the active Part")
        if editor._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Finish the server-bound sketch before binding another")
        if a["mode"] == "adopt_user_open" and not same_object(in_work, target):
            raise CADOperationError("AMBIGUOUS_REFERENCE", "Confirmed UI sketch differs from InWorkObject")
        factory = target.Factory2D if a["mode"] == "adopt_user_open" else target.OpenEdition()
        editor._active_sketch, editor._active_factory = target, factory
        editor._active_document_identity = editor._document_identity(self.conn.active_document)
        editor._active_document = self.conn.active_document
        editor._adopted_ui_sketch = a["mode"] == "adopt_user_open"
        return {"ok": True, "handle": self.state.register(target, "sketch"), "name": str(target.Name),
                "created_sketch": False, "mode": a["mode"], "edition_left_open": True,
                "warning": "UI editing state is user-confirmed, not proven by COM; do not switch sketch/document"}

    def set_construction(self, a):
        editor = self.engineering.sketcher
        editor._ensure_sketch_open()
        sketch = editor._active_sketch
        geometry = self.state.resolve(a["geometry_handle"]).value
        elements = sketch.GeometricElements
        if not any(same_object(geometry, elements.Item(i)) for i in range(1, elements.Count + 1)):
            raise CADOperationError("INVALID_ARGUMENT", "Geometry does not belong to the bound sketch")
        try:
            previous = bool(geometry.Construction)
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "Element does not expose Construction") from exc
        if not a["construction"]:
            # Do not silently invalidate the shaft/groove axis definition.
            centerline = sketch.CenterLine
            if centerline is not None and same_object(centerline, geometry):
                raise CADOperationError("INVALID_ARGUMENT", "Reassign the revolution axis before making its line standard")
        if previous != a["construction"]:
            self.changed(a["geometry_handle"])
            geometry.Construction = a["construction"]
            sketch.Evaluate()
        actual = bool(geometry.Construction)
        if actual != a["construction"]:
            raise CADOperationError("POSTCONDITION_FAILED", "Construction readback differs from requested value")
        return {"ok": True, "geometry_handle": a["geometry_handle"],
                "previous_construction": previous, "construction": actual,
                "changed": actual != previous, "edition_left_open": True,
                "warnings": ["Existing constraints retained. Close/update and verify the resulting profile before using it in a feature."]}

    def constraints(self, name, a):
        editor = self.engineering.sketcher
        editor._ensure_sketch_open()
        sketch = editor._active_sketch
        collection = sketch.Constraints
        if name == "catia_sketch_constraints":
            result = []
            for i in range(1, collection.Count + 1):
                obj = collection.Item(i)
                row = {"handle": self.state.register(obj, "constraint"), "name": str(obj.Name),
                       "type": int(obj.Type), "mode": int(obj.Mode), "status": int(obj.Status)}
                try:
                    row["dimension"] = str(obj.Dimension.ValueAsString())
                except Exception:
                    row["dimension"] = None
                result.append(row)
            return {"ok": True, "constraints": result, "count": len(result)}
        obj = self.obj(a["constraint_handle"], {"constraint"})
        indices = [i for i in range(1, collection.Count + 1) if same_object(obj, collection.Item(i))]
        if len(indices) != 1:
            raise CADOperationError("INVALID_ARGUMENT", "Constraint does not belong to the bound sketch")
        action = a["action"]
        if action != "dimension" and ("value" in a or "unit" in a):
            raise CADOperationError("INVALID_ARGUMENT", "value/unit are only valid for dimension edits")
        if action == "dimension":
            expected = "deg" if int(obj.Type) in (6, 7) else "mm" if int(obj.Type) in (1, 5, 14, 18, 19) else None
            if expected is None or a.get("unit") != expected or "value" not in a:
                raise CADOperationError("INVALID_ARGUMENT", "Unsupported dimension type or missing/wrong explicit unit/value")
            if int(obj.Mode) != 0:
                raise CADOperationError("INVALID_ARGUMENT", "Reference dimension cannot drive geometry; change mode explicitly first")
        self.changed(a["constraint_handle"])
        if action == "remove":
            collection.Remove(indices[0])
            sketch.Evaluate()
            return {"ok": True, "removed_constraint": a["constraint_handle"],
                    "edition_left_open": True, "diagnosis": editor._diagnose()}
        result = None
        if action == "dimension":
            result = dimension(obj.Dimension, a["value"], a["unit"])
        elif action in {"driving", "reference"}:
            obj.Mode = 0 if action == "driving" else 1
        elif action == "activate":
            obj.Activate()
        else:
            obj.Deactivate()
        sketch.Evaluate()
        status = int(obj.Status)
        if action != "deactivate" and status != 0:
            raise CADOperationError("POSTCONDITION_FAILED", f"Constraint solver status={status}; inspect sketch before proceeding")
        return {"ok": True, "status_native": status, "mode": int(obj.Mode), "dimension": result,
                "edition_left_open": True, "warning": "Close and Update before accepting sketch; solver status is not geometric verification"}
