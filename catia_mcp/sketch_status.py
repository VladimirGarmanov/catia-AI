"""Read constraint health without confusing satisfaction with solver rank.

CAA Sketch exposes no documented whole-sketch DOF/iso-constraint query. Evaluate
is a solver operation, not a boolean getter, and is deliberately never called.
"""
from catia_mcp.runtime import CADOperationError

STATUS_LABELS = (
    "satisfied", "strongly_not_satisfied", "wrong_orientation_or_side",
    "wrong_value", "wrong_geometry_type", "broken",
)


def constraint_health(sketch, *, register=None, max_constraints=1000):
    if isinstance(max_constraints, bool) or not isinstance(max_constraints, int) or not 1 <= max_constraints <= 5000:
        raise CADOperationError("INVALID_ARGUMENT", "max_constraints must be an integer in 1..5000")
    try:
        constraints = sketch.Constraints
        total = int(constraints.Count)
    except Exception as exc:
        raise CADOperationError("CONSTRAINT_READ_FAILED", f"Cannot read sketch constraints: {exc}") from exc
    rows = []
    for index in range(1, min(total, max_constraints) + 1):
        row = {"index": index, "name": None, "type": None, "mode": None,
               "status": None, "inactive": None, "unavailable": {}}
        rows.append(row)
        try:
            constraint = constraints.Item(index)
        except Exception as exc:
            row["unavailable"]["object"] = str(exc)
            row["diagnosis"] = "unavailable"
            continue
        for field, attr, cast in (("name", "Name", str), ("type", "Type", int),
                                  ("mode", "Mode", int), ("status", "Status", int)):
            try:
                row[field] = cast(getattr(constraint, attr))
            except Exception as exc:
                row["unavailable"][field] = str(exc)
        try:
            row["inactive"] = bool(constraint.IsInactive())
        except Exception as exc:
            row["unavailable"]["inactive"] = str(exc)
        status = row["status"]
        row["diagnosis"] = STATUS_LABELS[status] if status in range(len(STATUS_LABELS)) else "unknown"
        if register is not None:
            row["handle"] = register(constraint, "constraint")
        if row["type"] in {1, 5, 6, 7, 14, 18, 19}:
            try:
                row["dimension"] = str(constraint.Dimension.ValueAsString())
                row["dimension_reliable"] = status == 0
            except Exception as exc:
                row["unavailable"]["dimension"] = str(exc)
    if int(constraints.Count) != total:
        raise CADOperationError("SESSION_STATE_UNKNOWN", "Constraint collection changed during inspection; reread the sketch")
    active = [row for row in rows if row["inactive"] is False]
    problems = [row for row in active if row["status"] in range(1, len(STATUS_LABELS))]
    truncated = total > max_constraints
    unknown = truncated or any(row["inactive"] is None or (
        row["inactive"] is False and row["status"] not in range(len(STATUS_LABELS))) for row in rows)
    # Empty/all-inactive sets are not evidence that a sketch is constrained.
    satisfied = False if problems else None if unknown or not active else True
    health = ("problems_detected" if problems else "unknown" if unknown else
              "no_constraints" if total == 0 else "no_active_constraints" if not active else "satisfied")
    return {
        "ok": True, "constraint_health": health, "constraints": rows,
        "constraint_count": total, "inspected_count": len(rows), "truncated": truncated,
        "active_count": len(active), "inactive_count": sum(row["inactive"] is True for row in rows),
        "active_driving_count": sum(row["mode"] == 0 for row in active),
        "active_reference_count": sum(row["mode"] == 1 for row in active),
        "active_unknown_mode_count": sum(row["mode"] not in {0, 1} for row in active),
        "unknown_activation_count": sum(row["inactive"] is None for row in rows),
        "active_fix_count": sum(row["type"] == 0 for row in active),
        "problem_indices": [row["index"] for row in problems],
        "problem_handles": [row["handle"] for row in problems if "handle" in row],
        "all_constraints_satisfied": satisfied,
        "fully_constrained": None, "iso_constrained": None, "remaining_dof": None,
        "profile_closed": "not_verified", "completeness": "unknown",
        "warning": "Constraint satisfaction is not proof of full constraint, solver rank, absence of redundancy, "
                   "or profile closure. Inactive constraints do not constrain geometry; reference dimensions "
                   "do not drive it. Counts above describe only inspected rows when truncated. "
                   "Fix and AutoConstraint are disabled. Native Sketch Analysis is required to verify completeness.",
    }
