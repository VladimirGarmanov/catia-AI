"""Typed drawing dimensions, Properties-dialog edits, generated dimensions and BOM tables.

Every enum below is the 0-based value index of a cached CAA V5 DraftingInterfaces
enumeration (CatDimType, CatDimLineRep, CatDimDualDisplay, CatDimFrame,
CatDimReference, CatDimOrientation, CatDimSymbols, CatDimLineGraphRep,
CatJustification, CatFilletRepresentation). Agents use names, never raw integers.

Dimension presentation never changes a measured value: SetFakeDimValue is not
exposed, and the measured DrawingDimValue.Value is always read back. Change the
source model to change geometry. Native behavior needs live Windows validation.
"""
import math

from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.domain_support import members, read_properties, verify_equal
from catia_mcp.tools.drafting import XY
from catia_mcp.tools.drawing_management import DrawingManagementTools
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, tool
from catia_mcp.tools.operations import BOOL, array, group, optional_fields

TEXT = {"type": "string", "maxLength": 200}
NONNEGATIVE = {"type": "number", "minimum": 0}

# CatDimType indices.
DIM_TYPES = {"distance": 0, "length": 2, "angle": 4, "radius": 5, "diameter": 9}
ALONG_TYPES = {"distance": 0, "length": 2, "radius_tangent": 6, "diameter_tangent": 10}
LINE_REP = {"undefined": 0, "horizontal": 1, "vertical": 2, "auto": 3, "user_defined": 4,
            "true_length": 5, "parallel": 6, "offset": 7}
DUAL = {"none": 0, "below": 1, "fractional": 2, "side_by_side": 3}
DIM_FRAME = {"none": 0, "circle": 1, "scored_circle": 2, "diamond": 3, "square": 4,
             "rectangle": 5, "oblong": 6, "right_flag": 7, "right_triangle": 8}
VALUE_REFERENCE = {"screen": 0, "view": 1, "dimension_line": 2}
VALUE_ORIENTATION = {"horizontal": 0, "vertical": 1, "parallel": 2, "perpendicular": 3, "angle": 4}
SYMBOLS = {name: i for i, name in enumerate((
    "none", "open_arrow", "closed_arrow", "filled_arrow", "symmetric_arrow", "slash", "circle",
    "filled_circle", "scored_circle", "circled_cross", "triangle", "filled_triangle", "cross", "x_cross"))}
SYMBOLS_SIDE = {"auto": 0, "inside": 1, "outside": 2, "first_inside_second_outside": 3,
                "first_outside_second_inside": 4}
LINE_GRAPH = {"one_part": 0, "two_parts": 1, "leader_one_part": 2, "leader_two_parts": 3}
JUSTIFY = {"left": 0, "center": 1, "right": 2}
FILLETS = {"none": 0, "boundary": 1, "symbolic": 2, "original_edge": 3, "projected_original_edge": 4}
# CatGeometricType: Point2D=2, Line2D=3, Circle2D=5 (arcs are Circle2D), Ellipse2D=8.
GEOMETRY = {"distance": {2, 3, 5, 8}, "length": {3}, "angle": {3}, "radius": {5}, "diameter": {5}}
COUNTS = {"distance": 2, "length": 1, "angle": 2, "radius": 1, "diameter": 1}
# Tolerance type integers follow the CAA SetTolerances examples (0 none, 1 numerical,
# 2 alphanumerical); unverified on the installed release until a Windows probe passes.
TOLERANCE_TYPES = {"clear": 0, "numerical": 1, "fit": 2}
BOM_COLUMNS = {"item": "Item", "part_number": "Part Number", "quantity": "Qty",
               "nomenclature": "Nomenclature", "revision": "Revision", "definition": "Definition",
               "description": "Description", "source": "Source"}
SOURCE_LABELS = {0: "unknown", 1: "made", 2: "bought"}

GEOMETRY_SOURCE = {"geometry_handles": array(HANDLE, 1, 2), "selection_handles": array(HANDLE, 1, 2)}
DIMENSION_COMMON = {"picked_points_mm": array(XY, 1, 2), "line_representation": {"enum": list(LINE_REP)},
                    "expected_value": NUMBER, "value_tolerance": POSITIVE, **GEOMETRY_SOURCE}


def _angle_close(actual, expected_deg, tol):
    """Drawing angle values are unit-unstated in CAA: accept degree or radian readings."""
    return abs(actual - expected_deg) <= tol or abs(actual - math.radians(expected_deg)) <= math.radians(tol)


def _out_values(method, index, count):
    """Read a CAA Sub with output parameters; None means readback unavailable, never guessed.

    pywin32 returns output parameters as a tuple; some bindings need placeholders.
    index=None means the Sub has output parameters only.
    """
    prefix = () if index is None else (index,)
    for args in (prefix, (*prefix, *([""] * count))):
        try:
            values = method(*args)
        except Exception:
            continue
        if isinstance(values, (tuple, list)) and len(values) >= count:
            return list(values)[-count:]
    return None


def read_dimension_properties(obj):
    """Properties-dialog readback for one DrawingDimension; unavailable fields are reported."""
    data = read_properties(obj, {"DimType": int, "DimStatus": int, "DualValue": int, "ValueFrame": int,
        "ValueReference": int, "ValueOrientation": int, "ValueAngle": float, "SymbolsSide": int,
        "HalfDimMode": bool, "Forshortened": bool, "ValueAutoMode": bool, "IsClipped": bool})
    try:
        value = obj.GetValue()
        data["value"] = float(value.Value)
        data["format"] = {"precision": float(value.GetFormatPrecision(1)), "name": str(value.GetFormatName(1))}
        texts = _out_values(value.GetBaultText, 1, 4)
        data["texts"] = None if texts is None else dict(zip(("before", "after", "upper", "lower"), map(str, texts)))
        ps = _out_values(value.GetPSText, 1, 2)
        data["prefix_suffix"] = None if ps is None else dict(zip(("prefix", "suffix"), map(str, ps)))
    except Exception as exc:
        data.setdefault("unavailable", {})["value"] = str(exc)
    try:
        tolerance = _out_values(obj.GetTolerances, None, 7)
    except Exception:
        tolerance = None
    data["tolerance"] = None if tolerance is None or len(tolerance) < 7 else dict(zip(
        ("type", "name", "upper_text", "lower_text", "upper_value", "lower_value", "display_mode"), tolerance[-7:]))
    return data


def _with_dimension_options(definition):
    return optional_fields(definition, {
        "distance_along": {"direction_handle": HANDLE},
    }, DIMENSION_COMMON)


class DraftingPropertyTools(DrawingManagementTools):
    def get_tool_definitions(self):
        dim_modes = {mode: {} for mode in DIM_TYPES}
        dim_modes["distance_along"] = {"along_type": {"enum": list(ALONG_TYPES)}, "direction_angle_deg": NUMBER}
        typed = group("catia_drawing_dimension_typed",
            "Create ONE drawing dimension by engineering type: distance (2 elements), length (1 line), angle (2 lines), "
            "radius / diameter (1 circle or arc), distance_along (Add2: dimension line at direction_angle_deg from the view "
            "or from optional direction_handle line). Geometry: geometry_handles of 2D elements in that view (catia_domain_objects), "
            "or selection_handles of currently selected drawing elements (EXPERIMENTAL for generated/projected edges; needs a "
            "Windows probe). picked_points_mm are view-local selection points (default element origin); they choose the side/sector. "
            "Reads back native DimType and the MEASURED value; expected_value (mm or deg) turns a mismatch into "
            "POSTCONDITION_FAILED with the dimension left behind. Never fakes a value. For many dimensions from 3D constraints "
            "use catia_drawing_generate_dimensions.",
            dim_modes, {"view_handle": HANDLE})
        props = group("catia_drawing_dimension_properties",
            "Drafting Properties dialog for ONE existing dimension (handle from catia_domain_objects / creation). All fields of a "
            "mode are optional but at least one is required. value: precision (e.g. 0.01), format_name, before/after/upper/lower "
            "texts and prefix/suffix around the measured value (e.g. prefix '4x', suffix 'THRU'); value_index 2 targets the dual "
            "value. dual_value: display. presentation: value frame, value reference/orientation/angle, symbol side, half/"
            "foreshortened modes. dimension_line: graphic representation and both arrow symbols. extension_lines: overrun/gap/"
            "visibility of line 1, 2 or both (mm). tolerance_numerical: +upper/-lower mm; tolerance_fit: text pair such as H7; "
            "tolerance_clear removes it. Each write updates the sheet and reads the edited fields back; the measured value is "
            "never replaced (no fake dimensions) and source geometry is untouched.", {
                "value": {}, "dual_value": {"display": {"enum": list(DUAL)}}, "presentation": {},
                "dimension_line": {}, "extension_lines": {"line": {"enum": [1, 2, "both"]}},
                "tolerance_numerical": {"upper_mm": NUMBER, "lower_mm": NUMBER},
                "tolerance_fit": {"upper_text": TEXT, "lower_text": TEXT},
                "tolerance_clear": {},
            }, {"dimension_handle": HANDLE})
        optional_fields(props, {
            "value": {"value_index": {"enum": [1, 2]}, "precision": POSITIVE, "format_name": HANDLE,
                      "before_text": TEXT, "after_text": TEXT, "upper_text": TEXT, "lower_text": TEXT,
                      "prefix": TEXT, "suffix": TEXT},
            "presentation": {"frame": {"enum": list(DIM_FRAME)}, "value_reference": {"enum": list(VALUE_REFERENCE)},
                             "value_orientation": {"enum": list(VALUE_ORIENTATION)}, "value_angle_deg": NUMBER,
                             "symbols_side": {"enum": list(SYMBOLS_SIDE)}, "half_dimension": BOOL,
                             "foreshortened": BOOL},
            "dimension_line": {"graphic_representation": {"enum": list(LINE_GRAPH)},
                               "first_symbol": {"enum": list(SYMBOLS)}, "second_symbol": {"enum": list(SYMBOLS)}},
            "extension_lines": {"overrun_mm": NONNEGATIVE, "gap_mm": NONNEGATIVE, "visible": BOOL},
            "tolerance_numerical": {"tolerance_name": HANDLE},
            "tolerance_fit": {"tolerance_name": HANDLE},
        })
        text_style = tool(
            "catia_drawing_text_style",
            "Drafting Properties > Font/Text for ONE existing drawing text: bold, italic, underline, strike-through, font, size "
            "(mm), justification and wrapping width (mm). At least one field. Calls TextProperties.Update, updates the sheet and "
            "reads the fields back. Text content is edited with catia_drawing_text_edit; dimension values are never edited here.",
            {"text_handle": HANDLE, "bold": BOOL, "italic": BOOL, "underline": BOOL, "strike_through": BOOL,
             "font_name": HANDLE, "size_mm": POSITIVE, "justification": {"enum": list(JUSTIFY)},
             "wrapping_width_mm": NONNEGATIVE}, ["text_handle"])
        return [
            _with_dimension_options(typed),
            props,
            text_style,
            tool("catia_drawing_view_generation",
                 "Drafting view Properties > Generation for ONE generative view: hidden lines, fillet representation, color "
                 "inheritance and 3D points projection. At least one field. Updates the view's generative behavior and sheet, "
                 "then reads every field back. Does not modify the source part.",
                 {"view_handle": HANDLE, "hidden_lines": BOOL, "fillets": {"enum": list(FILLETS)},
                  "color_inheritance": BOOL, "points_projection": BOOL}, ["view_handle"]),
            tool("catia_drawing_generate_dimensions",
                 "Native Generate Dimensions for ONE sheet: CATIA creates associative dimensions in every view from the source "
                 "part's 3D constraints (distance, length, angle, radius, diameter only; one per constraint). Reports the new "
                 "dimension handles per view with their measured values. Clean up or reposition them explicitly afterwards; "
                 "nothing is deleted automatically. Zero new dimensions is reported as FEATURE_NO_EFFECT.",
                 {"sheet_handle": HANDLE}, ["sheet_handle"]),
            tool("catia_drawing_bom_table",
                 "Create a Bill of Materials as a native DrawingTable in an explicit view from an OPEN CATProduct "
                 "(source_document_id from catia_get_workspace_state / catia_domain_objects), read without activation. Rows group "
                 "occurrences by actual reference identity (not PartNumber) in first-occurrence order; scope leaf (terminal parts), "
                 "top (root children) or all. Item numbers are 1..N in row order: reuse them for catia_drawing_annotation balloons. "
                 "Header labels default to English names; position/sizes mm. Every cell is read back. Not a native associative "
                 "BOM: regenerate after assembly changes.",
                 {"view_handle": HANDLE, "source_document_id": HANDLE, "position_mm": XY,
                  "columns": {**array({"enum": list(BOM_COLUMNS)}, 1, 8), "uniqueItems": True},
                  "headers": array(TEXT, 1, 8), "scope": {"enum": ["leaf", "top", "all"]},
                  "row_height_mm": POSITIVE, "column_widths_mm": array(POSITIVE, 1, 8)},
                 ["view_handle", "source_document_id", "position_mm", "columns", "scope", "row_height_mm", "column_widths_mm"]),
        ]

    def execute(self, name, a):
        self.drawing()
        return {"catia_drawing_dimension_typed": self.typed_dimension,
                "catia_drawing_dimension_properties": self.dimension_properties,
                "catia_drawing_text_style": self.text_style,
                "catia_drawing_view_generation": self.view_generation,
                "catia_drawing_generate_dimensions": self.generate_dimensions,
                "catia_drawing_bom_table": self.bom_table}[name](a)

    # ------------------------------------------------------------------ dimensions
    def _geometry(self, a, view):
        if ("geometry_handles" in a) == ("selection_handles" in a):
            raise CADOperationError("INVALID_ARGUMENT", "Supply geometry_handles OR selection_handles")
        if "geometry_handles" in a:
            elements = [self.obj(h, {"drawing_geometry"}) for h in a["geometry_handles"]]
            pool = [g for _, g in members(view.GeometricElements)]
            if not all(any(same_object(e, g) for g in pool) for e in elements):
                raise CADOperationError("INVALID_ARGUMENT", "Geometry must belong to the specified view")
            return elements, "view_geometry"
        # Experimental: currently selected drawing elements (e.g. generated edges).
        return [self.state.resolve(h).value for h in a["selection_handles"]], "selection_experimental"

    def typed_dimension(self, a):
        mode = a["mode"]
        view = self.obj(a["view_handle"], {"view"})
        sheet, _ = self.view_owner(view)
        elements, source = self._geometry(a, view)
        kind = a["along_type"] if mode == "distance_along" else mode
        expected_count = {"distance": 2, "length": 1, "radius_tangent": 1, "diameter_tangent": 1}.get(kind, COUNTS.get(kind))
        if len(elements) != expected_count:
            raise CADOperationError("INVALID_ARGUMENT", f"{kind} needs {expected_count} element(s), got {len(elements)}")
        allowed = GEOMETRY.get(kind, {3, 5})
        types = []
        for element in elements:
            try:
                types.append(int(element.GeometricType))
            except Exception:
                types.append(None)
        if source == "view_geometry" and any(t not in allowed for t in types):
            raise CADOperationError("WRONG_GEOMETRY_TYPE",
                f"{kind} needs CatGeometricType in {sorted(allowed)}; got {types}. Radius/diameter need a circle or arc")
        points = a.get("picked_points_mm") or [[0.0, 0.0]] * len(elements)
        if len(points) != len(elements):
            raise CADOperationError("INVALID_ARGUMENT", "One picked point is required per geometry element")
        flat = tuple(v for p in points for v in p)
        direction = None
        if "direction_handle" in a:
            if mode != "distance_along":
                raise CADOperationError("INVALID_ARGUMENT", "direction_handle applies to distance_along only")
            direction = self.obj(a["direction_handle"], {"drawing_geometry"})
        self.changed(a["view_handle"])
        if mode == "distance_along":
            native = ALONG_TYPES[a["along_type"]]
            obj = view.Dimensions.Add2(native, tuple(elements), flat, direction, math.radians(a["direction_angle_deg"]))
        else:
            native = DIM_TYPES[mode]
            obj = view.Dimensions.Add(native, tuple(elements), flat, LINE_REP[a.get("line_representation", "auto")])
        handle = self.state.mark_created(obj, "drawing_dimension")
        result = self.update(sheet)
        actual_type = int(obj.DimType)
        if actual_type != native:
            raise CADOperationError("POSTCONDITION_FAILED",
                f"Dimension {handle} has DimType {actual_type}, expected {native} ({kind}); it was left behind, inspect it")
        try:
            measured = float(obj.GetValue().Value)
        except Exception as exc:
            measured = None
            result.setdefault("warnings", []).append(f"Measured value unavailable: {exc}")
        if "expected_value" in a:
            tol = a.get("value_tolerance", 0.01)
            if measured is None:
                raise CADOperationError("POSTCONDITION_FAILED",
                    f"Dimension {handle} created but its measured value cannot be read; expected {a['expected_value']}")
            ok = (_angle_close(measured, a["expected_value"], tol) if kind == "angle"
                  else abs(measured - a["expected_value"]) <= tol)
            if not ok:
                raise CADOperationError("POSTCONDITION_FAILED",
                    f"Dimension {handle} measures {measured}, expected {a['expected_value']} ±{tol}; "
                    "it was left behind. Check picked geometry or the source model, never fake the value")
        return {**result, "handle": handle, "dimension_type": kind, "native_dim_type": actual_type,
                "measured_value": measured, "dimension_status": int(obj.DimStatus), "geometry_source": source,
                "warning": "Attachment/side and display units need visual verification; selection geometry is experimental"}

    def _value_object(self, obj):
        try:
            return obj.GetValue()
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", f"DrawingDimension.GetValue failed: {exc}") from exc

    def dimension_properties(self, a):
        mode, handle = a["mode"], a["dimension_handle"]
        obj = self.obj(handle, {"drawing_dimension"})
        sheet, _, _ = self.child_owner(obj, "drawing_dimension")
        fields = {k: v for k, v in a.items() if k not in {"mode", "dimension_handle", "document_id", "request_id",
                                                          "expected_revision", "value_index", "line"}}
        if mode in {"value", "presentation", "dimension_line", "extension_lines"} and not fields:
            raise CADOperationError("INVALID_ARGUMENT", f"{mode} needs at least one property to change")
        try:
            measured_before = float(obj.GetValue().Value)
        except Exception:
            measured_before = None
        self.changed(handle)
        checks, unverified = [], []
        if mode == "value":
            value, index = self._value_object(obj), a.get("value_index", 1)
            if "precision" in a:
                value.SetFormatPrecision(index, a["precision"])
                checks.append(("precision", lambda: float(value.GetFormatPrecision(index)), a["precision"]))
            if "format_name" in a:
                value.SetFormatName(index, a["format_name"])
                checks.append(("format_name", lambda: str(value.GetFormatName(index)), a["format_name"]))
            bault = ("before_text", "after_text", "upper_text", "lower_text")
            if any(k in a for k in bault):
                current = _out_values(value.GetBaultText, index, 4)
                if current is None and not all(k in a for k in bault):
                    raise CADOperationError("CAPABILITY_UNAVAILABLE",
                        "Current before/after/upper/lower texts cannot be read; supply all four to avoid erasing one")
                wanted = [a.get(k, str(current[i]) if current else "") for i, k in enumerate(bault)]
                value.SetBaultText(index, *wanted)
                checks.append(("bault_text", lambda: _out_values(value.GetBaultText, index, 4), wanted))
            if "prefix" in a or "suffix" in a:
                current = _out_values(value.GetPSText, index, 2)
                if current is None and not ("prefix" in a and "suffix" in a):
                    raise CADOperationError("CAPABILITY_UNAVAILABLE",
                        "Current prefix/suffix cannot be read; supply both to avoid erasing one")
                wanted = [a.get("prefix", str(current[0]) if current else ""), a.get("suffix", str(current[1]) if current else "")]
                value.SetPSText(index, *wanted)
                checks.append(("prefix_suffix", lambda: _out_values(value.GetPSText, index, 2), wanted))
        elif mode == "dual_value":
            obj.DualValue = DUAL[a["display"]]
            checks.append(("DualValue", lambda: int(obj.DualValue), DUAL[a["display"]]))
        elif mode == "presentation":
            mapping = {"frame": ("ValueFrame", DIM_FRAME), "value_reference": ("ValueReference", VALUE_REFERENCE),
                       "value_orientation": ("ValueOrientation", VALUE_ORIENTATION),
                       "symbols_side": ("SymbolsSide", SYMBOLS_SIDE)}
            for key, (attr, table) in mapping.items():
                if key in a:
                    setattr(obj, attr, table[a[key]])
                    checks.append((attr, lambda attr=attr: int(getattr(obj, attr)), table[a[key]]))
            if "value_angle_deg" in a:
                # DrawingText/View angles are radians in CAA; the same convention is assumed here.
                obj.ValueAngle = math.radians(a["value_angle_deg"])
                checks.append(("ValueAngle", lambda: float(obj.ValueAngle), math.radians(a["value_angle_deg"])))
            for key, attr in (("half_dimension", "HalfDimMode"), ("foreshortened", "Forshortened")):
                if key in a:
                    setattr(obj, attr, a[key])
                    checks.append((attr, lambda attr=attr: bool(getattr(obj, attr)), a[key]))
        elif mode == "dimension_line":
            line = obj.GetDimLine()
            if "graphic_representation" in a:
                line.DimLineGraphRep = LINE_GRAPH[a["graphic_representation"]]
                checks.append(("DimLineGraphRep", lambda: int(line.DimLineGraphRep), LINE_GRAPH[a["graphic_representation"]]))
            for index, key in ((1, "first_symbol"), (2, "second_symbol")):
                if key in a:
                    line.SetSymbType(index, SYMBOLS[a[key]])
                    checks.append((key, lambda index=index: int(line.GetSymbType(index)), SYMBOLS[a[key]]))
        elif mode == "extension_lines":
            ext = obj.GetDimExtLine()
            for index in ((1, 2) if a["line"] == "both" else (a["line"],)):
                if "overrun_mm" in a:
                    ext.SetOverrun(index, a["overrun_mm"])
                    checks.append((f"overrun_{index}", lambda index=index: float(ext.GetOverrun(index)), a["overrun_mm"]))
                if "gap_mm" in a:
                    ext.SetGap(index, a["gap_mm"])
                    checks.append((f"gap_{index}", lambda index=index: float(ext.GetGap(index)), a["gap_mm"]))
                if "visible" in a:
                    ext.SetVisibility(index, a["visible"])
                    checks.append((f"visible_{index}", lambda index=index: bool(ext.GetVisibility(index)), a["visible"]))
        else:
            kind = mode.removeprefix("tolerance_")
            name = a.get("tolerance_name", {"numerical": "TOL_NUM2", "fit": "TOL_ALPHA1", "clear": ""}[kind])
            upper_text, lower_text = (a["upper_text"], a["lower_text"]) if kind == "fit" else ("", "")
            upper, lower = (a["upper_mm"], a["lower_mm"]) if kind == "numerical" else (0.0, 0.0)
            if kind == "numerical" and upper < lower:
                raise CADOperationError("INVALID_ARGUMENT", "upper_mm must be >= lower_mm")
            obj.SetTolerances(TOLERANCE_TYPES[kind], name, upper_text, lower_text, upper, lower, 0)
        result = self.update(sheet)
        verified = []
        for label, read, expected in checks:
            try:
                actual = read()
            except Exception as exc:
                unverified.append(f"{label}: {exc}")
                continue
            if actual is None:
                unverified.append(f"{label}: readback unavailable")
                continue
            if isinstance(expected, list):
                actual = [str(v) for v in actual]
                if actual != [str(v) for v in expected]:
                    raise CADOperationError("POSTCONDITION_FAILED", f"{label}: expected {expected!r}, read back {actual!r}")
            else:
                verify_equal(actual, expected, label)
            verified.append(label)
        if mode.startswith("tolerance_"):
            readback = read_dimension_properties(obj).get("tolerance")
            if readback is None:
                unverified.append("tolerance: GetTolerances readback unavailable")
            else:
                verify_equal(int(readback["type"]), TOLERANCE_TYPES[mode.removeprefix("tolerance_")], "Tolerance type")
                verified.append("tolerance_type")
        try:
            measured_after = float(obj.GetValue().Value)
        except Exception:
            measured_after = None
        if None not in (measured_before, measured_after) and abs(measured_after - measured_before) > 1e-9:
            raise CADOperationError("POSTCONDITION_FAILED",
                f"Measured value changed {measured_before} -> {measured_after} during a presentation edit; inspect it")
        return {**result, "handle": handle, "mode": mode, "verified": verified, "unverified": unverified,
                "measured_value": measured_after, "source_geometry_changed": False,
                "properties": read_dimension_properties(obj)}

    # ------------------------------------------------------------------ text / view
    def text_style(self, a):
        obj = self.obj(a["text_handle"], {"drawing_text"})
        sheet, _, _ = self.child_owner(obj, "drawing_text")
        keys = ("bold", "italic", "underline", "strike_through", "font_name", "size_mm", "justification", "wrapping_width_mm")
        if not any(k in a for k in keys):
            raise CADOperationError("INVALID_ARGUMENT", "Give at least one text property to change")
        self.changed(a["text_handle"])
        props = obj.TextProperties
        mapping = {"bold": ("Bold", bool), "italic": ("Italic", bool), "underline": ("Underline", bool),
                   "strike_through": ("StrikeThru", bool), "font_name": ("FontName", str), "size_mm": ("FontSize", float)}
        checks = []
        for key, (attr, convert) in mapping.items():
            if key in a:
                setattr(props, attr, a[key])
                checks.append((attr, lambda attr=attr, convert=convert: convert(getattr(props, attr)), a[key]))
        if "justification" in a:
            props.Justification = JUSTIFY[a["justification"]]
            checks.append(("Justification", lambda: int(props.Justification), JUSTIFY[a["justification"]]))
        props.Update()
        if "wrapping_width_mm" in a:
            obj.WrappingWidth = a["wrapping_width_mm"]
            checks.append(("WrappingWidth", lambda: float(obj.WrappingWidth), a["wrapping_width_mm"]))
        result = self.update(sheet)
        for label, read, expected in checks:
            verify_equal(read(), expected, label)
        return {**result, "handle": a["text_handle"], "verified": [c[0] for c in checks], "text": str(obj.Text)}

    def view_generation(self, a):
        view = self.obj(a["view_handle"], {"view"})
        sheet, _ = self.view_owner(view)
        keys = ("hidden_lines", "fillets", "color_inheritance", "points_projection")
        if not any(k in a for k in keys):
            raise CADOperationError("INVALID_ARGUMENT", "Give at least one generation property to change")
        if not view.IsGenerative():
            raise CADOperationError("INVALID_ARGUMENT", "Generation properties need a generative view")
        self.changed(a["view_handle"])
        gb = view.GenerativeBehavior
        expected = {}
        if "hidden_lines" in a:
            expected["HiddenLineMode"] = 1 if a["hidden_lines"] else 0  # CatHiddenLineMode
        if "fillets" in a:
            expected["FilletRepresentation"] = FILLETS[a["fillets"]]
        if "color_inheritance" in a:
            expected["ColorInheritanceMode"] = 1 if a["color_inheritance"] else 0
        if "points_projection" in a:
            expected["PointsProjectionMode"] = 1 if a["points_projection"] else 0
        for attr, value in expected.items():
            setattr(gb, attr, value)
        try:
            gb.Update()
        except Exception as exc:
            raise CADOperationError("UPDATE_FAILED", f"View generation update failed: {exc}") from exc
        result = self.update(sheet)
        for attr, value in expected.items():
            verify_equal(int(getattr(gb, attr)), value, attr)
        return {**result, "handle": a["view_handle"], "generation": {k: int(getattr(gb, k)) for k in expected},
                "warning": "On/off enum mapping 0/1 follows CAA; visually confirm hidden lines/fillets"}

    def generate_dimensions(self, a):
        sheet = self.obj(a["sheet_handle"], {"sheet"})
        self.sheet_owner(sheet)
        views = [view for _, view in members(sheet.Views)]
        before = [[d for _, d in members(view.Dimensions)] for view in views]
        self.changed(a["sheet_handle"])
        try:
            sheet.GenerateDimensions()
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", f"DrawingSheet.GenerateDimensions failed: {exc}") from exc
        result = self.update(sheet)
        created, per_view = [], []
        for view, old in zip(views, before):
            rows = []
            for _, dim in members(view.Dimensions):
                if any(same_object(dim, o) for o in old):
                    continue
                handle = self.state.mark_created(dim, "drawing_dimension")
                created.append(handle)
                row = {"handle": handle, **read_properties(dim, {"DimType": int})}
                try:
                    row["measured_value"] = float(dim.GetValue().Value)
                except Exception as exc:
                    row["measured_value"] = None
                    row["unavailable"] = str(exc)
                rows.append(row)
            per_view.append({"view_handle": self.state.register(view, "view"), "view_name": str(view.Name),
                             "new_dimensions": rows})
        if not created:
            raise CADOperationError("FEATURE_NO_EFFECT",
                "GenerateDimensions added no dimensions: the source may have no distance/length/angle/radius/diameter "
                "3D constraints, or they are already shown. Create typed dimensions instead")
        return {**result, "created": created, "views": per_view, "associative_to_3d": True,
                "warning": "Generated layout is CATIA's; reposition/clean explicitly and verify against the drawing spec"}

    # ------------------------------------------------------------------ BOM table
    def _bom_rows(self, root, scope, limit=2000):
        def children(value):
            try:
                return [c for _, c in members(value.Products)]
            except Exception:
                return []
        pending = [(c, 1, []) for c in reversed(children(root))]
        groups, references, visited = [], [], 0
        while pending:
            if visited >= limit:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", f"More than {limit} occurrences; BOM would be incomplete")
            value, depth, ancestors = pending.pop()
            if any(same_object(value, old) for old in ancestors):
                raise CADOperationError("INVALID_ASSEMBLY", "Occurrence cycle detected")
            visited += 1
            kids = children(value)
            if depth < 30:
                pending.extend((c, depth+1, [*ancestors, value]) for c in reversed(kids))
            elif kids:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", "Assembly deeper than 30 levels; BOM would be incomplete")
            if (scope == "leaf" and kids) or (scope == "top" and depth != 1):
                continue
            reference = value.ReferenceProduct
            index = next((i for i, r in enumerate(references) if same_object(r, reference)), None)
            if index is None:
                references.append(reference)
                data = read_properties(reference, {"PartNumber": str, "Nomenclature": str, "Revision": str,
                                                   "Definition": str, "DescriptionRef": str, "Source": int})
                groups.append({"part_number": data["PartNumber"], "nomenclature": data["Nomenclature"],
                               "revision": data["Revision"], "definition": data["Definition"],
                               "description": data["DescriptionRef"],
                               "source": SOURCE_LABELS.get(data["Source"], "" if data["Source"] is None else str(data["Source"])),
                               "quantity": 0})
                index = len(groups) - 1
            groups[index]["quantity"] += 1
        return groups, visited

    def bom_table(self, a):
        columns = a["columns"]
        if len(a["column_widths_mm"]) != len(columns) or ("headers" in a and len(a["headers"]) != len(columns)):
            raise CADOperationError("INVALID_ARGUMENT", "column_widths_mm and headers need one entry per column")
        view = self.obj(a["view_handle"], {"view"})
        sheet, _ = self.view_owner(view)
        source = self.state.documents.get(a["source_document_id"])
        documents = self.conn.app.Documents
        if source is None or not any(same_object(source, documents.Item(i)) for i in range(1, documents.Count + 1)):
            raise CADOperationError("STALE_REFERENCE", "Source document is no longer open; reread the workspace")
        if not str(source.Name).lower().endswith(".catproduct"):
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "BOM source must be a CATProduct")
        groups, visited = self._bom_rows(source.Product, a["scope"])
        if not groups:
            raise CADOperationError("INVALID_ARGUMENT", "The assembly has no occurrences in this scope")
        if len(groups) > 499:
            raise CADOperationError("INVALID_ARGUMENT", "More than 499 BOM rows do not fit one table")
        headers = a.get("headers") or [BOM_COLUMNS[c] for c in columns]
        cells = [list(headers)]
        for item, row in enumerate(groups, 1):
            values = {**row, "item": str(item), "quantity": str(row["quantity"])}
            cells.append(["" if values[c] is None else str(values[c]) for c in columns])
        self.changed(a["view_handle"])
        table = view.Tables.Add(*a["position_mm"], len(cells), len(columns), a["row_height_mm"], a["column_widths_mm"][0])
        handle = self.state.mark_created(table, "drawing_table")
        for index, width in enumerate(a["column_widths_mm"], 1):
            table.SetColumnSize(index, width)
        for r, values in enumerate(cells, 1):
            for c, text in enumerate(values, 1):
                if text:
                    table.SetCellString(r, c, text)
        result = self.update(sheet)
        verify_equal(int(table.NumberOfRows), len(cells), "BOM table rows")
        verify_equal(int(table.NumberOfColumns), len(columns), "BOM table columns")
        for r, values in enumerate(cells, 1):
            for c, text in enumerate(values, 1):
                if text:
                    verify_equal(str(table.GetCellString(r, c)), text, f"BOM cell {r},{c}")
        return {**result, "handle": handle, "rows": len(groups), "visited_occurrences": visited,
                "items": [{"item": i, "part_number": g["part_number"], "quantity": g["quantity"]}
                          for i, g in enumerate(groups, 1)],
                "associative": False, "source_modified": False,
                "warning": "Snapshot table: regenerate after assembly changes; equal PartNumbers of distinct references stay separate rows"}
