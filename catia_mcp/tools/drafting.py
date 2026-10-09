"""Explicit drawing views and annotations; no inferred hidden dimensions."""
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER, POSITIVE, tool
from catia_mcp.tools.operations import OperationTools, VECTOR, INTEGER, array, group, unit_vector

XY = array(NUMBER, 2, 2)
PROFILE = array(XY, 2)


class DraftingTools(OperationTools):
    def get_tool_definitions(self):
        return [
            tool("catia_new_drawing", "Create one new unsaved CATDrawing; existing documents remain untouched. Then read model state and domain objects before adding views.", {}),
            group("catia_drawing_dimension_series", "Composite chained or baseline dimensions. Separate ordinary dimensions, not native CumulateMode or coordinate dimensions. Geometry and label positions are view-local.",
                  {"chained": {}, "baseline": {}},
                  {"view_handle": HANDLE, "geometry_handles": array(HANDLE, 2), "picked_points_mm": array(XY, 2),
                   "label_positions_mm": array(XY), "dimension_type": {"type": "integer", "minimum": 0, "maximum": 20},
                   "line_representation": INTEGER, "subpart": INTEGER, "angle_behavior": INTEGER}),
            group("catia_drawing_view", "Create an associative drawing view on an explicit sheet. Source document must already be open. Vector frame is source model; positions are sheet mm. No automatic dimension inference.", {
                "front": {"source_document_id": HANDLE, "horizontal": VECTOR, "vertical": VECTOR},
                "isometric": {"source_document_id": HANDLE, "horizontal": VECTOR, "vertical": VECTOR},
                "unfolded": {"source_document_id": HANDLE, "horizontal": VECTOR, "vertical": VECTOR},
                "projection": {"parent_view_handle": HANDLE, "projection_type": {"enum": [0, 1, 2, 3, 4], "description": "right, left, top, bottom, rear respectively"}},
                "auxiliary": {"parent_view_handle": HANDLE, "start_mm": XY, "end_mm": XY, "side": {"enum": [0, 1]}},
                "section": {"parent_view_handle": HANDLE, "profile_mm": PROFILE,
                            "section_type": {"enum": ["SectionView", "SectionCut"]},
                            "profile_type": {"enum": ["Offset", "Aligned"]}, "side": {"enum": [0, 1]}},
                "detail": {"parent_view_handle": HANDLE, "center_mm": XY, "radius_mm": POSITIVE},
            }, {"sheet_handle": HANDLE, "name": HANDLE, "position_mm": XY, "scale": POSITIVE}),
            group("catia_drawing_edit", "Modify an exact view/sheet. Clipping and broken views are generative operations; coordinates are view-local mm.", {
                "new_sheet": {"name": HANDLE},
                "view_scale": {"view_handle": HANDLE, "scale": POSITIVE},
                "sheet_scale": {"sheet_handle": HANDLE, "scale": POSITIVE},
                "clip_circle": {"view_handle": HANDLE, "center_mm": XY, "radius_mm": POSITIVE},
                "clip_polygon": {"view_handle": HANDLE, "profile_mm": array(XY, 4)},
                "broken": {"view_handle": HANDLE, "extremities_mm": array(NUMBER, 8, 8), "direction": XY},
                "breakout": {"view_handle": HANDLE, "profile_mm": array(XY, 4),
                             "plane_origin_mm": VECTOR, "plane_first_direction": VECTOR, "plane_second_direction": VECTOR},
            }),
            group("catia_drawing_annotation", "Create text/leader, GDT, or non-associative title-block/center-mark primitives on an explicitly selected view. Not a native surface-finish or hatch constructor.", {
                "text": {"text": HANDLE, "position_mm": XY},
                "leader": {"text": HANDLE, "position_mm": XY, "head_mm": XY},
                "gdt": {"text": HANDLE, "position_mm": XY, "leader_mm": XY, "symbol": INTEGER},
                "center_mark": {"center_mm": XY, "half_size_mm": POSITIVE},
                "title_block": {"lines_mm": array(array(NUMBER, 4, 4)),
                                "texts": array({"type": "object", "properties": {"text": HANDLE, "position_mm": XY},
                                                "required": ["text", "position_mm"], "additionalProperties": False}, 0)},
            }, {"view_handle": HANDLE}),
            group("catia_drawing_dimension", "Create dimensions from exact drawing geometry handles or modify tolerances/position. Native enum integers must come from CATIA documentation; no GUI selection guessing.", {
                "create": {"view_handle": HANDLE, "geometry_handles": array(HANDLE, 1, 3),
                           "picked_points_mm": array(XY, 1, 3), "dimension_type": {"type": "integer", "minimum": 0, "maximum": 20}, "line_representation": INTEGER},
                "move": {"dimension_handle": HANDLE, "position_mm": XY, "subpart": INTEGER, "angle_behavior": INTEGER},
                "tolerance": {"dimension_handle": HANDLE, "tolerance_type": INTEGER, "tolerance_name": {"type": "string"},
                              "upper_text": {"type": "string"}, "lower_text": {"type": "string"},
                              "upper_value": NUMBER, "lower_value": NUMBER, "display_mode": INTEGER},
            }),
        ]

    def drawing(self):
        doc = self.conn.active_document
        try:
            doc.Sheets.Count
        except Exception as exc:
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "Active document must be a CATDrawing") from exc
        return doc

    def source(self, identity):
        doc = self.state.documents.get(identity)
        docs = self.conn.app.Documents
        if doc is None or not any(same_object(doc, docs.Item(i)) for i in range(1, docs.Count + 1)):
            raise CADOperationError("STALE_REFERENCE", "Source document is no longer open; reread domain objects")
        if same_object(doc, self.conn.active_document):
            raise CADOperationError("INVALID_ARGUMENT", "A drawing cannot be its own model source")
        if not str(doc.Name).lower().endswith((".catpart", ".catproduct")):
            raise CADOperationError("WRONG_DOCUMENT_TYPE", "View source must be a Part or Product")
        return doc

    def execute(self, name, a):
        if name == "catia_new_drawing":
            if self.engineering.sketcher._active_sketch is not None:
                raise CADOperationError("INVALID_ARGUMENT", "Close sketch before creating a drawing")
            doc = self.conn.app.Documents.Add("Drawing")
            self.state.mutation_started = True
            if not same_object(doc, self.conn.active_document):
                raise CADOperationError("DOCUMENT_MISMATCH", "New drawing did not become active")
            return {"ok": True, "document_id": self.state.document_id(doc), "name": str(doc.Name), "saved": False}
        self.drawing()
        if name == "catia_drawing_view":
            return self.view(a)
        if name == "catia_drawing_edit":
            return self.edit(a)
        if name == "catia_drawing_annotation":
            return self.annotation(a)
        if name == "catia_drawing_dimension_series":
            return self.series(a)
        return self.dimension(a)

    def series(self, a):
        handles, points = a["geometry_handles"], a["picked_points_mm"]
        if len(handles) != len(points) or len(a["label_positions_mm"]) != len(handles) - 1:
            raise CADOperationError("INVALID_ARGUMENT", "Series needs N points and N-1 label positions")
        view = self.obj(a["view_handle"], {"view"})
        geometry = [self.obj(h, {"drawing_geometry"}) for h in handles]
        if not all(any(same_object(g, view.GeometricElements.Item(i)) for i in range(1, view.GeometricElements.Count + 1)) for g in geometry):
            raise CADOperationError("INVALID_ARGUMENT", "All elements must belong to the target view")
        results = []
        for i in range(1, len(handles)):
            base = i - 1 if a["mode"] == "chained" else 0
            result = self.dimension({"mode": "create", "view_handle": a["view_handle"],
                                     "geometry_handles": [handles[base], handles[i]],
                                     "picked_points_mm": [points[base], points[i]],
                                     "dimension_type": a["dimension_type"], "line_representation": a["line_representation"]})
            self.dimension({"mode": "move", "dimension_handle": result["handle"],
                            "position_mm": a["label_positions_mm"][i-1], "subpart": a["subpart"], "angle_behavior": a["angle_behavior"]})
            results.append(result)
        return {"ok": True, "dimensions": results, "native_cumulated_dimensions": False}

    def view(self, a):
        sheet = self.obj(a["sheet_handle"], {"sheet"})
        parent = self.obj(a["parent_view_handle"], {"view"}) if "parent_view_handle" in a else None
        source = self.source(a["source_document_id"]) if "source_document_id" in a else None
        if source is not None:
            horizontal, vertical = unit_vector(a["horizontal"]), unit_vector(a["vertical"])
            if abs(sum(x * y for x, y in zip(horizontal, vertical))) > 1e-8:
                raise CADOperationError("INVALID_ARGUMENT", "View vectors must be perpendicular")
        if a["mode"] == "auxiliary" and a["start_mm"] == a["end_mm"]:
            raise CADOperationError("INVALID_ARGUMENT", "Auxiliary reference line has zero length")
        view = sheet.Views.Add(a["name"])
        h = self.state.mark_created(view, "view")
        gb, mode = view.GenerativeBehavior, a["mode"]
        if source is not None:
            gb.Document = source
            if mode == "front":
                gb.DefineFrontView(*horizontal, *vertical)
            elif mode == "isometric":
                gb.DefineIsometricView(*horizontal, *vertical)
            else:
                gb.DefineUnfoldedView(*horizontal, *vertical)
        else:
            pg = parent.GenerativeBehavior
            gb.Document = pg.Document
            if mode == "projection":
                gb.DefineProjectionView(pg, a["projection_type"])
            elif mode == "auxiliary":
                gb.DefineAuxiliaryView(*a["start_mm"], *a["end_mm"], a["side"], pg)
            elif mode == "section":
                gb.DefineSectionView(tuple(v for p in a["profile_mm"] for v in p), a["section_type"], a["profile_type"], a["side"], pg)
            else:
                gb.DefineCircularDetailView(*a["center_mm"], a["radius_mm"], pg)
        view.x, view.y = a["position_mm"]
        view.Scale = a["scale"]
        gb.Update()
        result = self.update(sheet)
        result.update(handle=h, name=str(view.Name), scale=float(view.Scale), position_mm=[float(view.x), float(view.y)],
                      warning="Projection, source links and dimension associativity need Windows visual/geometric verification")
        return result

    def edit(self, a):
        if a["mode"] == "new_sheet":
            sheet = self.drawing().Sheets.Add(a["name"])
            h = self.state.mark_created(sheet, "sheet")
            result = self.update(sheet)
            result["handle"] = h
            return result
        if a["mode"] == "sheet_scale":
            sheet = self.obj(a["sheet_handle"], {"sheet"})
            self.changed(a["sheet_handle"])
            sheet.Scale = a["scale"]
            result = self.update(sheet)
            result["scale"] = float(sheet.Scale)
            return result
        view = self.obj(a["view_handle"], {"view"})
        self.changed(a["view_handle"])
        if a["mode"] == "view_scale":
            view.Scale = a["scale"]
        elif a["mode"] == "clip_circle":
            view.GenerativeBehavior.DefineCircularClippingView(*a["center_mm"], a["radius_mm"])
        elif a["mode"] == "clip_polygon":
            if a["profile_mm"][0] != a["profile_mm"][-1]:
                raise CADOperationError("INVALID_ARGUMENT", "Clipping polygon must explicitly close")
            view.GenerativeBehavior.DefinePolygonalClippingView(tuple(v for p in a["profile_mm"] for v in p))
        elif a["mode"] == "breakout":
            if a["profile_mm"][0] != a["profile_mm"][-1]:
                raise CADOperationError("INVALID_ARGUMENT", "Breakout profile must explicitly close")
            u, v = unit_vector(a["plane_first_direction"]), unit_vector(a["plane_second_direction"])
            if abs(sum(x*y for x, y in zip(u, v))) > 1e-8:
                raise CADOperationError("INVALID_ARGUMENT", "Breakout plane axes must be perpendicular")
            # CAA help: Plane1[9] = origin, two vectors; Plane2[9] is unused.
            # https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html
            plane = (*a["plane_origin_mm"], *u, *v)
            view.GenerativeBehavior.DefineBreakout(tuple(x for p in a["profile_mm"] for x in p), plane, (0.0,) * 9)
        else:
            if sum(v * v for v in a["direction"]) < 1e-12:
                raise CADOperationError("INVALID_ARGUMENT", "Break direction is zero")
            if abs(a["direction"][0]) > 1e-10 and abs(a["direction"][1]) > 1e-10:
                raise CADOperationError("INVALID_ARGUMENT", "Broken-view direction must be horizontal or vertical")
            view.GenerativeBehavior.DefineBrokenView(tuple(a["extremities_mm"]), *a["direction"])
        result = self.update(view.GenerativeBehavior)
        result["scale"] = float(view.Scale)
        return result

    def annotation(self, a):
        view = self.obj(a["view_handle"], {"view"})
        self.changed(a["view_handle"])
        mode = a["mode"]
        if mode in {"text", "leader"}:
            obj = view.Texts.Add(a["text"], *a["position_mm"])
            self.state.mark_created(obj, "drawing_text")
            if mode == "leader":
                self.state.mark_created(obj.Leaders.Add(*a["head_mm"]), "drawing_leader")
        elif mode == "gdt":
            self.state.mark_created(view.GDTs.Add(*a["leader_mm"], *a["position_mm"], a["symbol"], a["text"]), "drawing_gdt")
        else:
            # SaveEdition is paired even on failure; these are explicitly non-associative primitives.
            view.Activate()
            try:
                if mode == "center_mark":
                    x, y = a["center_mm"]
                    d = a["half_size_mm"]
                    lines, texts = [[x-d, y, x+d, y], [x, y-d, x, y+d]], []
                else:
                    lines, texts = a["lines_mm"], a["texts"]
                for line in lines:
                    self.state.mark_created(view.Factory2D.CreateLine(*line), "drawing_geometry")
                for text in texts:
                    self.state.mark_created(view.Texts.Add(text["text"], *text["position_mm"]), "drawing_text")
            finally:
                view.SaveEdition()
        self.update_view_sheet(view)
        return {"ok": True, "warning": "Annotations created; inspect drawing layout and attachment. No native hatch/surface-finish support implied."}

    def update_view_sheet(self, view):
        sheets = self.drawing().Sheets
        for i in range(1, sheets.Count + 1):
            sheet = sheets.Item(i)
            if any(same_object(view, sheet.Views.Item(j)) for j in range(1, sheet.Views.Count + 1)):
                return self.update(sheet)
        raise CADOperationError("STALE_REFERENCE", "View no longer belongs to an open sheet")

    def dimension(self, a):
        if a["mode"] == "create":
            view = self.obj(a["view_handle"], {"view"})
            geometry = tuple(self.obj(h, {"drawing_geometry"}) for h in a["geometry_handles"])
            if len(geometry) != len(a["picked_points_mm"]):
                raise CADOperationError("INVALID_ARGUMENT", "One picked point is required per geometry element")
            # Handles from a different view must not be interpreted in this view's coordinates.
            members = view.GeometricElements
            if not all(any(same_object(g, members.Item(i)) for i in range(1, members.Count + 1)) for g in geometry):
                raise CADOperationError("INVALID_ARGUMENT", "Geometry must belong to the specified view")
            obj = view.Dimensions.Add(a["dimension_type"], geometry,
                                      tuple(v for p in a["picked_points_mm"] for v in p), a["line_representation"])
            h = self.state.mark_created(obj, "drawing_dimension")
        else:
            h = a["dimension_handle"]
            obj = self.obj(h, {"drawing_dimension"})
            self.changed(h)
            if a["mode"] == "move":
                obj.MoveValue(*a["position_mm"], a["subpart"], a["angle_behavior"])
            else:
                obj.SetTolerances(a["tolerance_type"], a["tolerance_name"], a["upper_text"], a["lower_text"], a["upper_value"], a["lower_value"], a["display_mode"])
        # DrawingDimension.Parent is its collection, so resolve the owning view explicitly.
        sheets = self.drawing().Sheets
        found = False
        for i in range(1, sheets.Count + 1):
            sheet = sheets.Item(i)
            for j in range(1, sheet.Views.Count + 1):
                candidate = sheet.Views.Item(j)
                if any(same_object(obj, candidate.Dimensions.Item(k)) for k in range(1, candidate.Dimensions.Count + 1)):
                    self.update(sheet)
                    found = True
                    break
            if found:
                break
        if not found:
            raise CADOperationError("STALE_REFERENCE", "Dimension no longer belongs to the active drawing")
        return {"ok": True, "handle": h, "dimension_status": int(obj.DimStatus),
                "warning": "Status is native CATIA enum, not automatic proof of correct attachment or units"}
