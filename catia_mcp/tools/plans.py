"""MCP surface of the unified plan compiler. Compilation is offline; execution is one step per call."""
from __future__ import annotations

from copy import deepcopy

from catia_mcp.plan_compiler import compile_plan
from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.engineering import HANDLE, tool

PLAN_TOOLS = {"catia_plan_compile", "catia_plan_status"}


class PlanTools:
    def __init__(self, server):
        self.server = server

    def get_tool_definitions(self):
        return [
            tool("catia_plan_compile",
                 "Unified transmitter, step 1: validate a WHOLE plan of typed tool calls without touching CATIA. "
                 "Plan = {title?, attempt?, allow_outputs?, steps:[{id, tool, args, checks?, note?}]}. args use the "
                 "target tool's normal parameters; reference earlier results with {\"$ref\": \"step_id.path\", "
                 "\"as\": \"string|number|integer|boolean\"} (e.g. \"pad1.handle\", \"objs.objects.0.handle\"); "
                 "a write step that created exactly one object exposes it as handle, otherwise use created_handles.N. "
                 "Do not put document_id/expected_revision/request_id in args: they are injected per step. "
                 "checks: [{path, op: eq|ne|approx|gt|gte|lt|lte|exists|truthy, value?, tolerance?}] on that step's "
                 "result. Fix/AutoConstraint, UI input and screenshots are rejected; save/close/export need "
                 "allow_outputs=true from an explicit user instruction. Identical plan content gives the same "
                 "plan_id; bump attempt for a deliberate new run.",
                 {"plan": {"type": "object"}}, ["plan"], readonly=True),
            tool("catia_plan_step",
                 "Unified transmitter, step 2: execute exactly ONE next step of a compiled plan through its typed "
                 "tool, with the normal schema, policy, Update/readback and revision checks, then evaluate its "
                 "checks. Write steps need document_id and expected_revision from the latest model state or step "
                 "session (new-document steps excepted); request_id is derived from plan_id and step id so a "
                 "repeated call never re-executes. Stops the plan at the first failure or failed check: inspect "
                 "the model, then compile a corrected plan (or bump attempt). Never a bulk run or rollback.",
                 {"plan_id": HANDLE, "step_id": HANDLE}, ["plan_id"]),
            tool("catia_plan_status", "Read a compiled plan's per-step status, recorded results and halt reason. No CATIA call.",
                 {"plan_id": HANDLE}, ["plan_id"], readonly=True),
        ]

    def execute(self, name, args):
        plans = self.server.session.plans
        if name == "catia_plan_compile":
            from catia_mcp.constraint_policy import check_constraint_command
            compiled = compile_plan(args["plan"], self.server._schemas, self.server.read_tool_names(),
                                    set(self.server._tool_router), check_constraint_command)
            existing = plans.get(compiled["plan_id"])
            if existing is not None:
                return {**status(existing), "already_compiled": True,
                        "message": "Same plan content is already tracked; bump attempt for a new run"}
            plans[compiled["plan_id"]] = {"compiled": compiled, "cursor": 0, "results": {}, "checks": {}, "halted": None}
            return compiled
        plan = plans.get(args["plan_id"])
        if plan is None:
            raise CADOperationError("PLAN_NOT_FOUND", "Unknown plan_id in this MCP session; compile the plan first")
        return status(plan)


def status(plan):
    compiled = plan["compiled"]
    rows = []
    for step in compiled["steps"]:
        state = ("completed" if step["id"] in plan["results"] and step["index"] < plan["cursor"] else
                 "failed" if plan["halted"] and plan["halted"]["step_id"] == step["id"] else
                 "next" if step["index"] == plan["cursor"] and not plan["halted"] else "pending")
        rows.append({"id": step["id"], "tool": step["tool"], "write": step["write"], "status": state,
                     "checks": plan["checks"].get(step["id"])})
    return {"ok": True, "plan_id": compiled["plan_id"], "title": compiled["title"], "steps": rows,
            "completed": plan["cursor"], "total": compiled["step_count"], "halted": deepcopy(plan["halted"]),
            "results": deepcopy(plan["results"])}
