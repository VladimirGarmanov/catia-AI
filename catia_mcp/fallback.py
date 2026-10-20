"""Advisory UI recovery policy, not a desktop driver or approval mechanism."""


def fallback_advice(result: dict) -> dict:
    """Preserve failure evidence; never turn a failed write into an automatic retry."""
    if result.get("ok", True):
        return result
    blocked = result.get("code") in {"COM_TIMEOUT", "SESSION_STATE_UNKNOWN"}
    return {
        **result,
        "ui_fallback": {
            "status": "blocked_pending_reconciliation" if blocked else "inspect_desktop_before_recovery",
            "local_confirmation_required": False,
            "desktop_driver_provided": True,
            "desktop_tools": ["catia_ui_snapshot", "catia_ui_action"],
            "instructions": (
                "Do not click or retry: the COM operation may still be running. "
                "Resolve busy/modal state with the human and reconcile the model first."
                if blocked else
                "Do not automatically repeat this operation through the UI. Inspect the "
                "document and partial results first. If an actual desktop-control tool "
                "is available on the CATIA Windows host (catia_ui_snapshot/action), use UI recovery within the authorized task. "
                "Whole-desktop access is enabled without local confirmation. Otherwise report missing "
                "desktop control; do not invent clicks or use shell automation."
            ),
        },
    }
