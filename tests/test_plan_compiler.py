"""Offline contract checks for the unified plan compiler and one-step transmitter."""
import pytest

from catia_mcp.runtime import CADOperationError
from catia_mcp.server import CATIAMCPServer


@pytest.fixture()
def server():
    server = CATIAMCPServer()
    yield server
    server.worker.shutdown()


def plan(*steps, **extra):
    return {"title": "bracket", "steps": list(steps), **extra}


PAD = {"id": "pad1", "tool": "catia_pad", "args": {"height": 10, "sketch_handle": {"$ref": "sk.handle"}}}
SKETCH = {"id": "sk", "tool": "catia_create_sketch", "args": {"plane": "xy"}}


def compile_(server, value):
    return server._execute_serial("catia_plan_compile", {"plan": value})


def test_compiles_against_live_schemas_and_derives_request_ids(server):
    measure = {"id": "m", "tool": "catia_measure_exact",
               "args": {"mode": "scalar", "property": "volume", "handle": {"$ref": "pad1.handle"}},
               "checks": [{"path": "value", "op": "approx", "value": 1000, "tolerance": 0.5}]}
    result = compile_(server, plan(SKETCH, PAD, measure))
    assert result["ok"] and result["write_steps"] == 2
    steps = {s["id"]: s for s in result["steps"]}
    assert steps["pad1"]["depends_on"] == ["sk"] and steps["pad1"]["request_id"] == result["plan_id"] + ":pad1"
    assert steps["m"]["write"] is False and steps["m"]["request_id"] is None
    assert compile_(server, plan(SKETCH, PAD, measure))["already_compiled"] is True
    assert compile_(server, plan(SKETCH, PAD, measure, attempt=2))["plan_id"] != result["plan_id"]


@pytest.mark.parametrize("bad,message", [
    (plan({"id": "a", "tool": "catia_pad", "args": {"height": "ten"}}), "catia_pad"),
    (plan({"id": "a", "tool": "catia_nope"}), "unknown or unavailable"),
    (plan({"id": "a", "tool": "catia_ui_action", "args": {}}), "not plannable"),
    (plan({"id": "a", "tool": "catia_save_document", "args": {"file_path": "C:/x.CATPart"}}), "allow_outputs"),
    (plan({"id": "a", "tool": "catia_pad", "args": {"height": 5, "request_id": "r"}}), "injected live"),
    (plan(PAD), "EARLIER step"),
    (plan(SKETCH, dict(SKETCH)), "Duplicate"),
    (plan({"id": "a", "tool": "catia_get_model_state", "checks": [{"path": "ok", "op": "approx", "value": 1}]}), "tolerance"),
])
def test_rejects_whole_plan_before_any_cad_call(server, bad, message):
    result = compile_(server, bad)
    assert result["ok"] is False and result["code"] == "INVALID_PLAN"
    assert message in result["error"]["message"]
    assert not server.session.plans


def test_fix_constraint_rejected_by_policy(server):
    result = compile_(server, plan({"id": "fx", "tool": "catia_sketch_constraint",
                                    "args": {"type": "fix", "element_1": 1}}))
    assert result["ok"] is False


def test_step_resolves_refs_injects_guards_stops_on_failed_check(server):
    measure = {"id": "m", "tool": "catia_measure_exact",
               "args": {"mode": "scalar", "property": "volume", "handle": {"$ref": "pad1.handle"}},
               "checks": [{"path": "value", "op": "approx", "value": 1000, "tolerance": 0.5}]}
    plan_id = compile_(server, plan(SKETCH, PAD, measure))["plan_id"]
    calls = []
    replies = {"catia_create_sketch": {"ok": True, "handle": "obj_sketch"},
               "catia_pad": {"ok": True, "message": "Pad created", "created_handles": ["obj_a", "obj_b"]},
               "catia_measure_exact": {"ok": True, "value": 999.0, "unit": "mm3"}}
    outer = server._execute_serial

    def fake(name, arguments):
        if name.startswith("catia_plan"):
            return outer(name, arguments)
        calls.append((name, arguments))
        return replies[name]
    server._execute_serial = fake
    guards = {"document_id": "doc_1", "expected_revision": 0}

    missing = server._execute_serial("catia_plan_step", {"plan_id": plan_id})
    assert missing["code"] == "MODEL_CONTEXT_REQUIRED" and not calls
    first = server._execute_serial("catia_plan_step", {"plan_id": plan_id, **guards})
    assert first["ok"] and first["next_step"] == "pad1"
    assert calls[-1] == ("catia_create_sketch", {"plane": "xy", "request_id": plan_id + ":sk", **guards})
    assert server._execute_serial("catia_plan_step", {"plan_id": plan_id, "step_id": "m"})["code"] == "PLAN_ORDER"
    second = server._execute_serial("catia_plan_step", {"plan_id": plan_id, **dict(guards, expected_revision=1)})
    assert second["ok"] and "handle" not in second["result"]
    assert calls[-1][1]["sketch_handle"] == "obj_sketch"
    # Two created objects make "handle" ambiguous: the dependent reference fails cleanly, no CAD call.
    third = server._execute_serial("catia_plan_step", {"plan_id": plan_id})
    assert third["code"] == "PLAN_REFERENCE_UNRESOLVED" and len(calls) == 2
    # Repeating a completed step replays the record instead of re-executing.
    again = server._execute_serial("catia_plan_step", {"plan_id": plan_id, "step_id": "sk"})
    assert again["replayed"] and len(calls) == 2


def test_failed_check_halts_plan(server):
    step = {"id": "m", "tool": "catia_measure_distance", "args": {"first_handle": "a", "second_handle": "b"},
            "checks": [{"path": "value", "op": "approx", "value": 20, "tolerance": 0.01}]}
    plan_id = compile_(server, plan(step, {"id": "m2", "tool": "catia_get_model_state"}))["plan_id"]
    outer = server._execute_serial
    server._execute_serial = lambda name, a: outer(name, a) if name.startswith("catia_plan") else {"ok": True, "value": 20000.0}
    result = server._execute_serial("catia_plan_step", {"plan_id": plan_id})
    assert result["ok"] is False and result["code"] == "PLAN_CHECK_FAILED"
    assert result["halted"]["step_id"] == "m"
    assert server._execute_serial("catia_plan_step", {"plan_id": plan_id})["code"] == "PLAN_HALTED"
    status = server._execute_serial("catia_plan_status", {"plan_id": plan_id})
    assert [row["status"] for row in status["steps"]] == ["failed", "pending"]


def test_lookup_paths_and_typed_refs():
    from catia_mcp.plan_compiler import lookup, resolve_args
    result = {"objects": [{"handle": "h0"}, {"handle": "h1"}], "value": 4.5}
    assert lookup(result, ["objects", "-1", "handle"]) == "h1"
    step = {"id": "x", "args": {"a": {"$ref": "s.value", "as": "number"}, "b": [{"$ref": "s.objects.0.handle"}]}}
    assert resolve_args(step, {"s": result}) == {"a": 4.5, "b": ["h0"]}
    with pytest.raises(CADOperationError, match="expected integer"):
        resolve_args({"id": "x", "args": {"a": {"$ref": "s.value", "as": "integer"}}}, {"s": result})


def test_single_created_handle_is_exposed_for_legacy_text_tools(server):
    plan_id = compile_(server, plan(SKETCH))["plan_id"]
    outer = server._execute_serial
    server._execute_serial = lambda name, a: outer(name, a) if name.startswith("catia_plan") else {
        "ok": True, "message": "Sketch created", "created_handles": ["obj_s"]}
    result = server._execute_serial("catia_plan_step", {"plan_id": plan_id, "document_id": "d", "expected_revision": 0})
    assert result["result"]["handle"] == "obj_s" and result["next_step"] is None
