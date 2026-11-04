"""Offline mating/spatial contracts. Not proof of native CATIA constraint solving."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from jsonschema import Draft202012Validator

from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.assembly_planning import IDENTITY, MATES, READ_TOOLS


class Collection:
    def __init__(self, *values):
        self.values = list(values)

    @property
    def Count(self):
        return len(self.values)

    def Item(self, index):
        return self.values[index-1]


def product(name, pose=None, children=()):
    values = list(IDENTITY if pose is None else pose)
    return NS(Name=name, PartNumber=name, Position=NS(GetComponents=lambda: values),
              Products=Collection(*children), Publications=Collection())


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setattr("catia_mcp.tools.assembly_planning.read_array", lambda fn, count: fn())
    monkeypatch.setattr("catia_mcp.tools.assembly_management.read_array", lambda fn, count: fn())
    a, b = product("Shaft.1"), product("Pulley.1", [*IDENTITY[:9], 10., 20., 30.])
    constraints = Collection()

    class Dimension:
        Value = 0.

        def ValuateFromString(self, value):
            self.text = value
            self.Value = float(value.removesuffix("mm").removesuffix("deg"))

        def ValueAsString(self):
            return getattr(self, "text", "0mm")

    def add(kind, first, second):
        assert first is references[0] and second is references[1]
        obj = NS(Name="Constraint.1", Type=kind, Status=0, Mode=0, Side=4,
                 Orientation=2, Dimension=Dimension(), IsInactive=lambda: False)
        constraints.values.append(obj)
        return obj

    constraints.AddBiEltCst = Mock(side_effect=add)
    root = product("Root", children=(a, b))
    root.Connections = lambda _: constraints
    root.Update = Mock()
    references = [NS(Name="exact1"), NS(Name="exact2")]
    selected = [NS(Name="selection1", Reference=references[0], LeafProduct=a),
                NS(Name="selection2", Reference=references[1], LeafProduct=b)]
    selection = NS(Item2=lambda i: selected[i-1])
    kinds = [10, 10]
    spa = NS(GetMeasurable=Mock(side_effect=lambda ref: NS(GeometryName=kinds[
        next(i for i, r in enumerate(references) if r is ref)])))
    doc = NS(Name="Test.CATProduct", Product=root, Selection=selection, GetWorkbench=lambda _: spa)
    server = CATIAMCPServer()
    server.connection.app = NS(ActiveDocument=doc, Documents=Collection(doc))
    server.connection.ensure_connected = Mock()
    server.session.bind()
    handles = [server.session.register(s, "face", reference=r, topology=True, selection_index=i+1)
               for i, (s, r) in enumerate(zip(selected, references))]
    guards = {"document_id": server.session.document_id(), "expected_revision": 0, "request_id": "mate-1"}
    yield NS(server=server, tools=server.assembly_planning_tools, a=a, b=b, root=root,
             constraints=constraints, kinds=kinds, handles=handles, guards=guards,
             selected=selected, references=references)
    server.worker.shutdown()


def args_for(rig, mode):
    args = {**rig.guards, "mode": mode, "name": "Shaft_Pulley_Mate", "selection_handles": rig.handles}
    if mode in {"axis_coincidence", "axis_parallel", "plane_coincidence", "plane_parallel", "plane_offset"}:
        args["orientation"] = "opposite"
    if mode == "plane_offset":
        args.update(distance_mm=12.5, side="negative")
    if mode == "plane_angle":
        args["angle_deg"] = 45.
    return args


@pytest.mark.parametrize("mode", list(MATES))
def test_typed_mate_sets_options_before_one_update_and_deduplicates(rig, mode):
    kind, native = MATES[mode]
    rig.kinds[:] = [kind, kind]
    args = args_for(rig, mode)

    def update():
        obj = rig.constraints.values[0]
        if "orientation" in args:
            assert obj.Orientation == 1
        if mode == "plane_offset":
            assert obj.Side == 1 and obj.Dimension.Value == 12.5 and obj.Mode == 0
        if mode == "plane_angle":
            assert obj.AngleSector == 0 and obj.Dimension.Value == 45

    rig.root.Update.side_effect = update
    result = rig.server._execute_serial("catia_assembly_mate", args)
    assert result["ok"] and result["native_constraint_satisfied"]
    assert result["remaining_dof"] is None and result["global_assembly_verified"] is False
    assert result["constraint"]["Type"] == native
    assert len(result["created_handles"]) == 1 and len(result["modified_handles"]) == 2
    assert result["session"]["revision"] == 1
    assert rig.server._execute_serial("catia_assembly_mate", args)["replayed"]
    rig.constraints.AddBiEltCst.assert_called_once()
    rig.root.Update.assert_called_once()
    assert all(h not in rig.server.session.objects for h in rig.handles)


def test_preview_is_read_only_and_does_not_turn_cylinder_into_axis(rig):
    rig.kinds[:] = [4, 4]
    result = rig.server._execute_serial("catia_assembly_mate_preview", {"selection_handles": rig.handles})
    assert result["ok"] and result["compatible_modes"] == []
    assert result["supports"][0]["geometry_kind"] == "cylinder"
    assert result["solvability_checked"] is False
    failed = rig.server._execute_serial("catia_assembly_mate", args_for(rig, "axis_coincidence"))
    assert failed["code"] == "WRONG_GEOMETRY_TYPE" and failed["status"] == "failed"
    assert failed["session"]["revision"] == 0
    rig.constraints.AddBiEltCst.assert_not_called()
    rig.root.Update.assert_not_called()


@pytest.mark.parametrize("failure", ["selection", "owner", "same_component", "name"])
def test_mate_preflight_never_writes_wrong_targets(rig, failure):
    if failure == "selection":
        rig.selected[0].Reference = NS(Name="another face")
    elif failure == "owner":
        rig.selected[0].LeafProduct = product("external child")
    elif failure == "same_component":
        rig.selected[1].LeafProduct = rig.a
    else:
        rig.constraints.values.append(NS(Name="Shaft_Pulley_Mate"))
    result = rig.server._execute_serial("catia_assembly_mate", args_for(rig, "axis_coincidence"))
    assert not result["ok"] and result["status"] == "failed"
    assert not result["session"]["reconciliation_required"]
    rig.constraints.AddBiEltCst.assert_not_called()
    rig.root.Update.assert_not_called()


@pytest.mark.parametrize("failure", ["update", "status", "dimension"])
def test_failed_solve_reports_created_constraint_and_stops(rig, failure):
    rig.kinds[:] = [7, 7]

    def update():
        if failure == "update":
            raise RuntimeError("solver error")
        obj = rig.constraints.values[0]
        if failure == "status":
            obj.Status = 5
        else:
            obj.Dimension.Value = 99

    rig.root.Update.side_effect = update
    args = args_for(rig, "plane_offset")
    result = rig.server._execute_serial("catia_assembly_mate", args)
    assert not result["ok"] and result["status"] == "partial_failure"
    assert result["created_handles"] and result["session"]["reconciliation_required"]
    assert rig.server._execute_serial("catia_assembly_mate", args)["replayed"]
    rig.constraints.AddBiEltCst.assert_called_once()


def test_spatial_context_composes_rotated_parent_and_propagates_unavailable(rig):
    parent_pose = [0., 1., 0., -1., 0., 0., 0., 0., 1., 100., 200., 300.]
    child = product("Nested.1", [*IDENTITY[:9], 10., 20., 30.])
    rig.a.Position.GetComponents = lambda: parent_pose
    rig.a.Products.values.append(child)
    result = rig.server._execute_serial("catia_assembly_spatial_context", {})
    row = next(r for r in result["products"] if r["Name"] == "Nested.1")
    assert result["spatial_complete"] and row["origin_root_mm"] == [80., 210., 330.]
    assert row["root_axis_components"][:9] == parent_pose[:9]
    assert not row["immediate_root_occurrence"]
    rig.a.Position.GetComponents = Mock(side_effect=RuntimeError("array unavailable"))
    failed = rig.tools.spatial_context({})
    row = next(r for r in failed["products"] if r["Name"] == "Nested.1")
    assert not failed["spatial_complete"] and row["origin_root_mm"] is None
    truncated = rig.tools.spatial_context({"max_objects": 1})
    assert truncated["truncated"] and not truncated["spatial_complete"]
    rig.root.Update.assert_not_called()
    assert rig.server.session.revisions[rig.server.session.document_id()] == 0


def test_schemas_and_registration_keep_reads_separate_from_mutations(rig):
    assert len(rig.server._tool_router) == 166
    for definition in rig.tools.get_tool_definitions():
        schema = rig.server._schemas[definition["name"]]
        Draft202012Validator.check_schema(schema)
        assert ("request_id" not in schema["required"]) == (definition["name"] in READ_TOOLS)
    validator = Draft202012Validator(rig.server._schemas["catia_assembly_mate"])
    assert not validator.is_valid({**args_for(rig, "axis_coincidence"), "distance_mm": 5})
    assert not validator.is_valid({**args_for(rig, "axis_coincidence"), "mode": "fix"})
