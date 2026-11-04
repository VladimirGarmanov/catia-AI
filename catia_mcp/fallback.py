"""Advisory UI recovery policy, not a desktop driver or approval mechanism."""


def fallback_advice(result: dict) -> dict:
    """Preserve failure evidence; never turn a failed write into an automatic retry."""
    if result.get("ok", True):
        return result
    blocked = result.get("code") in {"COM_TIMEOUT", "SESSION_STATE_UNKNOWN"}
    forbidden = result.get("code") == "OPERATION_DISABLED"
    return {
        **result,
        "ui_fallback": {
            "status": "blocked_pending_reconciliation" if blocked else "input_disabled_by_policy" if forbidden else "available_after_inspection",
            "local_confirmation_required": False,
            "desktop_driver_provided": True,
            "desktop_tools": ["catia_ui_snapshot"] if blocked or forbidden else ["catia_ui_snapshot", "catia_ui_action"],
            "instructions": (
                "Do not click or retry: the COM operation may still be running. "
                "Resolve busy/modal state with the human and reconcile the model first."
                if blocked else
                "This operation is forbidden by policy. Do not bypass it through UI, "
                "scripts or another client. Fix/AutoConstraint remain forbidden."
                if forbidden else
                "Inspect partial results and a current Windows desktop snapshot first. "
                "Use UI only for the authorized task and never repeat an uncertain write. "
                "Record the intended missing_tool, then verify UI and model state. "
                "Fix/AutoConstraint are forbidden even through UI."
            ),
        },
    }
