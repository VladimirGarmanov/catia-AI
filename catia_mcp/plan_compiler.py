"""Unified plan compiler: one parameter format for every typed CATIA tool.

An AI (coordinator or offline team worker) emits a plan of steps
``{"id", "tool", "args", "checks"}``. The compiler validates the WHOLE plan
against the same JSON schemas and policy checks the MCP server enforces, before
any CATIA call. Steps may reference earlier results with ``{"$ref": "step.path"}``.

Compilation never touches COM. Execution is a separate, strictly serial
``catia_plan_step`` call per step: one typed tool call, its own Update/readback,
declared checks, then stop. This is not a bulk script runner, rollback or proof
that geometry is correct.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any, Callable, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from catia_mcp.runtime import CADOperationError

FORMAT_VERSION = 1
MAX_STEPS = 300
STEP_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
GUARDS = ("document_id", "expected_revision", "request_id")
# Live UI/selection-only or session-control tools cannot be pre-planned safely.
EXCLUDED_TOOLS = {
    "catia_ui_action": "UI input needs a fresh snapshot; the coordinator calls it directly",
    "catia_ui_snapshot": "Screenshots are coordinator checkpoints, not plan steps",
    "catia_screenshot": "Call it directly so the image reaches the coordinator",
    "catia_disconnect": "Session control is not a plan step",
    "catia_report_missing_tool": "Report gaps directly; it is not a CAD step",
    "catia_fix_constraint": "Fix is forbidden by policy",
    "catia_plan_compile": "Plans cannot compile plans",
    "catia_plan_step": "Plans cannot execute plans",
    "catia_plan_status": "Plans cannot inspect plans",
}
# Side effects outside the model: allowed only when the human explicitly asked.
OUTPUT_TOOLS = {"catia_save_document", "catia_close_document", "catia_export"}
CHECK_OPS = {"eq", "ne", "approx", "gt", "gte", "lt", "lte", "exists", "truthy"}
REF_TYPES = {"string": "__plan_ref__", "number": 1.0, "integer": 1, "boolean": True}


def _fail(message: str):
    raise CADOperationError("INVALID_PLAN", message)


def split_ref(text: str) -> tuple[str, list[str]]:
    if not isinstance(text, str) or "." not in text:
        _fail(f"$ref {text!r} must look like 'step_id.path'")
    step, *path = text.split(".")
    if not STEP_ID.match(step) or not all(path):
        _fail(f"$ref {text!r} has an invalid step id or empty path segment")
    return step, path


def is_ref(value) -> bool:
    return isinstance(value, dict) and "$ref" in value


def iter_refs(value, location=()) -> Iterable[tuple[tuple, dict]]:
    if is_ref(value):
        yield location, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_refs(item, location + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from iter_refs(item, location + (index,))


def substitute(value, resolver: Callable[[dict], Any]):
    if is_ref(value):
        return resolver(value)
    if isinstance(value, dict):
        return {key: substitute(item, resolver) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, resolver) for item in value]
    return value


def lookup(result, path: list[str]):
    """Follow a dotted path through a recorded result; list indices are integers."""
    current = result
    for segment in path:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.lstrip("-").isdigit() and -len(current) <= int(segment) < len(current):
            current = current[int(segment)]
        else:
            raise KeyError(".".join(path))
    return current


def _validate_ref(ref: dict, known: list[str], step_id: str):
    if set(ref) - {"$ref", "as"}:
        _fail(f"Step {step_id}: $ref objects accept only '$ref' and 'as'")
    if ref.get("as", "string") not in REF_TYPES:
        _fail(f"Step {step_id}: $ref 'as' must be one of {sorted(REF_TYPES)}")
    source, _ = split_ref(ref["$ref"])
    if source not in known:
        _fail(f"Step {step_id}: $ref {ref['$ref']!r} must point to an EARLIER step")
    return source


def _validate_checks(checks, step_id: str) -> list[dict]:
    if not isinstance(checks, list):
        _fail(f"Step {step_id}: checks must be a list")
    result = []
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("path"), str) or check.get("op") not in CHECK_OPS:
            _fail(f"Step {step_id}: each check needs a string path and op in {sorted(CHECK_OPS)}")
        if set(check) - {"path", "op", "value", "tolerance", "label"}:
            _fail(f"Step {step_id}: unknown check fields {sorted(set(check) - {'path', 'op', 'value', 'tolerance', 'label'})}")
        needs_value = check["op"] not in {"exists", "truthy"}
        if needs_value != ("value" in check):
            _fail(f"Step {step_id}: check op {check['op']} {'requires' if needs_value else 'rejects'} value")
        if check["op"] in {"approx", "gt", "gte", "lt", "lte"} and not _finite(check.get("value")):
            _fail(f"Step {step_id}: numeric check needs a finite value")
        if check["op"] == "approx" and not (_finite(check.get("tolerance")) and check["tolerance"] >= 0):
            _fail(f"Step {step_id}: approx needs a finite non-negative tolerance")
        if check["op"] != "approx" and "tolerance" in check:
            _fail(f"Step {step_id}: tolerance only applies to approx")
        result.append(dict(check))
    return result


def _finite(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def plan_id(plan: dict) -> str:
    text = json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return "plan_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def compile_plan(plan: dict, schemas: dict[str, dict], read_tools: set[str],
                 available: set[str] | None = None,
                 constraint_check: Callable[[str, dict], None] | None = None) -> dict:
    """Validate and normalize a plan. Raises CADOperationError(INVALID_PLAN)."""
    if not isinstance(plan, dict):
        _fail("Plan must be an object")
    unknown = set(plan) - {"format", "title", "steps", "allow_outputs", "attempt", "notes"}
    if unknown:
        _fail(f"Unknown plan fields: {sorted(unknown)}")
    if plan.get("format", FORMAT_VERSION) != FORMAT_VERSION:
        _fail(f"Unsupported plan format; expected {FORMAT_VERSION}")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        _fail(f"Plan needs 1-{MAX_STEPS} steps")
    allow_outputs = plan.get("allow_outputs", False)
    if not isinstance(allow_outputs, bool):
        _fail("allow_outputs must be boolean")
    available = set(schemas) if available is None else available
    identity = plan_id(plan)
    compiled, known, warnings = [], [], []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            _fail(f"Step {index} must be an object")
        extra = set(step) - {"id", "tool", "args", "checks", "note"}
        if extra:
            _fail(f"Step {index}: unknown fields {sorted(extra)}")
        step_id, tool = step.get("id"), step.get("tool")
        if not isinstance(step_id, str) or not STEP_ID.match(step_id):
            _fail(f"Step {index}: id must match {STEP_ID.pattern}")
        if step_id in known:
            _fail(f"Duplicate step id {step_id}")
        if tool in EXCLUDED_TOOLS:
            _fail(f"Step {step_id}: {tool} is not plannable: {EXCLUDED_TOOLS[tool]}")
        if tool not in schemas or tool not in available:
            _fail(f"Step {step_id}: unknown or unavailable tool {tool!r}")
        if tool in OUTPUT_TOOLS and not allow_outputs:
            _fail(f"Step {step_id}: {tool} needs plan allow_outputs=true, set only on explicit user instruction")
        args = step.get("args", {})
        if not isinstance(args, dict):
            _fail(f"Step {step_id}: args must be an object")
        guards = [key for key in GUARDS if key in args]
        if guards:
            _fail(f"Step {step_id}: {guards} are injected live by catia_plan_step; remove them")
        sources = sorted({_validate_ref(ref, known, step_id) for _, ref in iter_refs(args)})
        probe = substitute(args, lambda ref: REF_TYPES[ref.get("as", "string")])
        schema = schemas[tool]
        if set(GUARDS) <= set(schema.get("properties", {})):
            probe = {**probe, "document_id": "__live__", "expected_revision": 0, "request_id": "__live__"}
        error = best_match(Draft202012Validator(schema).iter_errors(probe))
        if error is not None:
            location = "/".join(str(p) for p in error.absolute_path) or "args"
            _fail(f"Step {step_id} ({tool}) {location}: {error.message}")
        if constraint_check is not None:
            constraint_check(tool, probe)
        write = tool not in read_tools
        compiled.append({"index": index, "id": step_id, "tool": tool, "write": write,
                         "args": deepcopy(args), "depends_on": sources,
                         "checks": _validate_checks(step.get("checks", []), step_id),
                         "request_id": f"{identity}:{step_id}" if write else None,
                         "note": step.get("note")})
        known.append(step_id)
    write_count = sum(step["write"] for step in compiled)
    if write_count and not any(step["checks"] for step in compiled):
        warnings.append("No step declares checks; add measured postconditions (e.g. catia_measure_exact) for key dimensions")
    return {"ok": True, "plan_id": identity, "format": FORMAT_VERSION, "title": plan.get("title"),
            "step_count": len(compiled), "write_steps": write_count, "steps": compiled,
            "allow_outputs": allow_outputs, "warnings": warnings,
            "execution": "Run each step with catia_plan_step in order; it stops at the first failure or failed check."}


def resolve_args(step: dict, results: dict[str, Any]) -> dict:
    def resolver(ref):
        source, path = split_ref(ref["$ref"])
        try:
            value = lookup(results[source], path)
        except KeyError as exc:
            raise CADOperationError("PLAN_REFERENCE_UNRESOLVED",
                                    f"Step {step['id']}: {ref['$ref']} is absent from the recorded result") from exc
        expected = ref.get("as", "string")
        valid = {"string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool),
                 "number": _finite(value), "boolean": isinstance(value, bool)}[expected]
        if not valid:
            raise CADOperationError("PLAN_REFERENCE_UNRESOLVED",
                                    f"Step {step['id']}: {ref['$ref']} resolved to {type(value).__name__}, expected {expected}")
        return deepcopy(value)
    return substitute(step["args"], resolver)


def evaluate_checks(checks: list[dict], result) -> list[dict]:
    report = []
    for check in checks:
        entry = {**check, "passed": False}
        try:
            actual = lookup(result, check["path"].split("."))
            entry["actual"] = actual
        except KeyError:
            entry["error"] = "path absent from result"
            report.append(entry)
            continue
        op, expected = check["op"], check.get("value")
        try:
            entry["passed"] = {
                "exists": lambda: True,
                "truthy": lambda: bool(actual),
                "eq": lambda: actual == expected,
                "ne": lambda: actual != expected,
                "approx": lambda: _finite(actual) and abs(actual - expected) <= check["tolerance"],
                "gt": lambda: _finite(actual) and actual > expected,
                "gte": lambda: _finite(actual) and actual >= expected,
                "lt": lambda: _finite(actual) and actual < expected,
                "lte": lambda: _finite(actual) and actual <= expected,
            }[op]()
        except TypeError:
            entry["error"] = "incomparable values"
        report.append(entry)
    return report


def compile_offline(plan: dict) -> dict:
    """Compile with the full server's real schemas without connecting to CATIA (team workers, CLI)."""
    from catia_mcp.constraint_policy import check_constraint_command
    from catia_mcp.server import CATIAMCPServer

    server = CATIAMCPServer()  # schemas only; no tool is dispatched
    try:
        return compile_plan(plan, server._schemas, server.read_tool_names(),
                            set(server._tool_router), check_constraint_command)
    finally:
        server.worker.shutdown(wait=False)
