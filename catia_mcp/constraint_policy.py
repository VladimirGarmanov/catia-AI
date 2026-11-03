"""Non-configurable command restrictions, shared by routing and COM handlers."""
from typing import NoReturn

from catia_mcp.runtime import CADOperationError


def disabled(operation: str) -> NoReturn:
    raise CADOperationError(
        "OPERATION_DISABLED",
        f"{operation} is disabled by project policy. Use explicit geometric and "
        "dimensional constraints. Do not retry through UI, scripts or another client.",
    )


def check_constraint_command(tool_name: str, arguments: dict) -> None:
    """Reject forbidden writes before connecting, resolving targets or changing CAD."""
    if tool_name == "catia_fix_constraint":
        disabled("Fix Component")
    if tool_name == "catia_ui_action":
        disabled("UI input (generic clicks/keys cannot enforce the Fix/AutoConstraint ban)")
    field = {"catia_sketch_constraint": "type", "catia_assembly_constraint": "mode",
             "catia_assembly_operation": "mode"}.get(tool_name)
    if field:
        token = "".join(c for c in str(arguments.get(field, "")).casefold() if c.isalnum())
        if token in {"fix", "fixed", "fixcomponent", "fixtogether", "reference",
                     "catcsttypereference", "0", "autoconstraint", "autoconstraints",
                     "autoconstrain"}:
            disabled("Fix / AutoConstraint")
    if tool_name == "catia_dmu" and arguments.get("mode") == "mechanism":
        disabled("Mechanism creation with a FixedPart anchor")


def check_constraint_edit(constraint, action: str) -> None:
    """Existing Fix constraints may be read, deactivated or removed, never enabled."""
    if action in {"deactivate", "remove"}:
        return
    try:
        constraint_type = int(constraint.Type)
    except Exception as exc:
        raise CADOperationError("CAPABILITY_UNAVAILABLE", "Cannot read constraint Type; edit refused") from exc
    if constraint_type == 0:  # CAA catCstTypeReference is Fix, not a reference dimension.
        disabled("Editing or activating an existing Fix constraint")
