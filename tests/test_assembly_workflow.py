"""Assembly contracts with doubles; these do not establish native COM behavior."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator
from mcp.types import CallToolRequest, CallToolRequestParams

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.assembly_workflow import AssemblyWorkflowTools, READ_TOOLS
from catia_mcp.tools.engineering import EngineeringTools


IDENTITY = [1., 0, 0, 0, 1., 0, 0, 0, 1., 0, 0, 0]


class Collection:
    def __init__(self, *values):
        self.values = list(values)

    @property
    def Count(self):
        return len(self.values)

    def Item(self, key):
        return self.values[key-1] if isinstance(key, int) else next(v for v in self.values if v.Name == key)

    def Remove(self, key):
        self.values.remove(self.Item(key))


class Position:
    def __init__(self):
        self.values = list(IDENTITY)
        self.SetComponents = Mock(side_effect=self.set)

    def set(self, values):
        self.values = list(values)

    def GetComponents(self):
        return self.values


class Products(Collection):
    def __init__(self, *values):
        super().__init__(*values)
        self.AddComponent = Mock(side_effect=self.add)
        self.ReplaceProduct = Mock(side_effect=self.replace)

    def add(self, reference):
        obj = Product(f"{reference.PartNumber}.{self.Count+1}", reference)
        self.values.append(obj)
        return obj

    def replace(self, old, reference, multi):
        assert multi is False
        obj = Product(old.Name, reference)
        self.values[self.values.index(old)] = obj
        return obj


class Constraints(Collection):
    @property
    def BrokenConstraintsCount(self):
        return sum(v.Status == 5 for v in self.values)

    @property
    def UnUpdatedConstraintsCount(self):
        return 0


class Product:
    def __init__(self, name, reference=None):
        self.Name = self.PartNumber = name
        self.Revision = self.Nomenclature = self.Definition = self.DescriptionRef = ""
        self.Source = 0
        self.ReferenceProduct = reference if reference is not None else self
        self.Products = Products()
        self.Publications = Collection()
        self.Position = Position()
        self.constraints = Constraints()
        self.Update = Mock()

    def Connections(self, name):
        assert name == "CATIAConstraints"
        return self.constraints


def constraint(kind=1, status=0, inactive=False):
    dimension = NS(Value=10., ValueAsString=lambda: "10mm")
    dimension.ValuateFromString = Mock(side_effect=lambda v: setattr(dimension, "Value", float(v.rstrip("mdeg"))))
    return NS(Name="Constraint.1", Type=kind, Status=status, Mode=0, Orientation=0, Side=0,
              DistanceDirection=0, AngleSector=0, Dimension=dimension,
              IsInactive=lambda: inactive)


@pytest.fixture
def rig(monkeypatch):
    root, source = Product("Assembly"), Product("Wheel")
    seed = root.Products.add(source)
    root.Products.AddComponent.reset_mock()
    doc = NS(Name="Assembly.CATProduct", Product=root, Saved=False, FullName="Assembly.CATProduct")
    donor = NS(Name="Wheel.CATPart", Product=source, Saved=False, FullName="Wheel.CATPart")
    root.Parent, source.Parent = doc, donor
    conn = NS(active_document=doc, ensure_connected=lambda: None, app=NS(Documents=Collection(doc, donor)))
    state = SessionState(conn)
    state.bind()
    engine = EngineeringTools(conn, state, NS(_active_sketch=None))
    tools = AssemblyWorkflowTools(engine)
    monkeypatch.setattr("catia_mcp.tools.assembly_workflow.read_array", lambda method, count: list(method()))
    handle = state.register(seed, "product")
    return NS(tools=tools, root=root, source=source, seed=seed, doc=doc, donor=donor,
              source_id=state.document_id(donor), handle=handle, state=state, conn=conn)


def bind_server(rig):
    server = CATIAMCPServer()
    server.connection, server.session = rig.conn, rig.state
    server.assembly_workflow_tools = rig.tools
    for definition in rig.tools.get_tool_definitions():
        server._tool_router[definition["name"]] = rig.tools
    return server


def test_all_new_schemas_guards_and_wrong_mode_fields(rig):
    server = bind_server(rig)
    try:
        for item in rig.tools.get_tool_definitions():
            schema = server._schemas[item["name"]]
            Draft202012Validator.check_schema(schema)
            assert ("request_id" in schema["required"]) == (item["name"] not in READ_TOOLS)
        schema = Draft202012Validator(server._schemas["catia_assembly_pattern"])
        base = {"document_id": "doc", "expected_revision": 0, "request_id": "new",
                "mode": "linear", "component_handle": "part", "count": 4, "name_prefix": "Copy", "step_mm": [10, 0, 0]}
        assert schema.is_valid(base)
        assert not schema.is_valid({**base, "angle_step_deg": 90})
        assert not schema.is_valid({**base, "count": 1000})
        assert not schema.is_valid({**base, "mode": "fix"})
    finally:
        server.worker.shutdown()


def test_insert_open_document_and_duplicate_keep_reference_and_pose(rig):
    pose = IDENTITY[:9]+[12, 20, 30]
    result = rig.tools.insert_document({"source_document_id": rig.source_id, "instance_name": "WheelNew", "axis_components": pose})
    new = rig.state.resolve(result["handle"]).value
    assert new.ReferenceProduct is rig.source and new.Position.values == pose
    assert rig.conn.active_document is rig.doc and rig.donor.Saved is False
    result = rig.tools.duplicate({"component_handle": rig.handle, "instance_name": "WheelCopy", "axis_components": IDENTITY})
    assert rig.state.resolve(result["handle"]).value.ReferenceProduct is rig.source
    assert rig.root.Products.Count == 3


@pytest.mark.parametrize("failure", ["closed", "cycle", "name", "pose"])
def test_insert_rejects_preflight_errors_without_creation(rig, failure):
    args = {"source_document_id": rig.source_id, "instance_name": "New", "axis_components": list(IDENTITY)}
    if failure == "closed":
        rig.conn.app.Documents.values.remove(rig.donor)
    elif failure == "cycle":
        rig.source.Products.add(rig.root)
    elif failure == "name":
        args["instance_name"] = rig.seed.Name
    else:
        args["axis_components"][0] = -1  # Reflected basis is not a rigid rotation.
    with pytest.raises(CADOperationError):
        rig.tools.insert_document(args)
    rig.root.Products.AddComponent.assert_not_called()
    rig.root.Update.assert_not_called()


@pytest.mark.parametrize("mode", ["linear", "circular"])
def test_pattern_uses_shared_instances_with_explicit_poses(rig, mode):
    rig.seed.Position.values[9:] = [10, 0, 5]
    args = {"mode": mode, "component_handle": rig.handle, "count": 4, "name_prefix": "Copy"}
    if mode == "linear":
        args["step_mm"] = [0, 20, 0]
        expected = [[10, 20, 5], [10, 40, 5], [10, 60, 5]]
    else:
        args.update(axis=[0, 0, 1], pivot_mm=[0, 0, 5], angle_step_deg=90, rotate_orientation=True)
        expected = [[0, 10, 5], [-10, 0, 5], [0, -10, 5]]
    result = rig.tools.pattern(args)
    assert result["created_count"] == 3 and not result["associative"]
    for obj, translation in zip(rig.root.Products.values[1:], expected):
        assert obj.ReferenceProduct is rig.source
        assert obj.Position.values[9:] == pytest.approx(translation)
    assert rig.seed.Position.values[9:] == [10, 0, 5]
    if mode == "circular":
        assert rig.root.Products.values[1].Position.values[:3] == pytest.approx([0, 1, 0])


def test_circular_orientation_option_and_full_turn_rejection(rig):
    rig.seed.Position.values[9] = 10
    args = {"mode": "circular", "component_handle": rig.handle, "count": 3, "name_prefix": "Copy",
            "axis": [0, 0, 1], "pivot_mm": [0, 0, 0], "angle_step_deg": 180, "rotate_orientation": False}
    with pytest.raises(CADOperationError, match="less than 360"):
        rig.tools.pattern(args)
    rig.root.Products.AddComponent.assert_not_called()
    args["angle_step_deg"] = 120
    rig.tools.pattern(args)
    assert all(v.Position.values[:9] == IDENTITY[:9] for v in rig.root.Products.values)


def test_transform_rotate_about_pivot_and_explode_restore(rig):
    rig.seed.Position.values[9:] = [12, 0, 0]
    rig.tools.transform({"mode": "rotate", "component_handles": [rig.handle], "axis": [0, 0, 1],
                         "pivot_mm": [2, 0, 0], "angle_deg": 90})
    assert rig.seed.Position.values[9:] == pytest.approx([2, 10, 0])
    before = list(rig.seed.Position.values)
    exploded = rig.tools.explode({"offsets": [{"component_handle": rig.handle, "translation_mm": [0, 0, 50]}]})
    assert rig.seed.Position.values[11] == 50
    rig.tools.transform({"mode": "set_positions", "positions": exploded["restore"]["positions"]})
    assert rig.seed.Position.values == before


def test_batch_preflight_rejects_nested_alias_or_bad_pose_before_any_write(rig):
    nested = rig.seed.Products.add(Product("NestedRef"))
    nested_handle = rig.state.register(nested, "product")
    for handles in ([rig.handle, nested_handle], [rig.handle, rig.handle]):
        with pytest.raises(CADOperationError):
            rig.tools.transform({"mode": "translate", "component_handles": handles, "translation_mm": [1, 0, 0]})
    other = rig.root.Products.add(rig.source)
    bad = list(IDENTITY)
    bad[3] = 1
    with pytest.raises(CADOperationError):
        rig.tools.transform({"mode": "set_positions", "positions": [
            {"component_handle": rig.handle, "axis_components": IDENTITY},
            {"component_handle": rig.state.register(other, "product"), "axis_components": bad}]})
    rig.seed.Position.SetComponents.assert_not_called()
    rig.root.Update.assert_not_called()


def test_solver_overriding_pose_is_a_failure(rig):
    rig.root.Update.side_effect = lambda: rig.seed.Position.values.__setitem__(9, 0)
    with pytest.raises(CADOperationError, match="Solved pose"):
        rig.tools.transform({"mode": "translate", "component_handles": [rig.handle], "translation_mm": [5, 0, 0]})


@pytest.mark.parametrize("failure", ["constructor", "update"])
def test_partial_creation_is_journaled_and_mcp_replay_does_not_repeat(rig, failure):
    server = bind_server(rig)
    if failure == "constructor":
        def create_then_fail(ref):
            rig.root.Products.add(ref)
            raise RuntimeError("COM failed after creation")
        rig.root.Products.AddComponent.side_effect = create_then_fail
    else:
        rig.root.Update.side_effect = RuntimeError("solve rejected")
    args = {"source_document_id": rig.source_id, "instance_name": "New", "axis_components": IDENTITY,
            "document_id": rig.state.document_id(), "expected_revision": 0, "request_id": "insert-once"}
    try:
        result = server._execute_serial("catia_assembly_insert_document", args)
        assert result["ok"] is False and result["status"] == "partial_failure"
        assert result["created_handles"] and rig.root.Products.Count == 2
        assert server._execute_serial("catia_assembly_insert_document", args)["replayed"]
        rig.root.Products.AddComponent.assert_called_once()
    finally:
        server.worker.shutdown()


def test_replace_preserves_siblings_and_pose_and_reports_bad_constraints(rig):
    other_ref = Product("NewWheel")
    donor = NS(Name="NewWheel.CATPart", Product=other_ref)
    rig.conn.app.Documents.values.append(donor)
    sibling = rig.root.Products.add(rig.source)
    rig.seed.Position.values[9:] = [4, 5, 6]
    args = {"component_handle": rig.handle, "source_document_id": rig.state.document_id(donor), "preserve_position": True}
    result = rig.tools.replace(args)
    new = rig.state.resolve(result["handle"]).value
    assert new.ReferenceProduct is other_ref and new.Position.values[9:] == [4, 5, 6]
    assert sibling.ReferenceProduct is rig.source
    assert rig.handle not in rig.state.objects
    rig.root.constraints.values.append(constraint(status=5))
    with pytest.raises(CADOperationError, match="unsatisfied/broken"):
        rig.tools.replace({**args, "component_handle": result["handle"], "source_document_id": rig.source_id})


def test_bom_counts_occurrences_not_part_numbers_and_flags_truncation(rig):
    rig.root.Products.add(rig.source)
    same_label_different_reference = Product("Wheel")
    rig.root.Products.add(same_label_different_reference)
    report = rig.tools.bom({"scope": "leaf"})
    assert sorted(v["quantity"] for v in report["items"]) == [1, 2]
    assert report["quantities_complete"]
    report = rig.tools.bom({"max_occurrences": 1})
    assert report["truncated"] and not report["quantities_complete"]
    rig.root.Update.assert_not_called()


def test_details_metadata_and_publication_relay_owner_checks(rig):
    valuation = object()
    source = NS(Name="Axis", Valuation=valuation)
    rig.seed.Publications.values.append(source)
    details = rig.tools.details({"component_handle": rig.handle})
    assert details["source_document"]["document_id"] == rig.source_id
    pub_handle = details["publications"][0]["handle"]
    rig.tools.metadata({"properties": {"source": "made", "description": "Demo"}})
    assert rig.root.Source == 1 and rig.root.DescriptionRef == "Demo"
    assert rig.source.Source == 0 and rig.source.DescriptionRef == ""
    def add_publication(name):
        obj = NS(Name=name, Valuation=None)
        rig.root.Publications.values.append(obj)
        return obj
    def set_relay(name, collection, source_name):
        assert collection is rig.seed.Publications
        rig.root.Publications.Item(name).Valuation = collection.Item(source_name).Valuation
    rig.root.Publications.Add = Mock(side_effect=add_publication)
    rig.root.Publications.SetRelay = Mock(side_effect=set_relay)
    result = rig.tools.relay({"component_handle": rig.handle, "publication_handle": pub_handle, "name": "WheelAxis"})
    assert rig.state.resolve(result["handle"]).value.Valuation is valuation
    with pytest.raises(CADOperationError):
        rig.tools.relay({"component_handle": rig.handle, "publication_handle": result["handle"], "name": "WrongOwner"})
    rig.root.Publications.Add.assert_called_once()


def test_constraint_status_is_read_only_unknown_for_empty_and_mcp_error_for_broken(rig):
    server = bind_server(rig)
    try:
        report = server._execute_serial("catia_assembly_constraint_status", {})
        assert report["all_active_satisfied"] is None and report["remaining_dof"] is None
        rig.root.constraints.values.append(constraint())
        report = server._execute_serial("catia_assembly_constraint_status", {"require_satisfied": True})
        assert report["all_active_satisfied"] is True and report["fully_constrained"] is None
        rig.root.constraints.values[0].Status = 5
        request = CallToolRequest(params=CallToolRequestParams(name="catia_assembly_constraint_status", arguments={"require_satisfied": True}))
        response = asyncio.run(server.server.request_handlers[CallToolRequest](request)).root
        assert response.isError
        assert rig.state.revisions[rig.state.document_id()] == 0
        rig.root.Update.assert_not_called()
    finally:
        server.worker.shutdown()


@pytest.mark.parametrize("mode,number,count", [("tangent", 4, 2), ("sphere_concentric", 3, 2),
    ("symmetry", 15, 3), ("planar_angle", 7, 3), ("distance_three", 1, 3)])
def test_constraint_constructors_use_correct_arity_and_enum(rig, monkeypatch, mode, number, count):
    obj = constraint(kind=number)
    rig.root.constraints.AddBiEltCst = Mock(return_value=obj)
    rig.root.constraints.AddTriEltCst = Mock(return_value=obj)
    monkeypatch.setattr(rig.tools, "selected_reference", lambda h: f"ref-{h}")
    args = {"mode": mode, "selection_handles": [str(i) for i in range(count)]}
    if mode in {"planar_angle", "distance_three"}:
        args["value"] = 25
    assert rig.tools.constraint(args)["ok"]
    constructor = rig.root.constraints.AddTriEltCst if count == 3 else rig.root.constraints.AddBiEltCst
    constructor.assert_called_once_with(number, *[f"ref-{i}" for i in range(count)])


@pytest.mark.parametrize("mode,fields,kind,attribute,expected", [
    ("angle_sector", {"sector": 2}, 6, "AngleSector", 2),
    ("distance_direction", {"direction": "z"}, 1, "DistanceDirection", 3),
    ("driving_mode", {"driving": False}, 1, "Mode", 1),
])
def test_constraint_options_and_fix_block(rig, mode, fields, kind, attribute, expected):
    obj = constraint(kind)
    rig.root.constraints.values.append(obj)
    handle = rig.state.register(obj, "constraint")
    args = {"mode": mode, "constraint_handle": handle, **fields}
    assert rig.tools.constraint(args)["ok"] and getattr(obj, attribute) == expected
    obj.Type = 0
    with pytest.raises(CADOperationError) as error:
        rig.tools.constraint(args)
    assert error.value.code == "OPERATION_DISABLED"


def test_all_reads_leave_revision_and_model_unchanged(rig):
    server = bind_server(rig)
    try:
        for name, args in (
            ("catia_assembly_component_details", {"component_handle": rig.handle}),
            ("catia_assembly_bom", {}), ("catia_assembly_constraint_status", {}),
            ("catia_assembly_get_positions", {"component_handles": [rig.handle]}),
        ):
            assert server._execute_serial(name, args)["ok"]
        assert rig.state.revisions[rig.state.document_id()] == 0
        assert rig.state.bound_document == rig.state.document_id()
        rig.root.Update.assert_not_called()
        rig.seed.Position.SetComponents.assert_not_called()
    finally:
        server.worker.shutdown()


def test_wrong_document_stale_revision_and_sketch_fail_before_writes(rig):
    server = bind_server(rig)
    args = {"mode": "translate", "component_handles": [rig.handle], "translation_mm": [5, 0, 0],
            "document_id": rig.state.document_id(), "expected_revision": 0, "request_id": "move"}
    try:
        result = server._execute_serial("catia_assembly_transform", {**args, "expected_revision": 10})
        assert result["code"] == "STALE_REFERENCE"
        rig.tools.engineering.sketcher._active_sketch = object()
        result = server._execute_serial("catia_assembly_transform", {**args, "request_id": "move-with-sketch"})
        assert result["code"] == "SKETCH_OPEN"
        rig.tools.engineering.sketcher._active_sketch = None
        rig.conn.active_document = rig.donor
        with pytest.raises(CADOperationError, match="bound assembly"):
            rig.tools.metadata({"properties": {"part_number": "Wrong"}})
        with pytest.raises(CADOperationError) as error:
            rig.tools.bom({})
        assert error.value.code == "WRONG_DOCUMENT_TYPE"
        rig.root.Update.assert_not_called()
        rig.seed.Position.SetComponents.assert_not_called()
    finally:
        server.worker.shutdown()


def test_status_unknown_when_unupdated_or_read_incomplete(rig):
    cst = constraint()
    values = NS(Count=1, Item=lambda _: cst, BrokenConstraintsCount=0, UnUpdatedConstraintsCount=1)
    rig.root.constraints = values
    assert rig.tools.constraint_status({})["all_active_satisfied"] is None
    values.UnUpdatedConstraintsCount = 0
    cst.IsInactive = Mock(side_effect=RuntimeError("unavailable"))
    assert rig.tools.constraint_status({})["all_active_satisfied"] is None


def test_replace_detects_changes_to_another_reference(rig):
    other = Product("Other")
    doc = NS(Name="Other.CATPart", Product=other)
    rig.conn.app.Documents.values.append(doc)
    sibling = rig.root.Products.add(rig.source)
    def replace_multiple(old, reference, multi):
        new = rig.root.Products.replace(old, reference, multi)
        sibling.ReferenceProduct = reference
        return new
    rig.root.Products.ReplaceProduct.side_effect = replace_multiple
    with pytest.raises(CADOperationError, match="another occurrence"):
        rig.tools.replace({"component_handle": rig.handle, "source_document_id": rig.state.document_id(doc),
                           "preserve_position": False})
