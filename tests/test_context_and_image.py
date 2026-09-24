"""Offline contract tests: these doubles do not validate CATIA COM behavior."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from mcp.types import CallToolRequest, CallToolRequestParams, ImageContent, ListToolsRequest

from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.context import ContextTools
from catia_mcp.tools.document import DocumentTools
from catia_mcp.tools.export import ExportTools, ScreenshotCapture
from catia_mcp.tools.measurement import MeasurementTools
from catia_mcp.tools.part_design import PartDesignTools
from scripts.selection_probe import inspect_selection


class FakeConnection:
    def __init__(self, document=None, connected=True):
        self._document = document
        self.is_connected = connected
        self.active_window = None

    @property
    def active_document(self):
        if self._document is None:
            raise RuntimeError("No active document in CATIA")
        return self._document

    def ensure_connected(self):
        if not self.is_connected:
            raise RuntimeError("CATIA is disconnected")


def fake_part_document(selection):
    shape = SimpleNamespace(Name="Pad.1")
    sketch = SimpleNamespace(Name="Sketch.1")
    body = SimpleNamespace(
        Name="PartBody", Shapes=SimpleNamespace(Count=1, Item=lambda _: shape),
        Sketches=SimpleNamespace(Count=1, Item=lambda _: sketch),
    )
    parameters = [
        SimpleNamespace(Name="Part1\\Pad.1\\FirstLimit\\Length", Value=40.0,
                        ValueAsString=lambda: "40mm"),
        SimpleNamespace(Name="Part1\\Sketch.1\\Length", Value=100.0,
                        ValueAsString=lambda: "100mm"),
    ]
    part = SimpleNamespace(
        Name="Bracket", Bodies=SimpleNamespace(Count=1, Item=lambda _: body),
        HybridBodies=SimpleNamespace(Count=0),
        Parameters=SimpleNamespace(Count=2, Item=lambda index: parameters[index - 1]),
        UpdateObject=lambda _: None, Update=lambda: None, IsUpToDate=lambda _: True,
    )
    return SimpleNamespace(Name="Part1.CATPart", FullName="C:/work/Part1.CATPart",
                           Part=part, Selection=selection)


def test_empty_selection_and_model_state():
    selection = SimpleNamespace(Count2=0, Item2=lambda _: None)
    tools = ContextTools(FakeConnection(fake_part_document(selection)))

    selected = tools.execute("catia_get_selection", {})
    assert selected["ok"] is True
    assert selected["data"]["selection"]["count"] == 0
    assert selected["data"]["selection"]["items"] == []

    state = tools.execute("catia_get_model_state", {})
    assert state["data"]["document"]["type"] == "CATPart"
    assert state["data"]["document"]["bodies"] == [
        {"name": "PartBody", "features": ["Pad.1"], "sketches": ["Sketch.1"]}
    ]
    assert state["data"]["selection"]["count"] == 0
    assert state["data"]["parameters"]["items"][0]["display"] == "40mm"
    limited = tools.execute("catia_get_model_state", {"max_parameters": 1})
    assert limited["data"]["parameters"]["truncated"] is True


def test_selection_describes_but_does_not_identify_geometry():
    selected = SimpleNamespace(Type="Face", Value=SimpleNamespace(Name="Face.1"),
                               LeafProduct=SimpleNamespace(Name="Bracket.1"))
    selection = SimpleNamespace(Count2=1, Item2=lambda _: selected)
    result = ContextTools(FakeConnection(fake_part_document(selection))).execute(
        "catia_get_selection", {})
    item = result["data"]["selection"]["items"][0]
    assert item == {"position": 1, "selection_type": "Face", "name": "Face.1",
                    "leaf_product_name": "Bracket.1"}
    assert "not persistent or exact" in result["data"]["selection"]["identity_note"]
    assert "id" not in item


def test_selected_feature_reports_its_own_dimension_and_document():
    dimension = SimpleNamespace(Value=40.0, ValueAsString=lambda: "40mm")
    feature = SimpleNamespace(Name="Pad.1", FirstLimit=SimpleNamespace(Dimension=dimension))
    owner = SimpleNamespace(Name="Part1.CATPart", FullName="C:/work/Part1.CATPart")
    selected = SimpleNamespace(Type="Pad", Value=feature, Document=owner)
    doc = fake_part_document(SimpleNamespace(Count2=1, Item2=lambda _: selected))
    item = ContextTools(FakeConnection(doc)).execute(
        "catia_get_selection", {})["data"]["selection"]["items"][0]
    assert item["dimensions"]["first_limit"]["display"] == "40mm"
    assert item["document"]["name"] == "Part1.CATPart"


def test_selection_failures_are_explicit():
    class BrokenSelection:
        @property
        def Count2(self):
            raise RuntimeError("COM call rejected")

    tools = ContextTools(FakeConnection(fake_part_document(BrokenSelection())))
    failure = tools.execute("catia_get_selection", {})
    assert failure["ok"] is False
    assert failure["code"] == "SELECTION_READ_FAILED"
    assert "COM call rejected" in failure["message"]

    bad_item = SimpleNamespace(Count2=1, Item2=lambda _: (_ for _ in ()).throw(
        RuntimeError("Item2 failed")))
    result = ContextTools(FakeConnection(fake_part_document(bad_item))).execute(
        "catia_get_selection", {})
    assert result["code"] == "SELECTION_READ_FAILED"
    assert "Item2 failed" in result["message"]

    disconnected = ContextTools(FakeConnection(connected=False)).execute(
        "catia_get_model_state", {})
    assert disconnected["code"] == "NOT_CONNECTED"
    no_document = ContextTools(FakeConnection()).execute("catia_get_model_state", {})
    assert no_document["code"] == "NO_ACTIVE_DOCUMENT"


def test_unreadable_selected_name_is_reported_without_fabricating_one():
    class BrokenValue:
        @property
        def Name(self):
            raise RuntimeError("COM name access failed")

    selection = SimpleNamespace(
        Count2=1, Item2=lambda _: SimpleNamespace(Type="Face", Value=BrokenValue()))
    result = ContextTools(FakeConnection(fake_part_document(selection))).execute(
        "catia_get_selection", {})
    observed = result["data"]["selection"]
    assert observed["count"] == 1
    assert "name" not in observed["items"][0]
    assert any("COM name access failed" in warning for warning in observed["warnings"])


def test_windows_probe_is_read_only_with_com_doubles():
    selected = SimpleNamespace(
        Type="TriDimFeatEdge",
        Value=SimpleNamespace(Name="Edge.1"),
        Document=SimpleNamespace(FullName="C:/work/Test.CATPart"),
        Reference=SimpleNamespace(DisplayName="Edge:(...)"),
    )
    selection = SimpleNamespace(
        Count2=1, Item2=lambda _: selected,
        Clear=lambda: (_ for _ in ()).throw(AssertionError("selection cleared")),
    )
    app = SimpleNamespace(ActiveDocument=SimpleNamespace(
        FullName="C:/work/Test.CATPart", Selection=selection))
    report = inspect_selection(app)
    assert report["count"] == 1
    assert report["items"][0]["reference_available"] is True
    assert "not persistent" in report["note"]


def test_model_state_does_not_hide_body_inspection_error():
    doc = fake_part_document(SimpleNamespace(Count2=0, Item2=lambda _: None))
    doc.Part.Bodies = SimpleNamespace(Count=1, Item=lambda _: (_ for _ in ()).throw(
        RuntimeError("Bodies read failed")))
    result = ContextTools(FakeConnection(doc)).execute("catia_get_model_state", {})
    assert result["code"] == "MODEL_STATE_READ_FAILED"
    assert "Bodies read failed" in result["message"]


def test_update_selected_feature_uses_live_object_and_checks_update():
    feature = SimpleNamespace(Name="Pad.1")
    selected = SimpleNamespace(Type="Pad", Value=feature)
    doc = fake_part_document(SimpleNamespace(Count2=1, Item2=lambda _: selected))
    updated = []
    doc.Part.UpdateObject = lambda value: updated.append(value)
    result = ContextTools(FakeConnection(doc)).execute("catia_update_selected_feature", {})
    assert result["ok"] is True
    assert updated == [feature]
    assert result["data"]["saved"] is False

    doc.Part.IsUpToDate = lambda _: False
    failure = ContextTools(FakeConnection(doc)).execute("catia_update_selected_feature", {})
    assert failure["code"] == "UPDATE_FAILED"


def test_update_captures_selection_once_without_resolving_by_type_or_name():
    feature = SimpleNamespace(Name="Pad.1")
    calls = []

    def item_at(index):
        calls.append(index)
        if len(calls) != 1:
            raise AssertionError("Selection must not be resolved twice")
        return SimpleNamespace(Type="Pad", Value=feature)

    doc = fake_part_document(SimpleNamespace(Count2=1, Item2=item_at))
    updated = []
    doc.Part.UpdateObject = updated.append
    result = ContextTools(FakeConnection(doc)).execute("catia_update_selected_feature", {})
    assert result["ok"] is True
    assert calls == [1]
    assert updated[0] is feature


def test_update_selected_feature_rejects_empty_and_wrong_document():
    empty = fake_part_document(SimpleNamespace(Count2=0, Item2=lambda _: None))
    assert ContextTools(FakeConnection(empty)).execute(
        "catia_update_selected_feature", {})["code"] == "EMPTY_SELECTION"
    selected = SimpleNamespace(Type="Pad", Value=SimpleNamespace(Name="Pad.1"))
    product = SimpleNamespace(Name="A.CATProduct", FullName="C:/A.CATProduct",
                              Selection=SimpleNamespace(Count2=1, Item2=lambda _: selected))
    assert ContextTools(FakeConnection(product)).execute(
        "catia_update_selected_feature", {})["code"] == "WRONG_DOCUMENT_TYPE"

    edge_doc = fake_part_document(SimpleNamespace(
        Count2=1, Item2=lambda _: SimpleNamespace(
            Type="Edge", Value=SimpleNamespace(Name="Edge.1"))))
    assert ContextTools(FakeConnection(edge_doc)).execute(
        "catia_update_selected_feature", {})["code"] == "UNSUPPORTED_SELECTION_TYPE"

    foreign = SimpleNamespace(Type="Pad", Value=SimpleNamespace(Name="Pad.1"),
                              Document=SimpleNamespace(FullName="C:/other/Other.CATPart"))
    foreign_doc = fake_part_document(SimpleNamespace(Count2=1, Item2=lambda _: foreign))
    assert ContextTools(FakeConnection(foreign_doc)).execute(
        "catia_update_selected_feature", {})["code"] == "DIFFERENT_DOCUMENT"


def test_edge_query_does_not_destroy_user_selection():
    selection = SimpleNamespace(Clear=lambda: (_ for _ in ()).throw(
        AssertionError("The selection must not be cleared")))
    connection = FakeConnection(fake_part_document(selection))
    result = PartDesignTools(connection).execute("catia_list_edges", {})
    assert result["code"] == "UNSUPPORTED_EXACT_TOPOLOGY"
    assert result["ok"] is False


def test_legacy_edge_name_is_rejected_before_any_com_mutation():
    tools = PartDesignTools(FakeConnection())
    for name, arguments in (
        ("catia_fillet", {"radius": 2, "edge_name": "Edge.1"}),
        ("catia_chamfer", {"length": 2, "edge_name": "Edge.1"}),
    ):
        try:
            tools.execute(name, arguments)
        except ValueError as exc:
            assert "Exact edge targeting" in str(exc)
        else:
            raise AssertionError("An edge name must not be accepted as an exact target")


def test_legacy_face_name_is_rejected_before_any_com_mutation():
    tools = PartDesignTools(FakeConnection())
    for name, arguments in (
        ("catia_shell", {"thickness": 2, "faces_to_remove": ["Face.1"]}),
        ("catia_draft", {"angle": 2, "face_name": "Face.1"}),
        ("catia_thickness", {"offset": 2, "face_name": "Face.1"}),
    ):
        try:
            tools.execute(name, arguments)
        except ValueError as exc:
            assert "Exact" in str(exc)
        else:
            raise AssertionError("A face name must not be accepted as an exact target")


def test_save_requires_explicit_path_and_overwrite_opt_in(tmp_path):
    saved = []
    doc = SimpleNamespace(Name="Part1.CATPart", SaveAs=lambda path: saved.append(path))
    tools = DocumentTools(FakeConnection(doc))
    try:
        tools.execute("catia_save_document", {})
    except KeyError:
        pass
    else:
        raise AssertionError("Saving without a path must fail")

    existing = tmp_path / "Part1.CATPart"
    existing.write_bytes(b"user data")
    try:
        tools.execute("catia_save_document", {"file_path": str(existing)})
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing document must not be overwritten by default")
    assert saved == []
    tools.execute("catia_save_document", {"file_path": str(existing),
                                          "allow_overwrite": True})
    assert saved == [str(existing)]


def test_failed_part_update_is_not_reported_as_success():
    body = SimpleNamespace()
    part = SimpleNamespace(MainBody=body, Update=lambda: None, IsUpToDate=lambda _: False)
    connection = FakeConnection(SimpleNamespace(Part=part))
    connection.get_active_part = lambda: part
    connection.refresh_display = lambda: None
    try:
        MeasurementTools(connection).execute("catia_update_part", {})
    except RuntimeError as exc:
        assert "not up to date" in str(exc)
    else:
        raise AssertionError("A failed update must raise")


def test_screenshot_returns_bytes_and_rejects_fake_dimensions(tmp_path):
    connection = FakeConnection()

    class Viewer:
        def CaptureToFile(self, capture_format, file_path):
            assert capture_format == 5
            with open(file_path, "wb") as output:
                output.write(b"\xff\xd8mock-jpeg\xff\xd9")

    connection.active_window = SimpleNamespace(ActiveViewer=Viewer())
    tools = ExportTools(connection)
    result = tools.execute("catia_screenshot", {"file_path": str(tmp_path / "view.png")})
    assert isinstance(result, ScreenshotCapture)
    assert result.file_path.endswith("view.jpg")
    assert result.mime_type == "image/jpeg"
    assert result.image_bytes == b"\xff\xd8mock-jpeg\xff\xd9"
    assert "width" not in tools.get_tool_definitions()[1]["inputSchema"]["properties"]

    try:
        tools.execute("catia_screenshot", {"file_path": str(tmp_path / "view.jpg"),
                                           "width": 1920})
    except ValueError as exc:
        assert "does not control pixel dimensions" in str(exc)
    else:
        raise AssertionError("width must not be silently ignored")


def test_failed_capture_does_not_return_or_replace_old_image(tmp_path):
    destination = tmp_path / "previous.jpg"
    destination.write_bytes(b"old screenshot")
    connection = FakeConnection()
    connection.active_window = SimpleNamespace(ActiveViewer=SimpleNamespace(
        CaptureToFile=lambda *_: None))
    with pytest.raises(RuntimeError, match="new screenshot"):
        ExportTools(connection).execute("catia_screenshot", {"file_path": str(destination)})
    assert destination.read_bytes() == b"old screenshot"


def test_server_registers_legacy_tools_and_returns_mcp_image():
    server = CATIAMCPServer()
    assert len(server._tool_router) == 81
    assert "catia_get_selection" in server._tool_router
    assert "catia_get_model_state" in server._tool_router
    listed = asyncio.run(server.server.request_handlers[ListToolsRequest](ListToolsRequest()))
    by_name = {tool.name: tool for tool in listed.root.tools}
    assert len(by_name) == 81
    assert by_name["catia_get_selection"].annotations.readOnlyHint is True
    assert by_name["catia_get_model_state"].annotations.readOnlyHint is True
    server.connection.app = SimpleNamespace(Caption="Mock CATIA")
    server.export_tools.execute = lambda *_: ScreenshotCapture(
        "C:/mock/view.jpg", "image/jpeg", b"\xff\xd8mock\xff\xd9")

    request = CallToolRequest(params=CallToolRequestParams(
        name="catia_screenshot", arguments={"file_path": "C:/mock/view.jpg"}))
    response = asyncio.run(server.server.request_handlers[CallToolRequest](request))
    content = response.root.content
    assert content[0].text == "Screenshot saved to C:/mock/view.jpg"
    assert isinstance(content[1], ImageContent)
    assert content[1].mimeType == "image/jpeg"


def test_server_marks_context_error_as_mcp_error():
    server = CATIAMCPServer()
    request = CallToolRequest(params=CallToolRequestParams(
        name="catia_get_model_state", arguments={}))
    response = asyncio.run(server.server.request_handlers[CallToolRequest](request))
    assert response.root.isError is True
    assert response.root.structuredContent["code"] == "NOT_CONNECTED"


def test_server_marks_unsupported_topology_and_unknown_tools_as_errors():
    server = CATIAMCPServer()
    for name in ("catia_list_edges", "catia_nonexistent"):
        request = CallToolRequest(params=CallToolRequestParams(name=name, arguments={}))
        response = asyncio.run(server.server.request_handlers[CallToolRequest](request))
        assert response.root.isError is True
        if name == "catia_list_edges":
            assert response.root.structuredContent["code"] == "UNSUPPORTED_EXACT_TOPOLOGY"
