"""Product-Scene contracts with doubles; these do not establish native DMU behavior."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.assembly_scenes import AssemblySceneTools, READ_TOOLS
from catia_mcp.tools.engineering import EngineeringTools
from tests.test_assembly_workflow import IDENTITY, Collection, Position, Product


class SceneData:
    def __init__(self, pose):
        self.Position = Position()
        self.Position.values = list(pose)


class ProductScene:
    def __init__(self, name, kind):
        self.Name, self.Type, self.data = name, kind, {}
        self.GetSceneProductData = Mock(side_effect=self.get)

    def get(self, product):
        return self.data.setdefault(id(product), SceneData(product.Position.values))

    def ExistsInScene(self, product):
        return id(product) in self.data


class Scenes(Collection):
    def __init__(self):
        super().__init__()
        self.AddProductSceneFull = Mock(side_effect=lambda n, p: self.add(n, p, 1))
        self.AddProductScenePartial = Mock(side_effect=lambda n, p: self.add(n, p, 0))
        self.Remove = Mock(side_effect=self.values.remove)

    def add(self, name, product, kind):
        scene = ProductScene(name, kind)
        self.values.append(scene)
        return scene


@pytest.fixture
def rig(monkeypatch):
    root, source = Product("Assembly"), Product("Wheel")
    first, second = root.Products.add(source), root.Products.add(source)
    second.Position.values = [1., 0, 0, 0, 1., 0, 0, 0, 1., 5., 0, 0]
    scenes = Scenes()
    root.GetTechnologicalObject = Mock(side_effect=lambda kind: scenes if kind == "ProductScenes" else None)
    doc = NS(Name="Assembly.CATProduct", Product=root, Saved=False, FullName="Assembly.CATProduct")
    root.Parent = doc
    conn = NS(active_document=doc, ensure_connected=lambda: None, app=NS(Documents=Collection(doc)))
    state = SessionState(conn)
    state.bind()
    tools = AssemblySceneTools(EngineeringTools(conn, state, NS(_active_sketch=None)))
    monkeypatch.setattr("catia_mcp.tools.assembly_workflow.read_array", lambda method, count: list(method()))
    monkeypatch.setattr("catia_mcp.tools.assembly_scenes.read_array", lambda method, count: list(method()))
    return NS(tools=tools, root=root, scenes=scenes, first=first, second=second, state=state,
              handles=[state.register(first, "product"), state.register(second, "product")])


def create(rig, name="Exploded", kind="full"):
    return rig.tools.execute("catia_assembly_scene", {"mode": "create", "name": name, "scene_type": kind})


def test_schemas_registration_and_strict_guards():
    server = CATIAMCPServer()
    assert "catia_assembly_scene_inspect" in server.read_tool_names() and READ_TOOLS <= server.read_tool_names()
    write = server._schemas["catia_assembly_scene"]
    Draft202012Validator.check_schema(write)
    assert {"document_id", "request_id", "expected_revision"} <= set(write["required"])
    assert "request_id" not in server._schemas["catia_assembly_scene_inspect"].get("required", [])
    v = Draft202012Validator(write)
    base = {"document_id": "d", "expected_revision": 0, "request_id": "r", "mode": "explode_linear",
            "scene_handle": "s", "component_handles": ["a"], "direction": [0, 0, 1], "spacing_mm": 20}
    assert v.is_valid(base)
    assert not v.is_valid({**base, "spacing_mm": 0})
    assert not v.is_valid({**base, "offsets": []})
    assert not v.is_valid({**base, "mode": "apply_to_product"})


def test_create_full_and_partial_use_documented_calls_and_list(rig):
    full = create(rig)
    partial = create(rig, "Delta", "partial")
    rig.scenes.AddProductSceneFull.assert_called_once_with("Exploded", rig.root)
    rig.scenes.AddProductScenePartial.assert_called_once_with("Delta", rig.root)
    assert full["index"] == 1 and partial["scene_type"] == "partial"
    listed = rig.tools.execute("catia_assembly_scene_inspect", {})
    assert [(r["index"], r["name"], r["type"]) for r in listed["scenes"]] == [(1, "Exploded", "full"), (2, "Delta", "partial")]
    with pytest.raises(CADOperationError) as exc:
        create(rig)
    assert exc.value.code == "INVALID_ARGUMENT"


def test_explode_linear_writes_scene_not_product(rig):
    scene = create(rig)["scene_handle"]
    real = [list(p.Position.values) for p in (rig.first, rig.second)]
    result = rig.tools.execute("catia_assembly_scene", {"mode": "explode_linear", "scene_handle": scene,
        "component_handles": rig.handles, "direction": [0, 0, 2], "spacing_mm": 25})
    assert [r["scene_axis_components"][9:] for r in result["positions"]] == [[0, 0, 25.], [5., 0, 50.]]
    assert [list(p.Position.values) for p in (rig.first, rig.second)] == real
    rig.first.Position.SetComponents.assert_not_called()
    rig.root.Update.assert_not_called()
    assert result["real_positions_changed"] is False
    read = rig.tools.execute("catia_assembly_scene_inspect", {"scene_handle": scene, "component_handles": rig.handles})
    assert read["positions"][1]["scene_axis_components"][11] == 50.
    assert read["positions"][1]["real_axis_components"][9:] == [5., 0, 0]


def test_set_positions_argument_order_and_inspect_does_not_create_data(rig):
    scene_handle = create(rig)["scene_handle"]
    scene = rig.scenes.values[0]
    read = rig.tools.execute("catia_assembly_scene_inspect", {"scene_handle": scene_handle, "component_handles": rig.handles[:1]})
    assert read["positions"][0]["exists_in_scene"] is False and scene.data == {}
    scene.GetSceneProductData.assert_not_called()
    pose = [0., 1, 0, -1, 0, 0, 0, 0, 1, 3, 4, 5]
    rig.tools.execute("catia_assembly_scene", {"mode": "set_component_positions", "scene_handle": scene_handle,
        "positions": [{"component_handle": rig.handles[0], "axis_components": pose}]})
    assert scene.data[id(rig.first)].Position.SetComponents.call_args.args == (tuple(pose),)
    assert rig.first.Position.values == IDENTITY


def test_readback_mismatch_and_real_pose_change_are_postcondition_failures(rig):
    scene_handle = create(rig)["scene_handle"]
    scene = rig.scenes.values[0]
    data = scene.get(rig.first)
    data.Position.SetComponents.side_effect = lambda v: None
    args = {"mode": "explode_offsets", "scene_handle": scene_handle,
            "offsets": [{"component_handle": rig.handles[0], "translation_mm": [0, 0, 10]}]}
    with pytest.raises(CADOperationError) as exc:
        rig.tools.execute("catia_assembly_scene", args)
    assert exc.value.code == "POSTCONDITION_FAILED"
    data.Position.SetComponents.side_effect = lambda v: (data.Position.set(v), rig.first.Position.set([*IDENTITY[:9], 9, 9, 9]))
    with pytest.raises(CADOperationError) as exc:
        rig.tools.execute("catia_assembly_scene", args)
    assert exc.value.code == "POSTCONDITION_FAILED" and "real pose" in str(exc.value)


def test_invalid_input_rejected_before_any_scene_write(rig):
    scene_handle = create(rig)["scene_handle"]
    scene = rig.scenes.values[0]
    with pytest.raises(CADOperationError):
        rig.tools.execute("catia_assembly_scene", {"mode": "set_component_positions", "scene_handle": scene_handle,
            "positions": [{"component_handle": rig.handles[0], "axis_components": IDENTITY},
                          {"component_handle": rig.handles[1], "axis_components": [2., 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]}]})
    with pytest.raises(CADOperationError):
        rig.tools.execute("catia_assembly_scene", {"mode": "explode_linear", "scene_handle": scene_handle,
            "component_handles": rig.handles, "direction": [0, 0, 0], "spacing_mm": 5})
    scene.GetSceneProductData.assert_not_called()


def test_unavailable_dmu_api_is_capability_error_without_product_move(rig):
    rig.root.GetTechnologicalObject.side_effect = Exception("DMU license not granted")
    with pytest.raises(CADOperationError) as exc:
        create(rig)
    assert exc.value.code == "CAPABILITY_UNAVAILABLE" and "DMU license" in str(exc.value)
    assert rig.first.Position.values == IDENTITY


def test_remove_requires_expected_name_and_verifies_count(rig):
    handle = create(rig)["scene_handle"]
    with pytest.raises(CADOperationError):
        rig.tools.execute("catia_assembly_scene", {"mode": "remove", "scene_handle": handle, "expected_name": "Other"})
    rig.scenes.Remove.assert_not_called()
    result = rig.tools.execute("catia_assembly_scene", {"mode": "remove", "scene_handle": handle, "expected_name": "Exploded"})
    assert result["removed"] == "Exploded" and rig.scenes.Count == 0
    assert handle not in rig.state.objects


def test_non_target_real_pose_change_is_detected(rig):
    scene_handle = create(rig)["scene_handle"]
    data = rig.scenes.values[0].get(rig.first)
    # Writing the first occurrence's scene pose moves the OTHER (untargeted) occurrence.
    data.Position.SetComponents.side_effect = lambda v: (data.Position.set(v), rig.second.Position.set([*IDENTITY[:9], 7, 7, 7]))
    with pytest.raises(CADOperationError, match="real poses") as exc:
        rig.tools.execute("catia_assembly_scene", {"mode": "explode_offsets", "scene_handle": scene_handle,
            "offsets": [{"component_handle": rig.handles[0], "translation_mm": [0, 0, 10]}]})
    assert exc.value.code == "POSTCONDITION_FAILED"


def test_create_finally_enumeration_cannot_mask_add_failure(rig):
    rig.scenes.AddProductSceneFull.side_effect = RuntimeError("no DMU license")
    original = rig.scenes.Item
    calls = {"n": 0}

    def flaky(index):
        calls["n"] += 1
        if calls["n"] > 0 and rig.scenes.AddProductSceneFull.called:
            raise RuntimeError("enumeration broke")
        return original(index)
    rig.scenes.values.append(ProductScene("Old", 1))
    rig.scenes.Item = flaky
    with pytest.raises(CADOperationError) as exc:
        create(rig, name="New")
    assert exc.value.code == "CAPABILITY_UNAVAILABLE" and "no DMU license" in str(exc.value)


def test_server_level_mid_loop_failure_is_partial_and_poses_unchanged(rig):
    server = CATIAMCPServer()
    try:
        server.connection = rig.tools.conn
        server.session = rig.state
        server.engineering_tools.state = rig.state
        server.assembly_scene_tools = rig.tools
        server._tool_router["catia_assembly_scene"] = rig.tools
        rig.tools.conn.session = rig.state
        scene_handle = create(rig)["scene_handle"]
        scene = rig.scenes.values[0]
        second = scene.get(rig.second)
        second.Position.SetComponents.side_effect = RuntimeError("E_FAIL")
        real = [list(p.Position.values) for p in (rig.first, rig.second)]
        document_id = rig.state.document_id()
        result = server._execute_serial("catia_assembly_scene", {
            "mode": "explode_linear", "scene_handle": scene_handle, "component_handles": rig.handles,
            "direction": [1, 0, 0], "spacing_mm": 10, "document_id": document_id,
            "expected_revision": rig.state.revisions[document_id], "request_id": "scene-partial"})
        assert result["ok"] is False and result["status"] == "partial_failure"
        assert rig.state.reconciliation_required is True
        assert [list(p.Position.values) for p in (rig.first, rig.second)] == real
    finally:
        server.worker.shutdown()
