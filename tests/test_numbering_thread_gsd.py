"""Offline contracts for assembly numbering, Thread/Tap and new GSD modes (no CATIA)."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools
from catia_mcp.tools.assembly_numbering import AssemblyNumberingTools
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.part_features import PartFeatureTools, metric
from tests.test_assembly_drawing_management import Collection
from tests.test_operation_groups import fixture


def assembly(descriptions=("", "", "", "")):
    plate = NS(PartNumber="PLATE-10", Nomenclature="Plate")
    bolt = NS(PartNumber="BOLT-2", Nomenclature="Bolt")
    nut = NS(PartNumber="NUT-1", Nomenclature="Nut")
    occ = [NS(Name=n, ReferenceProduct=r, DescriptionInst=d)
           for n, r, d in zip(("Plate.1", "Bolt.1", "Bolt.2", "Nut.1"), (plate, bolt, bolt, nut), descriptions)]
    root = NS(Name="Asm", Products=Collection(*occ))
    doc = NS(Name="Asm.CATProduct", Product=root)
    conn = NS(active_document=doc, ensure_connected=lambda: None)
    state = SessionState(conn)
    state.bind()
    return AssemblyNumberingTools(EngineeringTools(conn, state, NS(_active_sketch=None))), occ


def test_numbering_shares_number_per_reference_and_reads_back():
    tools, occ = assembly()
    result = tools.execute("catia_assembly_numbering", {"mode": "apply", "order": "tree_order", "start": 1,
                                                        "step": 1, "overwrite_existing": False})
    assert [o.DescriptionInst for o in occ] == ["1", "2", "2", "3"]
    assert [i["quantity"] for i in result["items"]] == [1, 2, 1]
    assert result["written_occurrences"] == 4 and not result["component_files_changed"]
    assert "_obj" not in str(result) and "_groups" not in result


def test_numbering_part_number_order_prefix_and_preview_is_read_only():
    tools, occ = assembly()
    preview = tools.execute("catia_assembly_numbering_preview", {"order": "part_number", "start": 10, "step": 10,
                                                                 "prefix": "P"})
    assert [i["value"] for i in preview["items"]] == ["P10", "P20", "P30"]
    assert [i["part_number"] for i in preview["items"]] == ["BOLT-2", "NUT-1", "PLATE-10"]
    assert all(o.DescriptionInst == "" for o in occ) and not tools.state.mutation_started


def test_numbering_refuses_foreign_values_unless_overwrite_and_clear_keeps_them():
    tools, occ = assembly(("note", "", "", ""))
    with pytest.raises(CADOperationError):
        tools.execute("catia_assembly_numbering", {"mode": "apply", "order": "tree_order", "start": 1, "step": 1,
                                                   "overwrite_existing": False})
    assert occ[1].DescriptionInst == ""
    tools.execute("catia_assembly_numbering", {"mode": "apply", "order": "tree_order", "start": 1, "step": 1,
                                               "overwrite_existing": True})
    occ[3].DescriptionInst = "keep me"
    result = tools.execute("catia_assembly_numbering", {"mode": "clear"})
    assert [o.DescriptionInst for o in occ] == ["", "", "", "keep me"] and len(result["cleared"]) == 3


@pytest.mark.parametrize("text,expected", [("M10", (10, 1.5, "coarse")), ("M8x1", (8, 1, "fine")),
                                           ("M1.6", (1.6, .35, "coarse"))])
def test_metric_designations(text, expected):
    assert metric(text) == expected


@pytest.mark.parametrize("text", ["10", "M11", "M10x6", "M"])
def test_bad_metric_designation(text):
    with pytest.raises(CADOperationError):
        metric(text)


def thread_rig(face_radius):
    calls, part, state, engine = fixture()

    class Param:
        def __init__(self):
            self.Value = 0.0

        def ValuateFromString(self, text):
            self.Value = float(text.removesuffix("mm"))

        def ValueAsString(self):
            return f"{self.Value}mm"

    thread = NS(Name="Thread.1", Diameter=Param(), Pitch=Param(), Depth=Param(), Side=0,
                SetExplicitPolarity=Mock(), ReverseDirection=Mock())
    part.ShapeFactory = NS(AddNewThreadWithRef=Mock(return_value=thread))
    part.InWorkObject = None
    engine.conn.active_document.GetWorkbench = lambda _: NS(GetMeasurable=lambda ref: NS(GeometryName=4, Radius=face_radius))
    tools = PartFeatureTools(engine)
    args = {"mode": "metric", "designation": "M10", "body_handle": state.register(NS(Name="PartBody"), "body"),
            "lateral_face_handle": state.register(NS(Name="cyl"), "face"),
            "limit_face_handle": state.register(NS(Name="top"), "face"),
            "depth_mm": 15, "polarity": "thread", "hand": "right"}
    return tools, part, thread, args


def test_metric_thread_writes_iso_values_and_checks_fit():
    tools, part, thread, args = thread_rig(5.0)
    result = tools.execute("catia_thread", args)
    assert result["native"] == {"diameter_mm": 10, "pitch_mm": 1.5, "depth_mm": 15, "side": 0}
    assert result["fit_check"] == "passed"
    thread.SetExplicitPolarity.assert_called_once_with(0)


def test_tap_fit_uses_minor_diameter_and_mismatch_is_wrong_effect():
    tools, _, thread, args = thread_rig(4.25)  # Ø8.5 hole for M10 tap
    assert tools.execute("catia_thread", {**args, "polarity": "tap"})["fit_check"] == "passed"
    tools, _, _, args = thread_rig(3.0)  # Ø6 shaft cannot take M10
    with pytest.raises(CADOperationError) as error:
        tools.execute("catia_thread", args)
    assert error.value.code == "WRONG_GEOMETRY_EFFECT"


def test_thread_schema_is_strict():
    server = CATIAMCPServer()
    try:
        v = Draft202012Validator(server._schemas["catia_thread"])
        base = {"document_id": "d", "request_id": "r", "expected_revision": 0, "mode": "metric", "designation": "M6",
                "body_handle": "b", "lateral_face_handle": "l", "limit_face_handle": "t", "depth_mm": 10,
                "polarity": "tap", "hand": "right"}
        assert v.is_valid(base) and v.is_valid({**base, "reverse": True})
        assert not v.is_valid({**base, "pitch_mm": 1})
        assert "catia_assembly_numbering_preview" in server.read_tool_names()
    finally:
        server.worker.shutdown()


def test_polyline_inserts_points_radii_closure_and_reads_back():
    calls, part, state, engine = fixture()
    poly = NS(Name="Polyline.1", Closure=False, elements=[], SetRadius=Mock())
    poly.InsertElement = lambda p, i: poly.elements.insert(i - 1, p)
    part.HybridShapeFactory = NS(AddNewPolyline=Mock(return_value=poly))
    points = [state.register(NS(Name=f"P{i}"), "point") for i in range(4)]
    container = state.register(NS(Name="G", AppendHybridShape=lambda o: None), "geoset")
    poly.NumberOfElements = 4
    result = AdvancedGeometryTools(engine).execute("catia_wireframe_surface", {
        "mode": "polyline", "point_handles": points, "corner_radii_mm": [0, 2, 2, 0], "closed": True,
        "container_handle": container})
    assert len(poly.elements) == 4 and poly.Closure is True and result["points"] == 4
    assert [c.args for c in poly.SetRadius.call_args_list] == [(2, 2), (3, 2)]


def test_bisecting_and_three_point_circle_validate_distinct_inputs():
    calls, part, state, engine = fixture()
    part.HybridShapeFactory = NS(AddNewLineBisecting=Mock(return_value=NS(Name="Line.1")),
                                 AddNewCircle3Points=Mock(return_value=NS(Name="Circle.1")))
    container = state.register(NS(Name="G", AppendHybridShape=lambda o: None), "geoset")
    line = state.register(NS(Name="L"), "line")
    tools = AdvancedGeometryTools(engine)
    with pytest.raises(CADOperationError):
        tools.execute("catia_wireframe_surface", {"mode": "line_bisecting", "first_line_handle": line,
            "second_line_handle": line, "begin_mm": -5, "end_mm": 5, "reverse": False, "solution": 1,
            "container_handle": container})
    other = state.register(NS(Name="L2"), "line")
    result = tools.execute("catia_wireframe_surface", {"mode": "line_bisecting", "first_line_handle": line,
        "second_line_handle": other, "begin_mm": -5, "end_mm": 5, "reverse": False, "solution": 2,
        "container_handle": container})
    assert part.HybridShapeFactory.AddNewLineBisecting.call_args.args[2:] == (-5, 5, False, 2)
    assert state.resolve(result["handle"]).kind == "line"
    pts = [state.register(NS(Name=f"Q{i}"), "point") for i in range(3)]
    tools.execute("catia_wireframe_surface", {"mode": "circle_three_points", "point_handles": pts,
                                              "container_handle": container})
    part.HybridShapeFactory.AddNewCircle3Points.assert_called_once()
