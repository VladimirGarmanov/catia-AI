"""Item numbering of immediate assembly occurrences (Generate Numbering equivalent).

CAA V5 Automation documents no Generate Numbering call, so the native instance
"Number" attribute is not reachable. Numbers are written to the documented
instance-level Product.DescriptionInst of immediate root occurrences: it lives in
the bound CATProduct, never in the component CATPart/CATProduct reference files.
Occurrences sharing one ReferenceProduct (COM identity, not PartNumber) get the
same item number, matching catia_drawing_bom_table scope=top and balloons.
"""
import re

from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.assembly_workflow import AssemblyWorkflowTools
from catia_mcp.tools.domain_support import members, read_properties
from catia_mcp.tools.engineering import tool
from catia_mcp.tools.operations import BOOL, group

ORDER = {"enum": ["tree_order", "part_number"]}
START = {"type": "integer", "minimum": 0, "maximum": 100000}
STEP = {"type": "integer", "minimum": 1, "maximum": 1000}
PREFIX = {"type": "string", "maxLength": 16, "pattern": r"^[^\x00-\x1f]*$"}
READ_TOOLS = frozenset({"catia_assembly_numbering_preview"})


def _natural(text):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text or "")]


class AssemblyNumberingTools(AssemblyWorkflowTools):
    def get_tool_definitions(self):
        common = {"order": ORDER, "start": START, "step": STEP, "prefix": PREFIX}
        return [
            tool("catia_assembly_numbering_preview",
                 "Preview item numbers for the immediate occurrences of the active CATProduct: one number per distinct "
                 "reference (COM identity, not PartNumber), in tree order or natural PartNumber order. Shows current "
                 "DescriptionInst values. No writes, activation or Update.",
                 common, ["order", "start", "step"], readonly=True),
            group("catia_assembly_numbering",
                  "Number the parts of the active CATProduct (Generate Numbering equivalent). apply writes prefix+number "
                  "to Product.DescriptionInst of every immediate root occurrence; occurrences of the same reference share "
                  "a number. Existing different non-empty values are refused unless overwrite_existing=true. clear empties "
                  "DescriptionInst only where it holds a value this tool format could have written (prefix+digits). Every "
                  "value is read back. Only the bound assembly changes; component files are untouched. Native 'Number' "
                  "attribute is not exposed by CAA Automation. Use the returned items for balloons and "
                  "catia_drawing_bom_table scope=top (tree_order).", {
                      "apply": {**common, "overwrite_existing": BOOL},
                      "clear": {"prefix": PREFIX},
                  }),
        ]

    def execute(self, name, a):
        if name != "catia_assembly_numbering_preview" and self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("SKETCH_OPEN", "Close the edited sketch before assembly numbering")
        if name == "catia_assembly_numbering_preview":
            return {"ok": True, **self._strip(self._plan(a)), "written": False}
        if a["mode"] == "apply":
            return self._apply(a)
        return self._clear(a)

    def _plan(self, a):
        root = self.product()
        groups, references = [], []
        for _, occurrence in members(root.Products):
            reference = occurrence.ReferenceProduct
            index = next((i for i, r in enumerate(references) if same_object(r, reference)), None)
            if index is None:
                references.append(reference)
                data = read_properties(reference, {"PartNumber": str, "Nomenclature": str})
                groups.append({"part_number": data["PartNumber"], "nomenclature": data["Nomenclature"],
                               "reference_handle": self.state.register(reference, "product_reference"),
                               "occurrences": []})
                index = len(groups) - 1
            current = read_properties(occurrence, {"Name": str, "DescriptionInst": str})
            groups[index]["occurrences"].append({"handle": self.state.register(occurrence, "product"),
                                                 "name": current["Name"], "current": current["DescriptionInst"],
                                                 "_obj": occurrence})
        if not groups:
            raise CADOperationError("INVALID_ARGUMENT", "The assembly has no immediate occurrences to number")
        if a.get("order") == "part_number":
            groups.sort(key=lambda g: _natural(g["part_number"]))
        prefix = a.get("prefix", "")
        for i, row in enumerate(groups):
            row["item"] = a["start"] + i * a["step"]
            row["value"] = f"{prefix}{row['item']}"
            row["quantity"] = len(row["occurrences"])
        public = [{**{k: v for k, v in g.items() if k != "occurrences"},
                   "occurrences": [{k: v for k, v in o.items() if k != "_obj"} for o in g["occurrences"]]}
                  for g in groups]
        return {"items": public, "target": "Product.DescriptionInst", "scope": "immediate root occurrences",
                "order": a.get("order", "tree_order"), "_groups": groups}

    @staticmethod
    def _strip(result):
        result.pop("_groups", None)
        return result

    def _apply(self, a):
        document = self._bound_document()
        plan = self._plan(a)
        groups = plan["_groups"]
        conflicts = [o["name"] for g in groups for o in g["occurrences"]
                     if o["current"] not in (None, "", g["value"])]
        if conflicts and not a["overwrite_existing"]:
            raise CADOperationError("INVALID_ARGUMENT",
                f"DescriptionInst already holds other values on {conflicts}; set overwrite_existing=true to replace them")
        if any(o["current"] is None for g in groups for o in g["occurrences"]):
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "DescriptionInst is not readable on some occurrences")
        self.state.mutation_started = True
        written = []
        for g in groups:
            for o in g["occurrences"]:
                self.changed(o["handle"])
                try:
                    o["_obj"].DescriptionInst = g["value"]
                except Exception as exc:
                    raise CADOperationError("PARTIAL_MUTATION",
                        f"Numbering stopped after {len(written)} occurrences at {o['name']}: {exc}; inspect and rerun") from exc
                written.append(o["handle"])
        self._active(document)
        mismatches = [o["name"] for g in groups for o in g["occurrences"]
                      if str(o["_obj"].DescriptionInst) != g["value"]]
        if mismatches:
            raise CADOperationError("POSTCONDITION_FAILED", f"DescriptionInst readback differs on {mismatches}")
        plan = self._strip(plan)
        return {"ok": True, **plan, "written_occurrences": len(written), "overwritten": conflicts,
                "geometry_changed": False, "component_files_changed": False,
                "verification": "DescriptionInst readback on every occurrence; save the assembly to persist"}

    def _clear(self, a):
        document = self._bound_document()
        pattern = re.compile(re.escape(a.get("prefix", "")) + r"\d+$")
        targets = []
        for _, occurrence in members(self.product().Products):
            value = read_properties(occurrence, {"DescriptionInst": str})["DescriptionInst"]
            if value and pattern.fullmatch(value):
                targets.append((self.state.register(occurrence, "product"), occurrence, value))
        self.state.mutation_started = True
        for handle, occurrence, _ in targets:
            self.changed(handle)
            occurrence.DescriptionInst = ""
        self._active(document)
        left = [h for h, o, _ in targets if str(o.DescriptionInst) != ""]
        if left:
            raise CADOperationError("POSTCONDITION_FAILED", f"DescriptionInst not cleared on {left}")
        return {"ok": True, "cleared": [{"handle": h, "previous": v} for h, _, v in targets],
                "kept_other_values": True}
