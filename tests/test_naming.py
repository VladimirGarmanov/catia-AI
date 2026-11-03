"""Name assignment/ownership contracts; no Windows COM or geometry validation."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.naming import rename_object


class Collection:
    def __init__(self, *items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


def fixture():
    pad = NS(Name="Pad.1")
    sketch = NS(Name="Sketch.1", GeometricElements=Collection(), Constraints=Collection())
    body = NS(Name="PartBody", Shapes=Collection(pad), Sketches=Collection(sketch))
    part = NS(Bodies=Collection(body), Parameters=Collection(), Update=Mock())
    doc = NS(Name="Test.CATPart", Part=part, Save=Mock())
    conn = NS(active_document=doc, get_active_part=lambda: part, ensure_connected=lambda: None)
    state = SessionState(conn)
    state.bind()
    engine = EngineeringTools(conn, state, NS(_active_sketch=sketch, _close_sketch=Mock()))
    return engine, part, body, pad, sketch


def call(engine, obj, name, kind="feature", **kwargs):
    return rename_object(engine, {"handle": engine.state.register(obj, kind), "new_name": name, **kwargs})


def test_rename_feature_body_and_open_sketch_without_update_or_edition_changes():
    engine, part, body, pad, sketch = fixture()
    for obj, kind, name in ((pad, "feature", "BasePad"), (body, "body", "Bracket"), (sketch, "sketch", "Profile")):
        result = call(engine, obj, name, kind, expected_name=obj.Name)
        assert result["new_name"] == name and result["changed"] and result["metadata_only"]
        assert engine.state.resolve(result["handle"]).value is obj
    assert engine.sketcher._active_sketch is sketch
    part.Update.assert_not_called()
    engine.sketcher._close_sketch.assert_not_called()
    engine.conn.active_document.Save.assert_not_called()


def test_duplicates_stale_name_and_removed_objects_are_rejected_before_write():
    engine, _, body, pad, _ = fixture()
    body.Shapes.items.append(NS(Name="Base"))
    with pytest.raises(CADOperationError) as error:
        call(engine, pad, "base")
    assert error.value.code == "DUPLICATE_NAME"
    with pytest.raises(CADOperationError) as error:
        call(engine, pad, "NewName", expected_name="OldPad")
    assert error.value.code == "STALE_REFERENCE"
    body.Shapes.items.remove(pad)
    with pytest.raises(CADOperationError) as error:
        call(engine, pad, "NewName")
    assert error.value.code == "STALE_REFERENCE"
    assert pad.Name == "Pad.1" and not engine.state.mutation_started


def test_foreign_and_selection_handles_never_rename_the_face_parent():
    engine, _, _, pad, _ = fixture()
    handle = engine.state.register(pad, "face", reference=NS())
    with pytest.raises(CADOperationError) as error:
        rename_object(engine, {"handle": handle, "new_name": "MistakenFace"})
    assert error.value.code == "UNSUPPORTED_OPERATION"
    original = engine.conn.active_document
    handle = engine.state.register(pad, "feature")
    engine.conn.active_document = NS(Name="Other.CATPart")
    with pytest.raises(CADOperationError) as error:
        rename_object(engine, {"handle": handle, "new_name": "OtherName"})
    assert error.value.code == "DOCUMENT_MISMATCH"
    engine.conn.active_document = original
    assert pad.Name == "Pad.1" and not engine.state.mutation_started


def test_parameter_uses_native_rename_and_rejects_readonly_or_local_prefix():
    engine, part, _, _, _ = fixture()
    parameter = NS(Name="Thickness", IsTrueParameter=True, ReadOnly=False, Context=part)
    parameter.Rename = Mock(side_effect=lambda name: setattr(parameter, "Name", name))
    part.Parameters.items.append(parameter)
    result = call(engine, parameter, "WallThickness", "parameter")
    parameter.Rename.assert_called_once_with("WallThickness")
    assert result["method"] == "Parameter.Rename (global name)"
    with pytest.raises(CADOperationError, match="Local:"):
        call(engine, parameter, "Local:Other", "parameter")
    parameter.ReadOnly = True
    with pytest.raises(CADOperationError, match="writable"):
        call(engine, parameter, "Other", "parameter")
    assert parameter.Name == "WallThickness"


def test_component_instance_and_drawing_text_keep_reference_metadata_and_content():
    engine, _, _, _, _ = fixture()
    component = NS(Name="Part.1", PartNumber="Part", ReferenceProduct=NS(Name="Ref"))
    root = NS(Name="Assembly", Products=Collection(component))
    engine.conn.active_document = NS(Name="Assembly.CATProduct", Product=root)
    assert call(engine, component, "LeftBracket", "product")["changed"]
    assert component.PartNumber == "Part" and component.ReferenceProduct.Name == "Ref"
    nested = NS(Name="Nested.1")
    component.Products = Collection(nested)
    with pytest.raises(CADOperationError):
        call(engine, nested, "ExternalEdit", "product")
    text = NS(Name="Text.1", Text="DO NOT CHANGE CONTENT")
    view = NS(Name="View.1", Texts=Collection(text))
    sheet = NS(Name="Sheet.1", Views=Collection(view))
    engine.conn.active_document = NS(Name="Layout.CATDrawing", Sheets=Collection(sheet))
    result = call(engine, text, "TitleNote", "drawing_text")
    assert result["changed"] and text.Text == "DO NOT CHANGE CONTENT"


@pytest.mark.parametrize("reject", [False, True])
def test_server_readback_failure_is_not_success_and_request_is_not_repeated(reject):
    class RefusingFeature:
        assignments = 0

        @property
        def Name(self):
            return "Pad.1"

        @Name.setter
        def Name(self, value):
            self.assignments += 1
            if reject:
                raise RuntimeError("CATIA refused Name")

    engine, _, body, _, _ = fixture()
    feature = RefusingFeature()
    body.Shapes.items[:] = [feature]
    server = CATIAMCPServer()
    server.connection = engine.conn
    server.session = engine.state
    server._tool_router["catia_rename_object"] = engine
    try:
        args = {"handle": engine.state.register(feature, "feature"), "new_name": "Base",
                "document_id": engine.state.document_id(), "expected_revision": 0, "request_id": "rename"}
        schema = server._schemas["catia_rename_object"]
        Draft202012Validator(schema).validate(args)
        assert not Draft202012Validator(schema).is_valid({k: v for k, v in args.items() if k != "request_id"})
        result = server._execute_serial("catia_rename_object", args)
        assert result["ok"] is False and result["status"] == "partial_failure"
        assert result["code"] == ("RENAME_FAILED" if reject else "POSTCONDITION_FAILED")
        assert result["modified_handles"] == [args["handle"]]
        assert server._execute_serial("catia_rename_object", args)["replayed"]
        assert feature.assignments == 1
    finally:
        server.worker.shutdown()
