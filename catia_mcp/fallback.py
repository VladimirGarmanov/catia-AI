"""Advisory UI recovery policy, not a desktop driver or approval mechanism."""


def fallback_advice(result: dict) -> dict:
    """Preserve failure evidence; never turn a failed write into an automatic retry."""
    if result.get("ok", True):
        return result
    blocked = result.get("code") in {"COM_TIMEOUT", "SESSION_STATE_UNKNOWN"}
    return {
        **result,
        "ui_fallback": {
            "status": "blocked_pending_reconciliation" if blocked else "input_disabled_by_policy",
            "local_confirmation_required": False,
            "desktop_driver_provided": False,
            "desktop_tools": ["catia_ui_snapshot"],
            "instructions": (
                "Do not click or retry: the COM operation may still be running. "
                "Resolve busy/modal state with the human and reconcile the model first."
                if blocked else
                "UI input is disabled because generic clicks/keys could bypass the "
                "Fix/AutoConstraint ban. Snapshots are read-only. Do not retry disabled "
                "commands through scripts, another client or external desktop tools. "
                "For other failures inspect partial results before proposing a typed-tool repair."
            ),
        },
    }
