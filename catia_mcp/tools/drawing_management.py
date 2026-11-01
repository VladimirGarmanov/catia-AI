"""Typed CAA drawing editing, tables and readback; no arbitrary COM gateway."""
import math

from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.drafting import DraftingTools, XY
from catia_mcp.tools.domain_support import members, member_index, read_properties, verify_equal
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE
from catia_mcp.tools.operations import BOOL, array, group

TEXT = {"type": "string"}
INDEX = {"type": "integer", "minimum": 1}
PAPER = {name: i for i, name in enumerate(("letter", "legal", "A0", "A1", "A2", "A3", "A4", "A", "B", "C", "D", "E", "F", "custom"))}
FRAMES = {name: i for i, name in enumerate(("none", "rectangle", "square", "circle", "scored_circle", "diamond", "triangle", "right_flag", "left_flag", "both_flags", "oblong", "ellipse"))}
ALIGN = {name: i for i, name in enumerate(("top_left", "middle_left", "bottom_left", "top_center", "middle_center", "bottom_center", "top_right", "middle_right", "bottom_right"))}
CELL = {"row": INDEX, "column": INDEX}
CHILD_COLLECTIONS = {"drawing_text": "Texts", "drawing_table": "Tables", "drawing_dimension": "Dimensions", "drawing_geometry": "GeometricElements"}


class DrawingManagementTools(DraftingTools):
    def get_tool_definitions(self):
        return [
            group("catia_drawing_inspect", "Read drawing layout, text, table cells or measured dimension parameters without Update or activation. Native unavailable fields are reported, not guessed.", {
                "overview": {"max_objects": {"type": "integer", "minimum": 1, "maximum": 2000}},
                "view": {"view_handle": HANDLE},
                "text": {"text_handle": HANDLE},
                "table": {"table_handle": HANDLE, "start_row": INDEX, "start_column": INDEX,
                          "row_count": {"type": "integer", "minimum": 1, "maximum": 100},
                          "column_count": {"type": "integer", "minimum": 1, "maximum": 50}},
                "dimension": {"dimension_handle": HANDLE},
            }, readonly=True),
            group("catia_drawing_sheet_setup", "Edit an exact sheet of the active CATDrawing. Paper dimensions in mm. No printing, saving or source-part modification.", {
                "format": {"paper_size": {"enum": [x for x in PAPER if x != "custom"]}, "orientation": {"enum": ["portrait", "landscape"]}},
                "custom_format": {"width_mm": POSITIVE, "height_mm": POSITIVE, "orientation": {"enum": ["portrait", "landscape"]}},
                "projection": {"projection": {"enum": ["first_angle", "third_angle"]}},
                "rename": {"name": HANDLE},
                "scale": {"scale": POSITIVE},
                **{mode: {} for mode in ("activate", "update", "force_update", "remove")},
            }, {"sheet_handle": HANDLE}),
            group("catia_drawing_view_modify", "Modify existing view placement, rotation, alignment and clipping. Position is view origin on sheet in mm; angles in degrees. No source-document writes. Update is not visual acceptance.", {
                "position": {"position_mm": XY}, "angle": {"angle_deg": NUMBER},
                "rename": {"name": HANDLE}, "lock": {"locked": BOOL},
                "frame": {"visible": BOOL}, "alignment": {"aligned": BOOL},
                **{mode: {} for mode in ("activate", "update", "force_update", "unclip", "unbreak", "unbreakout", "remove")},
            }, {"view_handle": HANDLE}),
            group("catia_drawing_text_edit", "Edit an exact existing drawing text. Position exposed in mm, converted to documented DrawingText.x/y meters. Font size uses native drawing font units (mm); angles in degrees. Does not overwrite dimension measurements.", {
                "content": {"text": TEXT}, "position": {"position_mm": XY},
                "angle": {"angle_deg": NUMBER},
                "font": {"font_name": HANDLE, "size_mm": POSITIVE},
                "frame": {"frame": {"enum": list(FRAMES)}},
                "leader": {"head_mm": XY}, "remove": {},
            }, {"text_handle": HANDLE}),
            group("catia_drawing_table", "Create and edit native DrawingTable. Indices are current one-based table cells, never geometry IDs. Row/column insertion uses before_index=0 to append. Removing rows/columns removes their contents. All positions/sizes in mm.", {
                "create": {"view_handle": HANDLE, "position_mm": XY, "rows": {"type": "integer", "minimum": 1, "maximum": 500},
                           "columns": {"type": "integer", "minimum": 1, "maximum": 100}, "row_height_mm": POSITIVE, "column_width_mm": POSITIVE},
                "cells": {"table_handle": HANDLE, "cells": array({"type": "object", "properties": {**CELL, "text": TEXT}, "required": [*CELL, "text"], "additionalProperties": False}, 1, 1000)},
                **{mode: {"table_handle": HANDLE, "before_index": {"type": "integer", "minimum": 0}} for mode in ("insert_row", "insert_column")},
                **{mode: {"table_handle": HANDLE, "index": INDEX} for mode in ("remove_row", "remove_column")},
                "row_size": {"table_handle": HANDLE, "index": INDEX, "size_mm": POSITIVE},
                "column_size": {"table_handle": HANDLE, "index": INDEX, "size_mm": POSITIVE},
                "merge": {"table_handle": HANDLE, **CELL, "rows": {"type": "integer", "minimum": 1, "maximum": 500}, "columns": {"type": "integer", "minimum": 1, "maximum": 100}},
                "unmerge": {"table_handle": HANDLE, **CELL},
                "alignment": {"table_handle": HANDLE, **CELL, "alignment": {"enum": list(ALIGN)}},
                "cell_font": {"table_handle": HANDLE, **CELL, "font_name": HANDLE, "size_mm": POSITIVE},
                "position": {"table_handle": HANDLE, "position_mm": XY},
                "angle": {"table_handle": HANDLE, "angle_deg": NUMBER},
                "remove": {"table_handle": HANDLE},
            }),
            group("catia_drawing_geometry", "Create non-associative interactive 2D primitives in an explicit drawing view, in view-local mm. Calls SaveEdition, not document Save. Existing model projections are not changed.", {
                "point": {"position_mm": XY},
                "line": {"start_mm": XY, "end_mm": XY},
                "circle": {"center_mm": XY, "radius_mm": POSITIVE},
                "arc": {"center_mm": XY, "radius_mm": POSITIVE, "start_deg": NUMBER, "end_deg": NUMBER},
                "rectangle": {"corner_mm": XY, "width_mm": POSITIVE, "height_mm": POSITIVE},
                "polyline": {"points_mm": array(XY, 2, 500), "closed": BOOL},
            }, {"view_handle": HANDLE, "construction": BOOL}),
            group("catia_drawing_dimension_edit", "Edit dimension presentation, not its measured value or source geometry. Retain associativity. For dimensional changes use source model constraints then update drawing.", {
                **{mode: {} for mode in ("restore_position", "unclip", "remove")},
                "clip": {"position_mm": XY, "kept_side": {"enum": [1, 2]}},
                "value_auto": {"enabled": BOOL},
            }, {"dimension_handle": HANDLE}),
        ]

    def execute(self, name, a):
        self.drawing()
        return {"catia_drawing_inspect": self.inspect, "catia_drawing_sheet_setup": self.sheet_setup,
                "catia_drawing_view_modify": self.view_modify, "catia_drawing_text_edit": self.text_edit,
                "catia_drawing_table": self.table, "catia_drawing_geometry": self.geometry,
                "catia_drawing_dimension_edit": self.dimension_edit}[name](a)

    def sheet_owner(self, sheet):
        return member_index(self.drawing().Sheets, sheet)

    def view_owner(self, view):
        for _, sheet in members(self.drawing().Sheets):
            for index, candidate in members(sheet.Views):
                if same_object(candidate, view):
                    return sheet, index
        raise CADOperationError("STALE_REFERENCE", "View no longer belongs to the active drawing")

    def child_owner(self, obj, kind):
        attr = CHILD_COLLECTIONS[kind]
        for _, sheet in members(self.drawing().Sheets):
            for _, view in members(sheet.Views):
                for index, candidate in members(getattr(view, attr)):
                    if same_object(candidate, obj):
                        return sheet, view, index
        raise CADOperationError("STALE_REFERENCE", "Object no longer belongs to the active drawing")

    def view_data(self, view):
        data = read_properties(view, {"Name": str, "xAxisData": float, "yAxisData": float,
                                      "Scale": float, "Angle": float, "ViewType": int,
                                      "LockStatus": bool, "FrameVisualization": bool})
        counts = {}
        for attr in ("Texts", "Tables", "Dimensions", "GeometricElements"):
            try:
                counts[attr] = int(getattr(view, attr).Count)
            except Exception as exc:
                counts[attr] = None
                data.setdefault("unavailable", {})[attr] = str(exc)
        data.update(counts=counts, position_unit="mm", angle_unit="rad")
        return data

    def inspect(self, a):
        mode = a["mode"]
        if mode == "overview":
            rows, truncated = [], False
            for _, sheet in members(self.drawing().Sheets):
                if len(rows) >= a["max_objects"]:
                    truncated = True
                    break
                h = self.state.register(sheet, "sheet")
                rows.append({"handle": h, "kind": "sheet", **read_properties(sheet, {
                    "Name": str, "Scale": float, "PaperSize": int, "Orientation": int, "ProjectionMethod": int})})
                for _, view in members(sheet.Views):
                    if len(rows) >= a["max_objects"]:
                        truncated = True
                        break
                    rows.append({"handle": self.state.register(view, "view"), "kind": "view", "parent": h, **self.view_data(view)})
            return {"ok": True, "objects": rows, "truncated": truncated}
        if mode == "view":
            obj = self.obj(a["view_handle"], {"view"})
            self.view_owner(obj)
            return {"ok": True, **self.view_data(obj)}
        kind = {"text": "drawing_text", "table": "drawing_table", "dimension": "drawing_dimension"}[mode]
        obj = self.obj(a[f"{mode}_handle"], {kind})
        self.child_owner(obj, kind)
        if mode == "text":
            data = read_properties(obj, {"Text": str, "x": float, "y": float, "Angle": float, "FrameType": int})
            data["position_mm"] = [data[c] * 1000 if data[c] is not None else None for c in ("x", "y")]
            data["native_position_unit"] = "m per CAA DrawingText.x/y contract; validate on installed release"
            return {"ok": True, **data}
        if mode == "table":
            r0, c0 = a["start_row"], a["start_column"]
            self.cell_bounds(obj, r0, c0)
            end_row = min(int(obj.NumberOfRows), r0 + a["row_count"] - 1)
            end_col = min(int(obj.NumberOfColumns), c0 + a["column_count"] - 1)
            cells = [{"row": r, "column": c, "text": str(obj.GetCellString(r, c))}
                     for r in range(r0, end_row + 1) for c in range(c0, end_col + 1)]
            return {"ok": True, "cells": cells, "rows": int(obj.NumberOfRows), "columns": int(obj.NumberOfColumns),
                    "returned_range": [r0, c0, end_row, end_col], "position_mm": [float(obj.x), float(obj.y)],
                    "angle_rad": float(obj.Angle)}
        parameters = []
        for _, parameter in members(obj.Parameters):
            parameters.append({"name": str(parameter.Name), "value_with_unit": str(parameter.ValueAsString())})
        return {"ok": True, "parameters": parameters, **read_properties(obj, {"DimType": int, "DimStatus": int,
                "IsClipped": bool, "ValueAutoMode": bool}), "warning": "Measured drawing values are not source-model constraints"}

    def sheet_setup(self, a):
        sheet = self.obj(a["sheet_handle"], {"sheet"})
        index = self.sheet_owner(sheet)
        sheets = self.drawing().Sheets
        mode, checks = a["mode"], {}
        if mode == "remove" and sheets.Count <= 1:
            raise CADOperationError("INVALID_ARGUMENT", "Cannot remove the only sheet")
        if mode == "rename" and any(str(s.Name) == a["name"] and not same_object(s, sheet) for _, s in members(sheets)):
            raise CADOperationError("INVALID_ARGUMENT", "Sheet name already exists")
        count = int(sheets.Count)
        self.changed(a["sheet_handle"])
        if mode in {"format", "custom_format"}:
            checks = {"PaperSize": PAPER[a["paper_size"]] if mode == "format" else PAPER["custom"],
                      "Orientation": 0 if a["orientation"] == "portrait" else 1}
            sheet.PaperSize = checks["PaperSize"]
            sheet.Orientation = checks["Orientation"]
            if mode == "custom_format":
                sheet.SetPaperWidth(a["width_mm"])
                sheet.SetPaperHeight(a["height_mm"])
        elif mode == "projection":
            checks["ProjectionMethod"] = 0 if a["projection"] == "first_angle" else 1
            sheet.ProjectionMethod = checks["ProjectionMethod"]
        elif mode == "rename":
            sheet.Name = checks.setdefault("Name", a["name"])
        elif mode == "scale":
            sheet.Scale = checks.setdefault("Scale", a["scale"])
        elif mode == "activate":
            sheet.Activate()
        elif mode == "remove":
            sheets.Remove(index)
            self.state.objects.pop(a["sheet_handle"], None)
            result = self.update(self.drawing())
            verify_equal(int(sheets.Count), count - 1, "Sheet count")
            return {**result, "removed_handle": a["sheet_handle"]}
        elif mode == "force_update":
            sheet.ForceUpdate()
        result = self.update(sheet)
        for field, expected in checks.items():
            verify_equal(getattr(sheet, field), expected, field)
        if mode == "custom_format":
            verify_equal(float(sheet.GetPaperWidth()), a["width_mm"], "Paper width")
            verify_equal(float(sheet.GetPaperHeight()), a["height_mm"], "Paper height")
        if mode == "activate" and not same_object(sheets.ActiveSheet, sheet):
            raise CADOperationError("POSTCONDITION_FAILED", "Requested sheet is not active")
        return {**result, "properties": read_properties(sheet, {"Name": str, "PaperSize": int, "Orientation": int, "ProjectionMethod": int, "Scale": float})}

    def view_modify(self, a):
        view = self.obj(a["view_handle"], {"view"})
        sheet, index = self.view_owner(view)
        mode, checks = a["mode"], {}
        if mode == "remove" and index <= 2:
            raise CADOperationError("INVALID_ARGUMENT", "Main and background views cannot be removed")
        self.changed(a["view_handle"])
        if mode == "position":
            checks = dict(zip(("xAxisData", "yAxisData"), a["position_mm"]))
        elif mode == "angle":
            checks = {"Angle": math.radians(a["angle_deg"])}
        elif mode == "rename":
            checks = {"Name": a["name"]}
        elif mode == "lock":
            checks = {"LockStatus": a["locked"]}
        elif mode == "frame":
            checks = {"FrameVisualization": a["visible"]}
        elif mode == "alignment":
            if a["aligned"]:
                view.AlignedWithReferenceView()
            else:
                view.UnAlignedWithReferenceView()
        elif mode == "activate":
            view.Activate()
        elif mode == "remove":
            count = int(sheet.Views.Count)
            sheet.Views.Remove(index)
            self.state.objects.pop(a["view_handle"], None)
            result = self.update(sheet)
            verify_equal(int(sheet.Views.Count), count - 1, "View count")
            return {**result, "removed_handle": a["view_handle"]}
        elif mode != "update":
            if not view.IsGenerative():
                raise CADOperationError("INVALID_ARGUMENT", "This mode requires a generative view")
            method = {"force_update": "ForceUpdate", "unclip": "UnClip", "unbreak": "UnBreak", "unbreakout": "UnBreakout"}[mode]
            getattr(view.GenerativeBehavior, method)()
        for field, value in checks.items():
            setattr(view, field, value)
        result = self.update(sheet)
        for field, value in checks.items():
            verify_equal(getattr(view, field), value, field)
        if mode == "activate" and not same_object(sheet.Views.ActiveView, view):
            raise CADOperationError("POSTCONDITION_FAILED", "Requested view is not active")
        return {**result, "view": self.view_data(view)}

    def remove_child(self, handle, kind):
        obj = self.obj(handle, {kind})
        sheet, view, index = self.child_owner(obj, kind)
        collection = getattr(view, CHILD_COLLECTIONS[kind])
        count = int(collection.Count)
        self.changed(handle)
        collection.Remove(index)
        self.state.objects.pop(handle, None)
        result = self.update(sheet)
        verify_equal(int(collection.Count), count - 1, "Collection count")
        return {**result, "removed_handle": handle}

    def text_edit(self, a):
        if a["mode"] == "remove":
            return self.remove_child(a["text_handle"], "drawing_text")
        obj = self.obj(a["text_handle"], {"drawing_text"})
        sheet, _, _ = self.child_owner(obj, "drawing_text")
        mode, checks = a["mode"], {}
        self.changed(a["text_handle"])
        if mode == "content":
            checks = {"Text": a["text"]}
        elif mode == "position":
            checks = dict(zip(("x", "y"), (v / 1000 for v in a["position_mm"])))
        elif mode == "angle":
            checks = {"Angle": math.radians(a["angle_deg"])}
        elif mode == "font":
            obj.SetFontName(0, 0, a["font_name"])
            obj.SetFontSize(0, 0, a["size_mm"])
        elif mode == "frame":
            obj.ActivateFrame(FRAMES[a["frame"]])
            checks = {"FrameType": FRAMES[a["frame"]]}
        elif mode == "leader":
            self.state.mark_created(obj.Leaders.Add(*a["head_mm"]), "drawing_leader")
        for field, value in checks.items():
            if field != "FrameType":  # FrameType is read-only; ActivateFrame writes it.
                setattr(obj, field, value)
        result = self.update(sheet)
        for field, value in checks.items():
            verify_equal(getattr(obj, field), value, field)
        if mode == "font":
            verify_equal(str(obj.GetFontName(0, 0)), a["font_name"], "Font")
            verify_equal(float(obj.GetFontSize(0, 0)), a["size_mm"], "Font size")
        return {**result, "text": str(obj.Text), "handle": a["text_handle"]}

    @staticmethod
    def cell_bounds(table, row, column):
        if not 1 <= row <= int(table.NumberOfRows) or not 1 <= column <= int(table.NumberOfColumns):
            raise CADOperationError("INVALID_ARGUMENT", "Table cell is outside the current row/column range")

    def table(self, a):
        mode = a["mode"]
        if mode == "create":
            view = self.obj(a["view_handle"], {"view"})
            sheet, _ = self.view_owner(view)
            self.changed(a["view_handle"])
            obj = view.Tables.Add(*a["position_mm"], a["rows"], a["columns"], a["row_height_mm"], a["column_width_mm"])
            handle = self.state.mark_created(obj, "drawing_table")
            result = self.update(sheet)
            verify_equal(int(obj.NumberOfRows), a["rows"], "Table rows")
            verify_equal(int(obj.NumberOfColumns), a["columns"], "Table columns")
            return {**result, "handle": handle, "rows": int(obj.NumberOfRows), "columns": int(obj.NumberOfColumns)}
        if mode == "remove":
            return self.remove_child(a["table_handle"], "drawing_table")
        handle = a["table_handle"]
        obj = self.obj(handle, {"drawing_table"})
        sheet, _, _ = self.child_owner(obj, "drawing_table")
        rows, columns = int(obj.NumberOfRows), int(obj.NumberOfColumns)
        if mode == "cells":
            for cell in a["cells"]:
                self.cell_bounds(obj, cell["row"], cell["column"])
            if len({(c["row"], c["column"]) for c in a["cells"]}) != len(a["cells"]):
                raise CADOperationError("INVALID_ARGUMENT", "Each cell may be written only once per call")
        if "row" in a:
            self.cell_bounds(obj, a["row"], a["column"])
        if mode == "merge":
            self.cell_bounds(obj, a["row"] + a["rows"] - 1, a["column"] + a["columns"] - 1)
        if "index" in a or "before_index" in a:
            limit = rows if "row" in mode else columns
            index = a.get("index", a.get("before_index"))
            if index > limit or index < (0 if mode.startswith("insert_") else 1):
                raise CADOperationError("INVALID_ARGUMENT", "Table index out of bounds; insertion 0 appends")
            if mode.startswith("remove_") and limit == 1:
                raise CADOperationError("INVALID_ARGUMENT", "Cannot remove the last table row/column")
        self.changed(handle)
        if mode == "cells":
            for cell in a["cells"]:
                obj.SetCellString(cell["row"], cell["column"], cell["text"])
        elif mode in {"insert_row", "insert_column", "remove_row", "remove_column"}:
            method = {"insert_row": "AddRow", "insert_column": "AddColumn", "remove_row": "RemoveRow", "remove_column": "RemoveColumn"}[mode]
            getattr(obj, method)(index)
        elif mode in {"row_size", "column_size"}:
            getattr(obj, "SetRowSize" if mode == "row_size" else "SetColumnSize")(index, a["size_mm"])
        elif mode == "merge":
            obj.MergeCells(a["row"], a["column"], a["rows"], a["columns"])
        elif mode == "unmerge":
            obj.UnMergeCells(a["row"], a["column"])
        elif mode == "alignment":
            obj.SetCellAlignment(a["row"], a["column"], ALIGN[a["alignment"]])
        elif mode == "cell_font":
            text = obj.GetCellObject(a["row"], a["column"])
            text.SetFontName(0, 0, a["font_name"])
            text.SetFontSize(0, 0, a["size_mm"])
        elif mode == "position":
            obj.x, obj.y = a["position_mm"]
        else:
            obj.Angle = math.radians(a["angle_deg"])
        result = self.update(sheet)
        if mode == "cells":
            for cell in a["cells"]:
                verify_equal(str(obj.GetCellString(cell["row"], cell["column"])), cell["text"], "Table cell")
        elif mode in {"insert_row", "remove_row"}:
            verify_equal(int(obj.NumberOfRows), rows + (1 if mode == "insert_row" else -1), "Table rows")
        elif mode in {"insert_column", "remove_column"}:
            verify_equal(int(obj.NumberOfColumns), columns + (1 if mode == "insert_column" else -1), "Table columns")
        elif mode in {"row_size", "column_size"}:
            actual = getattr(obj, "GetRowSize" if mode == "row_size" else "GetColumnSize")(index)
            verify_equal(float(actual), a["size_mm"], "Table size")
        elif mode == "alignment":
            verify_equal(int(obj.GetCellAlignment(a["row"], a["column"])), ALIGN[a["alignment"]], "Cell alignment")
        elif mode == "cell_font":
            verify_equal(str(text.GetFontName(0, 0)), a["font_name"], "Cell font")
            verify_equal(float(text.GetFontSize(0, 0)), a["size_mm"], "Cell font size")
        elif mode == "position":
            for actual, expected in zip((float(obj.x), float(obj.y)), a["position_mm"]):
                verify_equal(actual, expected, "Table position")
        elif mode == "angle":
            verify_equal(float(obj.Angle), math.radians(a["angle_deg"]), "Table angle")
        return {**result, "handle": handle, "rows": int(obj.NumberOfRows), "columns": int(obj.NumberOfColumns),
                "warning": "Merged-cell topology and final layout require CATIA inspection"}

    def geometry(self, a):
        view = self.obj(a["view_handle"], {"view"})
        sheet, _ = self.view_owner(view)
        mode, lines = a["mode"], []
        if mode == "line":
            lines = [(a["start_mm"], a["end_mm"])]
        elif mode == "rectangle":
            x, y = a["corner_mm"]
            w, h = a["width_mm"], a["height_mm"]
            points = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
            lines = list(zip(points, points[1:]))
        elif mode == "polyline":
            points = list(a["points_mm"])
            if a["closed"] and points[-1] != points[0]:
                points.append(points[0])
            lines = list(zip(points, points[1:]))
        if any(p == q for p, q in lines):
            raise CADOperationError("INVALID_ARGUMENT", "A line segment has zero length")
        if mode == "arc" and not 0 < a["end_deg"] - a["start_deg"] < 360:
            raise CADOperationError("INVALID_ARGUMENT", "Arc requires 0 < end_deg - start_deg < 360, counterclockwise")
        self.changed(a["view_handle"])
        view.Activate()
        handles = []
        def created(obj):
            handles.append(self.state.mark_created(obj, "drawing_geometry"))
            obj.Construction = a["construction"]
            verify_equal(bool(obj.Construction), a["construction"], "Construction")
        try:
            factory = view.Factory2D
            for start, end in lines:
                created(factory.CreateLine(*start, *end))
            if mode == "point":
                created(factory.CreatePoint(*a["position_mm"]))
            elif mode == "circle":
                created(factory.CreateClosedCircle(*a["center_mm"], a["radius_mm"]))
            elif mode == "arc":
                created(factory.CreateCircle(*a["center_mm"], a["radius_mm"], math.radians(a["start_deg"]), math.radians(a["end_deg"])))
        finally:
            view.SaveEdition()
        return {**self.update(sheet), "handles": handles, "associative_to_3d": False}

    def dimension_edit(self, a):
        if a["mode"] == "remove":
            return self.remove_child(a["dimension_handle"], "drawing_dimension")
        obj = self.obj(a["dimension_handle"], {"drawing_dimension"})
        sheet, _, _ = self.child_owner(obj, "drawing_dimension")
        self.changed(a["dimension_handle"])
        mode = a["mode"]
        if mode == "restore_position":
            obj.RestoreValuePosition()
        elif mode == "unclip":
            obj.Unclip()
        elif mode == "clip":
            obj.SetClip(*a["position_mm"], a["kept_side"])
        else:
            obj.ValueAutoMode = a["enabled"]
        result = self.update(sheet)
        if mode in {"clip", "unclip"}:
            verify_equal(bool(obj.IsClipped), mode == "clip", "Dimension clipping")
        if mode == "value_auto":
            verify_equal(bool(obj.ValueAutoMode), a["enabled"], "Automatic value placement")
        return {**result, "dimension_status": int(obj.DimStatus), "source_geometry_changed": False}
