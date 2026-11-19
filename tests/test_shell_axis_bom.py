"""Offline contracts for Shell, native Axis lines and configured BOM reports (no CATIA)."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools
from catia_mcp.tools.domains import DomainTools
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.part_design import PartDesignTools
from tests.test_operation_groups import fixture


def shell_rig(volumes=(1e-3, 6e-4), faces_removed=None):
    volumes = list(volumes)
    face_refs = [NS(Name="Face1"), NS(Name="Face2")]
    added = []

    class Faces:
        @property
        def Count(self):
            return len(added) if faces_removed is None else faces_removed

    shell = NS(Name="Shell.1", InternalThickness=NS(Value=0.0), ExternalThickness=NS(Value=0.0),
               FacesToRemove=Faces())

    def add_shell(face, inner, outer):
        added.append(face)
        shell.InternalThickness.Value, shell.ExternalThickness.Value = inner, outer
        return shell

    def add_face(face):
        added.append(face)

    shell.AddFaceToRemove = Mock(side_effect=add_face)
    part = NS(ShapeFactory=NS(AddNewShell=Mock(side_effect=add_shell)), InWorkObject=None,
              UpdateObject=lambda o: None, Update=lambda: None, IsUpToDate=lambda o: True,
              CreateReferenceFromObject=lambda o: o)
    body = NS(Name="PartBody")

    def measure(_ref):
        return NS(Volume=volumes.pop(0) if volumes else 0)

    doc = NS(Name="T.CATPart", GetWorkbench=lambda _: NS(GetMeasurable=measure))
    conn = NS(ensure_connected=lambda: None, get_active_part=lambda: part, get_active_part_body=lambda: body,
              active_document=doc, refresh_display=lambda: None)
    state = SessionState(conn)
    conn.session = state
    state.bind()
    handles = [state.register(NS(Name=f"f{i}"), "face", reference=ref) for i, ref in enumerate(face_refs)]
    return PartDesignTools(conn), part, shell, handles, face_refs, added


def test_shell_removes_multiple_faces_in_order_with_inner_and_outer_thickness():
    tools, part, shell, handles, refs, added = shell_rig()
    result = tools.execute("catia_shell", {"thickness": 2, "outer_thickness": 0.5, "selection_handles": handles})
    part.ShapeFactory.AddNewShell.assert_called_once_with(refs[0], 2, 0.5)
    assert added == refs and result["native"]["faces_removed"] == 2
    assert result["native"]["inner_thickness_mm"] == 2 and result["effect"] == "material_removed"


@pytest.mark.parametrize("volumes,code", [((1e-3, 1e-3), "FEATURE_NO_EFFECT"), ((1e-3, 2e-3), "WRONG_GEOMETRY_EFFECT")])
def test_shell_volume_effect_is_classified_and_feature_reported(volumes, code):
    tools, _, _, handles, _, _ = shell_rig(volumes)
    with pytest.raises(CADOperationError) as error:
        tools.execute("catia_shell", {"thickness": 2, "selection_handles": handles})
    assert error.value.code == code
    assert tools.conn.session.created


def test_shell_rejects_bad_thickness_and_face_count_mismatch_before_or_after_update():
    tools, part, *_ = shell_rig()
    with pytest.raises(ValueError):
        tools.execute("catia_shell", {"thickness": 0, "outer_thickness": 0})
    with pytest.raises(ValueError):
        tools.execute("catia_shell", {"thickness": -1})
    part.ShapeFactory.AddNewShell.assert_not_called()
    tools, _, _, handles, _, _ = shell_rig(faces_removed=1)
    with pytest.raises(CADOperationError) as error:
        tools.execute("catia_shell", {"thickness": 1, "selection_handles": handles})
    assert error.value.code == "POSTCONDITION_FAILED"


@pytest.mark.parametrize("kind,expected_type", [("face", 1), ("edge", 3)])
def test_axis_line_uses_native_axis_feature_and_measures_line(kind, expected_type):
    calls, part, state, engine = fixture()
    axis = NS(Name="Axis.1", AxisLineType=0)
    part.HybridShapeFactory = NS(AddNewAxisLine=Mock(return_value=axis))
    engine.conn.active_document.GetWorkbench = lambda _: NS(GetMeasurable=lambda ref: NS(GeometryName=10))
    container = NS(Name="G", AppendHybridShape=lambda obj: calls.append("append"))
    source = NS(Name="Bore")
    result = AdvancedGeometryTools(engine).execute("catia_wireframe_surface", {
        "mode": "axis_line", "element_handle": state.register(source, kind),
        "container_handle": state.register(container, "geoset")})
    part.HybridShapeFactory.AddNewAxisLine.assert_called_once_with(source)
    assert axis.AxisLineType == expected_type and result["axis_measurement"]["status"] == "line"
    assert state.resolve(result["handle"]).kind == "line"


def test_axis_line_that_does_not_measure_as_line_is_a_wrong_effect():
    calls, part, state, engine = fixture()
    part.HybridShapeFactory = NS(AddNewAxisLine=Mock(return_value=NS(Name="Axis.1", AxisLineType=0)))
    engine.conn.active_document.GetWorkbench = lambda _: NS(GetMeasurable=lambda ref: NS(GeometryName=11))
    with pytest.raises(CADOperationError) as error:
        AdvancedGeometryTools(engine).execute("catia_wireframe_surface", {
            "mode": "axis_line", "element_handle": state.register(NS(Name="c"), "face"),
            "container_handle": state.register(NS(Name="G", AppendHybridShape=lambda o: None), "geoset")})
    assert error.value.code == "WRONG_GEOMETRY_EFFECT"


def bom_rig(tmp_path, write=True):
    convertor = NS(SetCurrentFormat=Mock(), SetSecondaryFormat=Mock())

    def printer(kind, path, product):
        if write:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("Part Number\tQuantity\nBOLT\t4\n")

    convertor.Print = Mock(side_effect=printer)
    root = NS(Name="Root", GetItem=Mock(return_value=convertor))
    doc = NS(Name="A.CATProduct", Product=root)
    conn = NS(active_document=doc, ensure_connected=lambda: None)
    state = SessionState(conn)
    state.bind()
    tools = DomainTools(EngineeringTools(conn, state, NS(_active_sketch=None)))
    tools.product = lambda: root  # the tool binds the active root product
    return tools, root, convertor, state.register(root, "product")


def test_bom_custom_sets_columns_and_prints_requested_format(tmp_path):
    tools, root, convertor, handle = bom_rig(tmp_path)
    path = tmp_path / "bom.txt"
    result = tools.bom_custom(root, {"file_path": str(path), "format": "text", "report": "bill_of_materials",
                                     "columns": ["Part Number", "Quantity", "Revision"],
                                     "summary_columns": ["Part Number", "Quantity"], "allow_overwrite": False})
    root.GetItem.assert_called_once_with("BillOfMaterial")
    convertor.SetCurrentFormat.assert_called_once_with(("Part Number", "Quantity", "Revision"))
    assert convertor.Print.call_args.args[0] == "TXT"
    assert result["column_labels_found"] == {"Part Number": True, "Quantity": True, "Revision": False}


def test_bom_custom_refuses_overwrite_wrong_suffix_and_empty_output(tmp_path):
    tools, root, convertor, _ = bom_rig(tmp_path, write=False)
    base = {"format": "xls", "report": "listing_report", "columns": ["Quantity"], "summary_columns": [],
            "allow_overwrite": False}
    with pytest.raises(CADOperationError):
        tools.bom_custom(root, {**base, "file_path": str(tmp_path / "bom.CATPart")})
    existing = tmp_path / "old.xls"
    existing.write_text("x")
    with pytest.raises(CADOperationError):
        tools.bom_custom(root, {**base, "file_path": str(existing)})
    with pytest.raises(CADOperationError) as error:
        tools.bom_custom(root, {**base, "file_path": str(tmp_path / "new.xls")})
    assert error.value.code == "POSTCONDITION_FAILED"
    convertor.Print.assert_called_once()
