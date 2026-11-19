"""Offline contracts for typed dimensions, Properties edits, generated dimensions and BOM tables.

Doubles only: these do not establish native CATIA Drafting behavior on Windows.
"""
import math
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.runtime import CADOperationError
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.drafting_properties import DraftingPropertyTools
from tests.test_assembly_drawing_management import Collection, engineering


class Value:
    def __init__(self, measured):
        self.Value = measured
        self.precision, self.name = {1: 0.1}, {1: "NUM.DIMM"}
        self.bault, self.ps = {1: ["", "", "", ""]}, {1: ["", ""]}

    def GetFormatPrecision(self, i): return self.precision[i]
    def SetFormatPrecision(self, i, v): self.precision[i] = v
    def GetFormatName(self, i): return self.name[i]
    def SetFormatName(self, i, v): self.name[i] = v
    def GetBaultText(self, i): return tuple(self.bault[i])
    def SetBaultText(self, i, *v): self.bault[i] = list(v)
    def GetPSText(self, i): return tuple(self.ps[i])
    def SetPSText(self, i, *v): self.ps[i] = list(v)


class Dimension:
    def __init__(self, kind=5, measured=12.5):
        self.Name, self.DimType, self.DimStatus = "Dim.1", kind, 0
        self.DualValue = self.ValueFrame = self.ValueReference = self.ValueOrientation = self.SymbolsSide = 0
        self.ValueAngle, self.HalfDimMode, self.Forshortened = 0.0, False, False
        self.ValueAutoMode, self.IsClipped = True, False
        self.value = Value(measured)
        self.tolerance = (0, "", "", "", 0.0, 0.0, 0)
        self.line = NS(DimLineGraphRep=0, symbols={1: 2, 2: 2})
        self.line.SetSymbType = lambda i, t: self.line.symbols.__setitem__(i, t)
        self.line.GetSymbType = lambda i: self.line.symbols[i]
        self.ext = NS(values={})
        self.ext.SetOverrun = lambda i, v: self.ext.values.__setitem__(("o", i), v)
        self.ext.GetOverrun = lambda i: self.ext.values[("o", i)]
        self.ext.SetGap = lambda i, v: self.ext.values.__setitem__(("g", i), v)
        self.ext.GetGap = lambda i: self.ext.values[("g", i)]
        self.ext.SetVisibility = lambda i, v: self.ext.values.__setitem__(("v", i), v)
        self.ext.GetVisibility = lambda i: self.ext.values[("v", i)]

    def GetValue(self): return self.value
    def GetDimLine(self): return self.line
    def GetDimExtLine(self): return self.ext
    def GetTolerances(self): return self.tolerance

    def SetTolerances(self, *args):
        self.tolerance = args


def rig(dim=None, geometry_type=5):
    circle = NS(Name="Circle.1", GeometricType=geometry_type)
    line = NS(Name="Line.1", GeometricType=3)
    dim = dim or Dimension()
    dims = Collection()
    dims.Add = Mock(side_effect=lambda *a: dims.items.append(dim) or dim)
    dims.Add2 = Mock(side_effect=lambda *a: dims.items.append(dim) or dim)
    text = NS(Name="Text.1", Text="NOTE", WrappingWidth=0.0,
              TextProperties=NS(Bold=False, Italic=False, Underline=False, StrikeThru=False,
                                FontName="SSS1", FontSize=3.5, Justification=0, Update=Mock()))
    gb = NS(HiddenLineMode=0, FilletRepresentation=0, ColorInheritanceMode=0, PointsProjectionMode=0, Update=Mock())
    tables = Collection()
    view = NS(Name="Front view", Dimensions=dims, GeometricElements=Collection(circle, line),
              Texts=Collection(text), Tables=tables, GenerativeBehavior=gb, IsGenerative=lambda: True)
    sheet = NS(Name="Sheet.1", Views=Collection(view), Update=Mock())
    doc = NS(Name="Test.CATDrawing", Sheets=Collection(sheet))
    tools = DraftingPropertyTools(engineering(doc))
    reg = tools.state.register
    return NS(tools=tools, view=view, sheet=sheet, dim=dim, dims=dims, text=text, gb=gb, tables=tables,
              view_h=reg(view, "view"), circle_h=reg(circle, "drawing_geometry"), line_h=reg(line, "drawing_geometry"),
              text_h=reg(text, "drawing_text"), sheet_h=reg(sheet, "sheet"))


def dim_handle(r):
    r.dims.items.append(r.dim)
    return r.tools.state.register(r.dim, "drawing_dimension")


def test_schemas_are_valid_strict_and_never_offer_fake_values():
    server = CATIAMCPServer()
    try:
        for name in ("catia_drawing_dimension_typed", "catia_drawing_dimension_properties", "catia_drawing_text_style",
                     "catia_drawing_view_generation", "catia_drawing_generate_dimensions", "catia_drawing_bom_table"):
            schema = server._schemas[name]
            Draft202012Validator.check_schema(schema)
            assert {"document_id", "request_id", "expected_revision"} <= set(schema["required"])
            assert "fake" not in str(schema).lower()
        guards = {"document_id": "d", "request_id": "r", "expected_revision": 0}
        typed = Draft202012Validator(server._schemas["catia_drawing_dimension_typed"])
        assert typed.is_valid({**guards, "mode": "diameter", "view_handle": "v", "geometry_handles": ["c"], "expected_value": 20})
        assert not typed.is_valid({**guards, "mode": "diameter", "view_handle": "v", "geometry_handles": ["c"], "dimension_type": 9})
        assert not typed.is_valid({**guards, "mode": "radius", "view_handle": "v", "geometry_handles": ["c"], "direction_handle": "l"})
        props = Draft202012Validator(server._schemas["catia_drawing_dimension_properties"])
        assert props.is_valid({**guards, "mode": "value", "dimension_handle": "d", "prefix": "4x", "precision": 0.01})
        assert not props.is_valid({**guards, "mode": "value", "dimension_handle": "d", "frame": "circle"})
        assert props.is_valid({**guards, "mode": "presentation", "dimension_handle": "d", "frame": "rectangle"})
        assert not props.is_valid({**guards, "mode": "presentation", "dimension_handle": "d", "frame": "hexagon"})
    finally:
        server.worker.shutdown()


@pytest.mark.parametrize("mode,native", [("radius", 5), ("diameter", 9)])
def test_typed_radius_diameter_use_catdimtype_and_read_measured_value(mode, native):
    r = rig(Dimension(kind=native, measured=20.0))
    result = r.tools.typed_dimension({"mode": mode, "view_handle": r.view_h, "geometry_handles": [r.circle_h],
                                      "picked_points_mm": [[10, 0]], "expected_value": 20.0})
    args = r.dims.Add.call_args.args
    assert args[0] == native and args[2] == (10, 0) and args[3] == 3  # catDimAuto
    assert result["measured_value"] == 20.0 and result["handle"] in r.tools.state.created
    r.sheet.Update.assert_called_once()


def test_radius_on_a_line_is_rejected_before_any_write():
    r = rig()
    with pytest.raises(CADOperationError) as error:
        r.tools.typed_dimension({"mode": "radius", "view_handle": r.view_h, "geometry_handles": [r.line_h]})
    assert error.value.code == "WRONG_GEOMETRY_TYPE"
    r.dims.Add.assert_not_called()


def test_measured_value_or_type_mismatch_fails_and_leaves_dimension():
    r = rig(Dimension(kind=5, measured=19.0))
    with pytest.raises(CADOperationError) as error:
        r.tools.typed_dimension({"mode": "radius", "view_handle": r.view_h, "geometry_handles": [r.circle_h],
                                 "expected_value": 20.0})
    assert error.value.code == "POSTCONDITION_FAILED" and "never fake" in str(error.value)
    assert r.tools.state.created
    r2 = rig(Dimension(kind=0))
    with pytest.raises(CADOperationError):
        r2.tools.typed_dimension({"mode": "diameter", "view_handle": r2.view_h, "geometry_handles": [r2.circle_h]})


def test_angle_expected_value_accepts_degree_or_radian_readback():
    r = rig(Dimension(kind=4, measured=math.radians(30)), geometry_type=3)
    result = r.tools.typed_dimension({"mode": "angle", "view_handle": r.view_h,
                                      "geometry_handles": [r.circle_h, r.line_h], "expected_value": 30})
    assert result["dimension_type"] == "angle"


def test_distance_along_uses_add2_with_radians_and_view_reference():
    r = rig(Dimension(kind=0), geometry_type=3)
    r.tools.typed_dimension({"mode": "distance_along", "along_type": "distance", "direction_angle_deg": 90,
                             "view_handle": r.view_h, "geometry_handles": [r.circle_h, r.line_h]})
    args = r.dims.Add2.call_args.args
    assert args[0] == 0 and args[3] is None and math.isclose(args[4], math.pi / 2)


def test_value_properties_set_precision_and_texts_and_keep_measured_value():
    r = rig()
    handle = dim_handle(r)
    result = r.tools.dimension_properties({"mode": "value", "dimension_handle": handle, "precision": 0.01,
                                           "prefix": "4x", "after_text": "THRU"})
    assert r.dim.value.precision[1] == 0.01 and r.dim.value.ps[1] == ["4x", ""]
    assert r.dim.value.bault[1] == ["", "THRU", "", ""]
    assert set(result["verified"]) == {"precision", "bault_text", "prefix_suffix"}
    assert result["measured_value"] == 12.5 and not result["source_geometry_changed"]


def test_presentation_edit_that_changes_measured_value_is_a_failure():
    r = rig()
    handle = dim_handle(r)
    r.sheet.Update.side_effect = lambda: setattr(r.dim.value, "Value", 13.0)
    with pytest.raises(CADOperationError) as error:
        r.tools.dimension_properties({"mode": "presentation", "dimension_handle": handle, "frame": "rectangle"})
    assert error.value.code == "POSTCONDITION_FAILED"


def test_presentation_dual_line_and_extension_lines_map_enum_names():
    r = rig()
    h = dim_handle(r)
    r.tools.dimension_properties({"mode": "presentation", "dimension_handle": h, "frame": "rectangle",
                                  "value_orientation": "parallel", "symbols_side": "outside", "half_dimension": True})
    assert (r.dim.ValueFrame, r.dim.ValueOrientation, r.dim.SymbolsSide, r.dim.HalfDimMode) == (5, 2, 2, True)
    r.tools.dimension_properties({"mode": "dual_value", "dimension_handle": h, "display": "side_by_side"})
    assert r.dim.DualValue == 3
    r.tools.dimension_properties({"mode": "dimension_line", "dimension_handle": h, "first_symbol": "filled_arrow",
                                  "second_symbol": "slash"})
    assert r.dim.line.symbols == {1: 3, 2: 5}
    r.tools.dimension_properties({"mode": "extension_lines", "dimension_handle": h, "line": "both",
                                  "overrun_mm": 2, "gap_mm": 1, "visible": False})
    assert r.dim.ext.values[("o", 2)] == 2 and r.dim.ext.values[("v", 1)] is False


def test_empty_property_mode_is_rejected_before_writing():
    r = rig()
    h = dim_handle(r)
    with pytest.raises(CADOperationError):
        r.tools.dimension_properties({"mode": "presentation", "dimension_handle": h})
    r.sheet.Update.assert_not_called()


def test_tolerances_use_documented_argument_order_and_read_type_back():
    r = rig()
    h = dim_handle(r)
    r.tools.dimension_properties({"mode": "tolerance_numerical", "dimension_handle": h, "upper_mm": 0.1, "lower_mm": -0.05})
    assert r.dim.tolerance == (1, "TOL_NUM2", "", "", 0.1, -0.05, 0)
    r.tools.dimension_properties({"mode": "tolerance_fit", "dimension_handle": h, "upper_text": "H7", "lower_text": ""})
    assert r.dim.tolerance[:4] == (2, "TOL_ALPHA1", "H7", "")
    with pytest.raises(CADOperationError):
        r.tools.dimension_properties({"mode": "tolerance_numerical", "dimension_handle": h, "upper_mm": -1, "lower_mm": 1})


def test_text_style_and_view_generation_read_back():
    r = rig()
    result = r.tools.text_style({"text_handle": r.text_h, "bold": True, "size_mm": 5, "justification": "center",
                                 "wrapping_width_mm": 40})
    props = r.text.TextProperties
    assert props.Bold and props.FontSize == 5 and props.Justification == 1 and r.text.WrappingWidth == 40
    props.Update.assert_called_once()
    assert "Bold" in result["verified"]
    result = r.tools.view_generation({"view_handle": r.view_h, "hidden_lines": True, "fillets": "symbolic"})
    assert r.gb.HiddenLineMode == 1 and r.gb.FilletRepresentation == 2
    r.gb.Update.assert_called_once()
    with pytest.raises(CADOperationError):
        r.tools.view_generation({"view_handle": r.view_h})


def test_generate_dimensions_reports_only_new_dimensions_and_no_effect():
    r = rig()
    old = Dimension(kind=0)
    r.dims.items.append(old)
    new = Dimension(kind=9, measured=8.0)
    r.sheet.GenerateDimensions = Mock(side_effect=lambda: r.dims.items.append(new))
    result = r.tools.generate_dimensions({"sheet_handle": r.sheet_h})
    assert len(result["created"]) == 1
    assert result["views"][0]["new_dimensions"][0]["measured_value"] == 8.0
    r.sheet.GenerateDimensions = Mock()
    with pytest.raises(CADOperationError) as error:
        r.tools.generate_dimensions({"sheet_handle": r.sheet_h})
    assert error.value.code == "FEATURE_NO_EFFECT"


def product(name, reference=None, children=()):
    p = NS(Name=name, Products=Collection(*children))
    p.ReferenceProduct = reference if reference is not None else p
    return p


def test_bom_table_groups_by_reference_identity_and_reads_cells_back():
    r = rig()
    bolt = NS(PartNumber="BOLT-M8", Nomenclature="Bolt", Revision="A", Definition="", DescriptionRef="", Source=2)
    twin = NS(PartNumber="BOLT-M8", Nomenclature="Bolt", Revision="B", Definition="", DescriptionRef="", Source=2)
    plate = NS(PartNumber="PLATE", Nomenclature="Plate", Revision="", Definition="", DescriptionRef="", Source=1)
    root = product("Root", children=(product("Plate.1", plate), product("Bolt.1", bolt),
                                     product("Bolt.2", bolt), product("Bolt.3", twin)))
    source = NS(Name="Asm.CATProduct", Product=root)
    r.tools.conn.app = NS(Documents=Collection(source))
    source_id = r.tools.state.document_id(source)
    cells = {}

    def add(x, y, rows, cols, h, w):
        table = NS(Name="Table.1", NumberOfRows=rows, NumberOfColumns=cols, SetColumnSize=Mock(),
                   SetCellString=lambda a, b, t: cells.__setitem__((a, b), t),
                   GetCellString=lambda a, b: cells.get((a, b), ""))
        r.tables.items.append(table)
        return table

    r.tables.Add = Mock(side_effect=add)
    result = r.tools.bom_table({"view_handle": r.view_h, "source_document_id": source_id, "position_mm": [10, 10],
                                "columns": ["item", "part_number", "quantity", "source"], "scope": "leaf",
                                "row_height_mm": 6, "column_widths_mm": [10, 40, 12, 20]})
    assert [i["quantity"] for i in result["items"]] == [1, 2, 1]  # equal PartNumber, distinct refs stay separate
    assert cells[(1, 2)] == "Part Number" and cells[(3, 3)] == "2" and cells[(2, 4)] == "made"
    assert r.tables.Add.call_args.args[2:4] == (4, 4)


def test_bom_table_rejects_non_product_and_mismatched_widths():
    r = rig()
    part = NS(Name="P.CATPart")
    r.tools.conn.app = NS(Documents=Collection(part))
    pid = r.tools.state.document_id(part)
    base = {"view_handle": r.view_h, "source_document_id": pid, "position_mm": [0, 0], "columns": ["item"],
            "scope": "leaf", "row_height_mm": 5}
    with pytest.raises(CADOperationError):
        r.tools.bom_table({**base, "column_widths_mm": [10, 20]})
    with pytest.raises(CADOperationError) as error:
        r.tools.bom_table({**base, "column_widths_mm": [10]})
    assert error.value.code == "WRONG_DOCUMENT_TYPE"
