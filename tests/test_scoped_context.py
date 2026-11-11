"""Scoped/compact context reads. Offline doubles only; not live CATIA validation."""
import json
from types import SimpleNamespace as NS

import pytest

from catia_mcp.server import CATIAMCPServer


class Collection:
    def __init__(self, items=()):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


class Parameters(Collection):
    def __init__(self, items, sublists):
        super().__init__(items)
        self.sublists = sublists

    def SubList(self, owner, recursive):
        assert recursive is True
        return Collection(self.sublists[owner.Name])


def param(name, mode, value):
    return NS(Name=name, UserAccessMode=mode, ValueAsString=lambda: value)


def make_part(name):
    line = NS(Name="Line.1", GeometricType=3)
    constraint = NS(Name="Length.1")
    sketch = NS(Name="Sketch.1", GeometricElements=Collection([line]), Constraints=Collection([constraint]))
    pad = NS(Name="Pad.1", Type="Pad")
    main = NS(Name="PartBody", Sketches=Collection([sketch]), Shapes=Collection([pad]),
              HybridShapes=Collection(), HybridBodies=Collection(), OrderedGeometricalSets=Collection())
    other = NS(Name="Body.2", Sketches=Collection(), Shapes=Collection([NS(Name="Pocket.1", Type="Pocket")]),
               HybridShapes=Collection(), HybridBodies=Collection(), OrderedGeometricalSets=Collection())
    width = param("Width", 2, "40mm")
    internal = param("Part1\\Pad.1\\FirstLimit\\Length", 1, "20mm")
    pocket_depth = param("Part1\\Pocket.1\\Depth", 1, "5mm")
    parameters = Parameters([width, internal, pocket_depth],
                            {"PartBody": [internal], "Body.2": [pocket_depth], "Sketch.1": []})
    plane = lambda n: NS(Name=n)
    return NS(Name=name, Bodies=Collection([main, other]), HybridBodies=Collection(),
              OrderedGeometricalSets=Collection(), Parameters=parameters, MainBody=main,
              OriginElements=NS(PlaneXY=plane("xy plane"), PlaneYZ=plane("yz plane"), PlaneZX=plane("zx plane")))


@pytest.fixture
def server():
    server = CATIAMCPServer()
    documents = [NS(Name=n + ".CATPart", FullName="", Saved=False, Part=make_part(n),
                    Selection=NS(Count2=0, Count=0, Item2=lambda _: None)) for n in ("Bracket", "Pin")]
    app = NS(Caption="Mock CATIA", Documents=Collection(documents), ActiveDocument=documents[0])
    for document in documents:
        document.Activate = lambda d=document: setattr(app, "ActiveDocument", d)
    server.connection.app = app
    server.app, server.docs = app, documents
    state = server._execute_serial("catia_get_model_state", {})
    assert state["ok"], state
    server.doc_id = state["session"]["document_id"]
    yield server
    server.worker.shutdown()


def call(server, name, args=None):
    return server._execute_serial(name, args or {})


def handles(result, kind):
    return {o["name"]: o["handle"] for o in result["objects"] if o["kind"] == kind}


def test_default_list_is_compact_without_parameters_or_sketch_internals(server):
    result = call(server, "catia_list_objects")
    assert result["ok"] and result["scope"] == {"source": "part"}
    kinds = {o["kind"] for o in result["objects"]}
    assert "parameter" not in kinds and "constraint" not in kinds and "line2d" not in kinds
    assert {"body", "sketch", "feature", "plane"} <= kinds
    assert result["omitted"] == {"sketch_internals": 1, "parameters": 3}
    assert all(None not in o.values() for o in result["objects"])
    assert "container" not in handles(result, "body") and result["truncated"] is False
    assert "warnings" in result and "session" in result


def test_scope_handle_lists_only_subtree_and_sketch_scope_expands_internals(server):
    bodies = handles(call(server, "catia_list_objects"), "body")
    scoped = call(server, "catia_list_objects", {"scope_handle": bodies["Body.2"]})
    names = {o["name"] for o in scoped["objects"] if o["kind"] != "plane"}
    assert names == {"Body.2", "Pocket.1"} and scoped["scope"]["source"] == "argument"
    sketch = handles(call(server, "catia_list_objects"), "sketch")["Sketch.1"]
    inner = call(server, "catia_list_objects", {"scope_handle": sketch, "kinds": ["line2d", "constraint"]})
    assert sorted(o["kind"] for o in inner["objects"]) == ["constraint", "line2d"]
    assert all(o["container"] == sketch for o in inner["objects"])
    explicit = call(server, "catia_list_objects", {"include_sketch_internals": True, "kinds": ["constraint"]})
    assert [o["name"] for o in explicit["objects"]] == ["Length.1"]


def test_parameters_are_opt_in_user_only_filterable_and_scoped(server):
    users = call(server, "catia_list_objects", {"include_parameters": True, "kinds": ["parameter"]})
    assert [(o["name"], o["value"]) for o in users["objects"]] == [("Width", "40mm")]
    assert users["omitted"]["internal_parameters"] == 2
    every = call(server, "catia_list_objects", {"include_parameters": True, "include_internal_parameters": True,
                                                "parameter_filter": "depth", "kinds": ["parameter"]})
    assert [(o["name"], o["access"]) for o in every["objects"]] == [("Part1\\Pocket.1\\Depth", "read_write")]
    body = handles(call(server, "catia_list_objects"), "body")["PartBody"]
    scoped = call(server, "catia_list_objects", {"scope_handle": body, "include_parameters": True,
                                                 "include_internal_parameters": True, "kinds": ["parameter"]})
    assert [o["name"] for o in scoped["objects"]] == ["Part1\\Pad.1\\FirstLimit\\Length"]
    # Without include_parameters the omitted count is the scope's SubList count, not the Part total.
    compact = call(server, "catia_list_objects", {"scope_handle": body})
    assert compact["omitted"]["parameters"] == 1 and "warnings" in compact


def test_parameter_com_failure_keeps_tree_handles(server):
    def broken(owner, recursive):
        raise RuntimeError("E_FAIL SubList")
    server.docs[0].Part.Parameters.SubList = broken
    body = handles(call(server, "catia_list_objects", {"ignore_focus": True}), "body")["PartBody"]
    result = call(server, "catia_list_objects", {"scope_handle": body, "include_parameters": True})
    assert result["ok"] and {o["name"] for o in result["objects"]} >= {"PartBody", "Pad.1", "Sketch.1"}
    assert any(w.startswith("Parameters.SubList: ") for w in result["warnings"])
    assert result["omitted"]["parameters"] == "unreadable"
    compact = call(server, "catia_list_objects", {"scope_handle": body})
    assert compact["ok"] and any(w.startswith("Parameters.Count: ") for w in compact["warnings"])


@pytest.mark.parametrize("args", [
    {"parameter_filter": "x"}, {"kinds": ["parameter"]}, {"kinds": ["constraint"]},
    {"scope_handle": "obj_missing", "ignore_focus": True},
])
def test_inconsistent_scope_arguments_are_rejected(server, args):
    result = call(server, "catia_list_objects", args)
    assert result["ok"] is False and result["code"] == "INVALID_ARGUMENT"


def test_focus_is_default_scope_and_reported_without_touching_catia(server):
    body = handles(call(server, "catia_list_objects"), "body")["Body.2"]
    revision = server.session.revisions[server.doc_id]
    focused = call(server, "catia_set_focus", {"document_id": server.doc_id, "scope_handle": body})
    assert focused["ok"] and focused["focus"]["name"] == "Body.2"
    assert server.session.revisions[server.doc_id] == revision and server.app.ActiveDocument is server.docs[0]
    listed = call(server, "catia_list_objects")
    assert listed["scope"]["source"] == "focus" and listed["focus"]["handle"] == body
    assert {o["name"] for o in listed["objects"] if o["kind"] != "plane"} == {"Body.2", "Pocket.1"}
    assert call(server, "catia_list_objects", {"ignore_focus": True})["scope"] == {"source": "part"}
    features = json.loads(call(server, "catia_list_features"))
    assert features["scope_source"] == "focus" and [f["name"] for f in features["features"]] == ["Pocket.1"]
    state = call(server, "catia_get_model_state")
    assert state["data"]["focus"]["name"] == "Body.2" and "items" not in state["data"]["parameters"]
    rows = state["data"]["document"]["bodies"]
    assert rows[0] == {"name": "PartBody", "features": 1, "sketches": 1, "collapsed": True}
    assert rows[1]["focused"] and rows[1]["features"] == ["Pocket.1"]
    assert state["session"]["document_id"] == server.doc_id and "revision" in state["session"]
    assert call(server, "catia_get_workspace_state")["focus"]["handle"] == body
    cleared = call(server, "catia_set_focus", {"document_id": server.doc_id, "clear": True})
    assert cleared["focus"] is None and call(server, "catia_list_objects")["scope"]["source"] == "part"


def test_focus_requires_bound_document_and_clears_when_document_changes(server):
    other_id = server.session.document_id(server.docs[1])
    refused = call(server, "catia_set_focus", {"document_id": other_id})
    assert refused["code"] == "DOCUMENT_MISMATCH" and server.session.focus is None
    assert call(server, "catia_set_focus", {"document_id": server.doc_id})["ok"]
    switched = call(server, "catia_activate_document", {"document_id": server.doc_id, "expected_revision": 0,
                                                        "request_id": "switch", "target_document_id": other_id})
    assert switched["ok"] and server.session.focus is None
    assert call(server, "catia_get_workspace_state")["focus"] == {"cleared": "document switched"}
    # External UI switch: focus never follows or activates; it is dropped on next read.
    server.app.ActiveDocument = server.docs[0]
    call(server, "catia_get_model_state")
    assert call(server, "catia_set_focus", {"document_id": server.doc_id})["ok"]
    server.app.ActiveDocument = server.docs[1]
    state = call(server, "catia_get_model_state")
    assert state["data"]["focus"] == {"cleared": "active document changed"} and server.session.focus is None
    assert server.app.ActiveDocument is server.docs[1]


def test_model_state_full_detail_keeps_parameter_listing(server):
    summary = call(server, "catia_get_model_state", {})
    assert summary["data"]["detail"] == "summary" and "detail_note" not in summary["data"]
    full = call(server, "catia_get_model_state", {"detail": "full"})
    assert [p["name"] for p in full["data"]["parameters"]["items"]][0] == "Width"
    assert full["data"]["detail"] == "full"
    legacy = call(server, "catia_get_model_state", {"max_parameters": 1})
    assert legacy["data"]["parameters"]["truncated"] is True
    # The reported level is the effective one: max_parameters forces the full listing.
    assert legacy["data"]["detail"] == "full" and "max_parameters" in legacy["data"]["detail_note"]
    mixed = call(server, "catia_get_model_state", {"detail": "summary", "max_parameters": 1})
    assert mixed["data"]["detail"] == "full" and "items" in mixed["data"]["parameters"]
