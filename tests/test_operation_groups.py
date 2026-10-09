"""Small offline regression set for new typed groups; not a CATIA integration test."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

from jsonschema import Draft202012Validator

from catia_mcp.runtime import SessionState
from catia_mcp.server import CATIAMCPServer
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools
from catia_mcp.tools.domains import DomainTools


def test_discriminators_and_all_catalog_rows():
    server = CATIAMCPServer()
    try:
        for schema in server._schemas.values():
            Draft202012Validator.check_schema(schema)
        schema = server._schemas["catia_wireframe_surface"]
        args = {"mode": "point_center", "curve_handle": "c", "container_handle": "g",
                "document_id": "d", "request_id": "r", "expected_revision": 0}
        assert Draft202012Validator(schema).is_valid(args)
        assert not Draft202012Validator(schema).is_valid(dict(args, radius_mm=4))
        assert not Draft202012Validator(schema).is_valid({k: v for k, v in args.items() if k != "document_id"})
        rows = server._execute_serial("catia_capability_status", {"limit": 218})["matches"]
        assert len(rows) == 218
        assert all(not row["live_tested"] for row in rows)
        missing = [row for row in rows if not row["implemented"]]
        assert missing and all(row["unsupported_reason"] for row in missing)
        for row in missing:
            response = server._execute_serial("catia_capability_request", {"capability_id": row["capability_id"]})
            assert response["ok"] is False and response["status"] == "unsupported"
    finally:
        server.worker.shutdown()


def fixture():
    calls = []
    part = NS(CreateReferenceFromObject=lambda obj: obj,
              UpdateObject=lambda obj: calls.append("update_object"),
              Update=lambda: calls.append("update"), IsUpToDate=lambda obj: True)
    conn = NS(active_document=NS(Name="Test.CATPart"), get_active_part=lambda: part)
    state = SessionState(conn)
    conn.session = state
    engine = EngineeringTools(conn, state, NS(_active_sketch=None))
    return calls, part, state, engine


def test_wireframe_constructor_append_update_order():
    calls, part, state, engine = fixture()
    center = NS(Name="Center")
    curve = NS(Name="Curve")
    container = NS(Name="G", AppendHybridShape=lambda obj: calls.append("append"))
    part.HybridShapeFactory = NS(AddNewPointCenter=lambda ref: calls.append("constructor") or center)
    tool = AdvancedGeometryTools(engine)
    result = tool.execute("catia_wireframe_surface", {"mode": "point_center", "curve_handle": state.register(curve, "curve"),
                          "container_handle": state.register(container, "geoset")})
    assert result["ok"] and calls == ["constructor", "append", "update_object", "update"]
    assert state.resolve(result["handle"]).kind == "point"


def test_rule_uses_create_program_and_updates():
    calls, part, state, engine = fixture()
    rule = NS(Name="R")
    part.Relations = NS(CreateProgram=Mock(return_value=rule))
    result = DomainTools(engine).execute("catia_knowledgeware", {"mode": "rule", "name": "R", "body": "if true { }"})
    assert result["ok"]
    part.Relations.CreateProgram.assert_called_once_with("R", "Created by typed CATIA MCP", "if true { }")
    assert calls == ["update"] and state.created


def test_instance_factory_cleanup_after_failure():
    calls, part, state, engine = fixture()
    factory = NS(BeginInstanceFactory=lambda *args: calls.append("begin_factory"),
                 BeginInstantiate=lambda: calls.append("begin_instance"),
                 Instantiate=Mock(side_effect=RuntimeError("bad template")),
                 EndInstantiate=lambda: calls.append("end_instance"),
                 EndInstanceFactory=lambda: calls.append("end_factory"))
    part.GetCustomerFactory = lambda _: factory
    body = state.register(NS(Name="Body"), "body")
    try:
        DomainTools(engine).execute("catia_template_instance", {"mode": "file_template", "file_path": __file__,
             "body_handle": body, "template_name": "Template", "inputs": [], "parameters": []})
    except RuntimeError as exc:
        assert "bad template" in str(exc)
    else:
        raise AssertionError("Template failure was swallowed")
    assert calls == ["begin_factory", "begin_instance", "end_instance", "end_factory"]


def test_profile_sequence_updates_each_feature_and_reports_partial_failure():
    calls, part, state, engine = fixture()
    sketches = [NS(Name="A"), NS(Name="B")]
    body = NS(Name="Body", Sketches=NS(Count=2, Item=lambda i: sketches[i-1]))
    parameter = NS(ValuateFromString=lambda value: calls.append(value), ValueAsString=lambda: "10mm")
    feature = NS(Name="Pad", FirstLimit=NS(Dimension=parameter))
    part.ShapeFactory = NS(AddNewPad=Mock(side_effect=[feature, RuntimeError("invalid profile")]))
    tool = AdvancedGeometryTools(engine)
    args = {"mode": "pads", "body_handle": state.register(body, "body"),
            "profiles": [{"sketch_handle": state.register(sketch, "sketch"), "depth_mm": 10} for sketch in sketches]}
    from catia_mcp.runtime import CADOperationError
    try:
        tool.execute("catia_profile_solids", args)
    except CADOperationError as exc:
        assert exc.code == "PARTIAL_MUTATION" and "1 features completed" in str(exc)
    else:
        raise AssertionError("Second constructor failure was swallowed")
    assert len(state.created) == 1
    assert calls == ["10mm", "update_object", "update"]


def test_multi_pad_alternative_does_not_claim_native_support():
    server = CATIAMCPServer()
    try:
        result = server._execute_serial("catia_capability_request", {"capability_id": "CATIA-056"})
        assert result["ok"] is False
        assert result["alternative"]["tool"] == "catia_profile_solids"
        assert result["alternative"]["equivalent_native_feature"] is False
    finally:
        server.worker.shutdown()
