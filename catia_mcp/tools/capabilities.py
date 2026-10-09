"""Read the supplied API evidence without pretending that a documented API is a tool."""
import json
from importlib.resources import files

from catia_mcp.tools.engineering import tool, HANDLE

# Explicit implementation links. A link means partial coverage, not the entire
# handbook/GUI command, a license entitlement, or live-CATIA validation.
IMPLEMENTATIONS = {
    1: ["catia_new_part"], 2: ["catia_create_container"], 3: ["catia_create_container"],
    4: ["catia_create_container"], 5: ["catia_feature_state"], 6: ["catia_update_part"],
    7: ["catia_feature_state"], 9: ["catia_list_objects"],
    11: ["catia_create_sketch", "catia_close_sketch"],
    12: ["catia_create_sketch"],
    31: ["catia_sketch_import_geometry"], 32: ["catia_sketch_import_geometry"],
    13: ["catia_sketch_point"], 14: ["catia_sketch_line"],
    16: ["catia_sketch_rectangle", "catia_sketch_centered_rectangle"],
    17: ["catia_sketch_circle"], 18: ["catia_sketch_arc"], 19: ["catia_sketch_ellipse"],
    20: ["catia_sketch_spline"], 21: ["catia_sketch_set_axis"], 33: ["catia_sketch_diagnose"],
    46: ["catia_pad"], 47: ["catia_pocket"], 48: ["catia_shaft"], 49: ["catia_groove"],
    50: ["catia_hole"], 51: ["catia_swept_solid"], 52: ["catia_swept_solid"],
    54: ["catia_solid_loft"], 55: ["catia_solid_loft"],
    64: ["catia_hole"], 65: ["catia_hole"], 66: ["catia_hole"],
    58: ["catia_pad", "catia_pocket"], 59: ["catia_pad", "catia_pocket"],
    60: ["catia_pad", "catia_pocket"], 61: ["catia_pad", "catia_pocket"],
    62: ["catia_pad", "catia_pocket"], 63: ["catia_pad"],
    68: ["catia_fillet"], 72: ["catia_chamfer"], 73: ["catia_shell"], 74: ["catia_thickness"],
    75: ["catia_draft"],
    76: ["catia_gsd_thick_surface"], 77: ["catia_gsd_close_surface"],
    78: ["catia_rect_pattern"], 79: ["catia_circ_pattern"], 81: ["catia_mirror"],
    84: ["catia_boolean"], 85: ["catia_boolean"], 86: ["catia_boolean"], 87: ["catia_boolean"],
    89: ["catia_reference_point"], 90: ["catia_reference_point"], 91: ["catia_reference_point"],
    94: ["catia_reference_point"], 95: ["catia_gsd_line"],
    100: ["catia_reference_plane"], 101: ["catia_reference_plane"],
    103: ["catia_reference_plane"], 104: ["catia_reference_plane"], 105: ["catia_reference_plane"],
    107: ["catia_reference_plane"], 108: ["catia_reference_plane"], 109: ["catia_reference_plane"],
    111: ["catia_gsd_extrude"], 112: ["catia_gsd_revolve"], 113: ["catia_gsd_sweep"],
    114: ["catia_gsd_multi_section_surface"], 115: ["catia_gsd_fill"], 116: ["catia_gsd_blend"],
    117: ["catia_gsd_offset_surface"], 123: ["catia_gsd_join"], 124: ["catia_gsd_split"],
    125: ["catia_gsd_trim"], 126: ["catia_gsd_intersection"], 127: ["catia_gsd_project"],
    132: ["catia_add_component"], 133: ["catia_add_new_part"], 148: ["catia_move_component"],
    142: ["catia_fix_constraint"], 143: ["catia_coincidence_constraint"],
    145: ["catia_offset_constraint"], 146: ["catia_angle_constraint"],
    188: ["catia_create_parameter", "catia_set_parameter"], 189: ["catia_create_formula"],
    198: ["catia_measure_object"], 199: ["catia_measure_distance"], 200: ["catia_get_inertia"],
    209: ["catia_pocket"], 210: ["catia_sketch_diagnose"], 218: ["catia_get_inertia"],
    202: ["catia_export"], 203: ["catia_export"], 204: ["catia_export"],
    205: ["catia_export"], 206: ["catia_export"], 207: ["catia_save_document"],
}
for number in (34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45):
    IMPLEMENTATIONS[number] = ["catia_sketch_constraint"]


# Manual links indicate scoped implementations, not full GUI equivalence.
for numbers, handler in (
    ((53, 69, 70, 71, 80, 82, 83, 88), "catia_solid_operation"),
    ((62, 63, 67, 73, 75, 54, 55), "catia_feature_options"),
    ((90, 91, 92, 93, 96, 97, 98, 102, 106, 110, 118, 119, 121, 122, 128, 129, 130, 131), "catia_wireframe_surface"),
    ((99,), "catia_axis_system"), ((8,), "catia_visibility"), ((15,), "catia_sketch_profile"),
    ((22, 23, 24, 25), "catia_sketch_line_edit"),
    ((26, 27, 28, 29, 30), "catia_sketch_transform"),
    ((35, 43), "catia_sketch_relation"),
    ((134, 135, 136, 137, 139, 140, 141, 144, 147, 195), "catia_assembly_operation"),
    ((149, 150, 151), "catia_dmu"),
    ((*range(152, 160), 163, 170), "catia_drawing_view"),
    ((160, 161, 162, 174), "catia_drawing_edit"),
    ((164, 165, 171), "catia_drawing_dimension"),
    ((166, 167), "catia_drawing_dimension_series"),
    ((168, 169, 172, 175), "catia_drawing_annotation"),
    ((183,), "catia_hole"), ((183,), "catia_pocket"), ((186,), "catia_set_parameter"),
    ((120, 189, 190, 191, 192), "catia_knowledgeware"),
    ((193, 194), "catia_template_instance"),
    ((198, 199, 200), "catia_measure_exact"),
    ((201,), "catia_material"), ((*range(208, 219),), "catia_diagnose_geometry"),
):
    for number in numbers:
        IMPLEMENTATIONS.setdefault(number, []).append(handler)

UNSUPPORTED_REASONS = {
    138: "Occurrence-aware external copy/link workflow not confirmed; publication alone is not Design in Context.",
    196: "Arbitrary scripts forbidden; no audited fixed-contract macro supplied.",
    197: "Infrastructure, not a geometry command. Server uses raw pywin32 without mixing wrappers.",
}

# Alternatives are not implementation links: ordinary features do not implement
# the native multi-domain GUI operation or preserve its feature-tree semantics.
ALTERNATIVES = {
    56: {"tool": "catia_profile_solids", "mode": "pads", "equivalent_native_feature": False},
    57: {"tool": "catia_profile_solids", "mode": "pockets", "equivalent_native_feature": False},
}


class CapabilityTools:
    def __init__(self):
        self.available_tools = set()

    def get_tool_definitions(self):
        return [tool("catia_capability_status", "Look up supplied CATIA API documentation and implementation coverage without connecting to CATIA. Documentation is NOT proof of implemented or live-tested tools.",
                     {"capability_id": {"type": "string", "pattern": "^CATIA-[0-9]{3}$"},
                      "query": HANDLE, "limit": {"type": "integer", "minimum": 1, "maximum": 218, "default": 10}}, readonly=True),
                tool("catia_capability_request", "Resolve a handbook capability to existing typed tools, or explicitly reject unsupported operations. This never executes arbitrary COM or scripts and never claims an unsupported operation succeeded.",
                     {"capability_id": {"type": "string", "pattern": "^CATIA-[0-9]{3}$"}}, ["capability_id"], readonly=True)]

    def execute(self, name, args):
        catalog = json.loads(files("CATIA_AGENT_CODEX_PACKAGE").joinpath("CATIA_AGENT_TOOL_CATALOG.json").read_text(encoding="utf-8"))
        if name == "catia_capability_request":
            entries = [e for e in catalog["capabilities"] if e["capability_id"] == args["capability_id"]]
            if not entries:
                return {"ok": False, "status": "unsupported", "code": "UNSUPPORTED_OPERATION", "message": "Unknown handbook capability"}
            entry = entries[0]
            available = [h for h in IMPLEMENTATIONS.get(entry["handbook_id"], []) if h in self.available_tools]
            if available:
                return {"ok": True, "status": "routing_only", "executed": False, "tools": available,
                        "coverage": "partial; use a supported mode and read its limitations", "live_tested": False}
            return {"ok": False, "status": "unsupported", "code": "UNSUPPORTED_OPERATION", "executed": False,
                    "capability_id": entry["capability_id"],
                    "alternative": ALTERNATIVES.get(entry["handbook_id"]),
                    "message": UNSUPPORTED_REASONS.get(entry["handbook_id"], entry["implementation_notes"]),
                    "research_task": "Confirm exact COM constructor, collection acquisition, input semantics and live postconditions before enabling",
                    "api_bindings": entry["api_bindings"]}
        matches = []
        for entry in catalog["capabilities"]:
            if args.get("capability_id") and entry["capability_id"] != args["capability_id"]:
                continue
            if args.get("query") and args["query"].casefold() not in json.dumps(entry, ensure_ascii=False).casefold():
                continue
            handlers = IMPLEMENTATIONS.get(entry["handbook_id"], [])
            available = [h for h in handlers if h in self.available_tools]
            matches.append({"capability_id": entry["capability_id"], "title": entry["title"],
                            "documented": entry["mapping_status"] != "unconfirmed",
                            "mapping_status": entry["mapping_status"], "implemented": bool(available),
                            "implementation_coverage": "partial; see individual tool schema" if available else "not_implemented",
                            "offline_tested": False, "live_tested": False,
                            "available_in_session": bool(available), "tools": available,
                            "api_bindings": entry["api_bindings"], "limitations": entry["implementation_notes"],
                            "unsupported_reason": None if available else UNSUPPORTED_REASONS.get(entry["handbook_id"], entry["implementation_notes"])})
            matches[-1]["alternative"] = ALTERNATIVES.get(entry["handbook_id"])
        return {"ok": True, "matches": matches[:args.get("limit", 10)], "total_matches": len(matches),
                "note": "Capability-level validation is not inferred from registration/schema smoke tests. Unimplemented entries are research tasks, not executable tools."}
