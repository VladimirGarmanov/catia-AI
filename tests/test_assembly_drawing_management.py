"""Scoped orchestration tests; no CATIA, native geometry or Windows claims."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.assembly_management import AssemblyManagementTools
from catia_mcp.tools.drawing_management import DrawingManagementTools
from catia_mcp.tools.engineering import EngineeringTools


class Collection:
    def __init__(self, *items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]

    def Remove(self, index):
        self.items.pop(index - 1)


def engineering(doc):
    conn = NS(active_document=doc, ensure_connected=lambda: None)
    state = SessionState(conn)
    state.bind()
    return EngineeringTools(conn, state, NS(_active_sketch=None))


def drawing_fixture():
    table = NS(Name="Table.1", NumberOfRows=2, NumberOfColumns=3, x=0, y=0, Angle=0)
    text = NS(Name="Text.1", Text="old", x=0, y=0, Angle=0, FrameType=0)
    view = NS(Name="View.1", Tables=Collection(table), Texts=Collection(text),
              Dimensions=Collection(), GeometricElements=Collection(),
              Activate=Mock(), SaveEdition=Mock())
    sheet = NS(Name="Sheet.1", Views=Collection(view), Update=Mock())
    engine = engineering(NS(Name="Test.CATDrawing", Sheets=Collection(sheet)))
    tools = DrawingManagementTools(engine)
    return tools, sheet, view, table, text


def assembly_fixture():
    occurrence = NS(Name="Part.1", Position=NS(SetComponents=Mock(), GetComponents=Mock()))
    constraints = Collection()
    root = NS(Name="Root", Products=Collection(occurrence), Connections=lambda _: constraints, Update=Mock())
    tools = AssemblyManagementTools(engineering(NS(Name="Test.CATProduct", Product=root)))
    return tools, root, occurrence, constraints


def test_new_schemas_guard_writes_keep_read_only_and_reject_fix():
    server = CATIAMCPServer()
    try:
        for module in (server.assembly_management_tools, server.drawing_management_tools):
            for definition in module.get_tool_definitions():
                schema = server._schemas[definition["name"]]
                Draft202012Validator.check_schema(schema)
                assert ("request_id" in schema["required"]) != definition["readOnlyHint"]
        schema = Draft202012Validator(server._schemas["catia_assembly_constraint"])
        guards = {"document_id": "d", "request_id": "r", "expected_revision": 0}
        assert not schema.is_valid({**guards, "mode": "fix", "selection_handle": "s"})
        assert not schema.is_valid({**guards, "mode": "fix", "selection_handles": ["a", "b"]})
        assert not schema.is_valid({**guards, "mode": "distance", "selection_handles": ["a"], "value": 10})
        assert len(server._tool_router) == 176
    finally:
        server.worker.shutdown()


def test_table_batch_preflights_all_cells_before_writing_and_reads_back():
    tools, sheet, _, table, _ = drawing_fixture()
    values = {}
    table.SetCellString = Mock(side_effect=lambda r, c, t: values.__setitem__((r, c), t))
    table.GetCellString = lambda r, c: values[(r, c)]
    handle = tools.state.register(table, "drawing_table")
    args = {"mode": "cells", "table_handle": handle,
            "cells": [{"row": 1, "column": 1, "text": "Part"}, {"row": 3, "column": 2, "text": "bad"}]}
    with pytest.raises(CADOperationError, match="outside"):
        tools.table(args)
    table.SetCellString.assert_not_called()
    args["cells"][1]["row"] = 2
    assert tools.table(args)["ok"]
    assert values == {(1, 1): "Part", (2, 2): "bad"}
    sheet.Update.assert_called_once()


def test_table_creation_records_handle_before_update_failure():
    tools, sheet, view, table, _ = drawing_fixture()
    view.Tables.Add = Mock(return_value=table)
    sheet.Update.side_effect = RuntimeError("CATIA rejected update")
    args = {"mode": "create", "view_handle": tools.state.register(view, "view"), "position_mm": [10, 20],
            "rows": 2, "columns": 3, "row_height_mm": 5, "column_width_mm": 15}
    with pytest.raises(CADOperationError) as error:
        tools.table(args)
    assert error.value.code == "UPDATE_FAILED"
    assert tools.state.resolve(tools.state.created[0]).value is table
    view.Tables.Add.assert_called_once_with(10, 20, 2, 3, 5, 15)


def test_text_mm_conversion_and_stale_membership():
    tools, _, view, _, text = drawing_fixture()
    handle = tools.state.register(text, "drawing_text")
    args = {"mode": "position", "text_handle": handle, "position_mm": [25, 40]}
    assert tools.text_edit(args)["ok"]
    assert (text.x, text.y) == (0.025, 0.04)
    assert tools.inspect({"mode": "text", "text_handle": handle})["position_mm"] == [25, 40]
    view.Texts.items.clear()
    with pytest.raises(CADOperationError, match="no longer belongs"):
        tools.text_edit(dict(args, position_mm=[80, 90]))
    assert (text.x, text.y) == (0.025, 0.04)


def test_drawing_geometry_saves_edition_on_partial_failure():
    tools, sheet, view, _, _ = drawing_fixture()
    line = NS(Name="Line.1", Construction=False)
    view.Factory2D = NS(CreateLine=Mock(side_effect=[line, RuntimeError("bad line")]))
    with pytest.raises(RuntimeError, match="bad line"):
        tools.geometry({"mode": "rectangle", "view_handle": tools.state.register(view, "view"),
                        "corner_mm": [0, 0], "width_mm": 10, "height_mm": 20, "construction": True})
    assert len(tools.state.created) == 1 and line.Construction
    view.SaveEdition.assert_called_once()
    sheet.Update.assert_not_called()


def test_assembly_position_detects_solver_moving_component_back(monkeypatch):
    tools, root, occurrence, _ = assembly_fixture()
    old = [1., 0, 0, 0, 1., 0, 0, 0, 1., 0, 0, 0]
    monkeypatch.setattr("catia_mcp.tools.assembly_management.read_array", lambda *args: list(old))
    args = {"mode": "translate", "component_handle": tools.state.register(occurrence, "product"), "translation_mm": [10, 0, 0]}
    with pytest.raises(CADOperationError) as error:
        tools.component(args)
    assert error.value.code == "POSTCONDITION_FAILED"
    assert occurrence.Position.SetComponents.call_args.args[0][9:] == (10, 0, 0)
    root.Update.assert_called_once()


def test_assembly_rotate_and_reject_nested_writes(monkeypatch):
    tools, _, occurrence, _ = assembly_fixture()
    pose = [1., 0, 0, 0, 1., 0, 0, 0, 1., 5, 10, 20]
    monkeypatch.setattr("catia_mcp.tools.assembly_management.read_array", lambda *args: list(pose))
    occurrence.Position.SetComponents.side_effect = lambda p: pose.__setitem__(slice(None), p)
    args = {"mode": "rotate", "component_handle": tools.state.register(occurrence, "product"), "axis": [0, 0, 1], "angle_deg": 90}
    assert tools.component(args)["ok"]
    assert pose == pytest.approx([0, 1, 0, -1, 0, 0, 0, 0, 1, 5, 10, 20])
    nested = NS(Name="Nested")
    with pytest.raises(CADOperationError, match="not a member"):
        tools.component({"mode": "rename", "component_handle": tools.state.register(nested, "product"), "name": "Wrong"})
    assert nested.Name == "Nested"


def test_constraint_side_uses_caa_enum_and_unsolved_is_failure():
    tools, root, _, constraints = assembly_fixture()
    cst = NS(Name="Offset", Type=1, Status=0, Mode=0, Orientation=0, Side=0,
             IsInactive=lambda: False, Dimension=NS(ValueAsString=lambda: "10mm"))
    constraints.items.append(cst)
    handle = tools.state.register(cst, "constraint")
    args = {"mode": "side", "constraint_handle": handle, "side": "undefined"}
    assert tools.constraint(args)["ok"] and cst.Side == 4
    root.Update.side_effect = lambda: setattr(cst, "Status", 1)
    with pytest.raises(CADOperationError, match="not solved"):
        tools.constraint(args)


def test_existing_assembly_fix_cannot_activate_but_can_be_removed():
    tools, root, _, constraints = assembly_fixture()
    fixed = NS(Name="Fix.1", Type=0, Activate=Mock())
    constraints.items.append(fixed)
    handle = tools.state.register(fixed, "constraint")
    with pytest.raises(CADOperationError) as error:
        tools.constraint({"mode": "activate", "constraint_handle": handle})
    assert error.value.code == "OPERATION_DISABLED"
    fixed.Activate.assert_not_called()
    root.Update.assert_not_called()
    assert tools.constraint({"mode": "remove", "constraint_handle": handle})["ok"]
    assert constraints.Count == 0


def test_server_propagates_partial_failure_and_inspection_does_not_mutate():
    server = CATIAMCPServer()
    try:
        tools, sheet, view, table, _ = drawing_fixture()
        conn = tools.conn
        server.connection = conn
        server.session = tools.state
        server.drawing_management_tools.engineering = tools.engineering
        server.drawing_management_tools.conn = conn
        h = tools.state.register(view, "view")
        view.Tables.Add = Mock(return_value=table)
        sheet.Update.side_effect = RuntimeError("update failed")
        args = {"mode": "create", "view_handle": h, "position_mm": [0, 0], "rows": 2, "columns": 3,
                "row_height_mm": 5, "column_width_mm": 20, "document_id": tools.state.document_id(),
                "expected_revision": 0, "request_id": "create-table"}
        result = server._execute_serial("catia_drawing_table", args)
        assert result["ok"] is False and result["status"] == "partial_failure"
        assert result["created_handles"] and result["code"] == "UPDATE_FAILED"
        table_handle = result["created_handles"][0]
        table.GetCellString = lambda *_: "cell"
        count = view.Tables.Add.call_count
        assert server._execute_serial("catia_drawing_table", args)["replayed"]
        assert view.Tables.Add.call_count == count
        revision = tools.state.revisions[tools.state.document_id()]
        result = server._execute_serial("catia_drawing_inspect", {"mode": "table", "table_handle": table_handle,
            "start_row": 1, "start_column": 1, "row_count": 1, "column_count": 1})
        # A read needs no request_id/document binding and must not advance revision.
        assert tools.state.revisions[tools.state.document_id()] == revision
        assert result["ok"] and result["cells"][0]["text"] == "cell"
        sheet.Update.assert_called_once()
    finally:
        server.worker.shutdown()
