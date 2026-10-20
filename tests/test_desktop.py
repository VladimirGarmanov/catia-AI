from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.desktop import DesktopTools, Window


def setup():
    window = Window(100, 9, "CATIA - Test.CATPart", (0, 0, 800, 600))
    backend = Mock()
    backend.window.return_value = window
    backend.capture.return_value = (b"png", 800, 600)
    backend.approve.return_value = True
    state = NS(reconciliation_required=False, document_id=lambda: "doc", mutation_started=False,
               revisions={"doc": 0})
    tool = DesktopTools(NS(active_document=NS(Name="Test.CATPart")), state,
                        backend_factory=lambda: backend, clock=lambda: 0)
    snapshot = tool.execute("catia_ui_snapshot", {})
    args = {"snapshot_id": snapshot["snapshot_id"], "reason": "test",
            "action": {"kind": "click", "x": 10, "y": 20}}
    return tool, backend, args


def test_denied_never_sends_and_consumes_snapshot():
    tool, backend, args = setup()
    backend.approve.return_value = False
    with pytest.raises(CADOperationError, match="declined"):
        tool.execute("catia_ui_action", args)
    backend.send.assert_not_called()
    assert tool.snapshot is None


def test_approved_one_input_and_not_verified():
    tool, backend, args = setup()
    result = tool.execute("catia_ui_action", args)
    backend.approve.assert_called_once()
    backend.send.assert_called_once()
    assert result["requires_reconciliation"] and not result["geometry_verified"]
    with pytest.raises(CADOperationError, match="fresh"):
        tool.execute("catia_ui_action", args)
    assert backend.send.call_count == 1


def test_out_of_bounds_no_confirmation_or_input():
    tool, backend, args = setup()
    args["action"]["x"] = 800
    with pytest.raises(CADOperationError, match="outside"):
        tool.execute("catia_ui_action", args)
    backend.approve.assert_not_called()
    backend.send.assert_not_called()


def test_uncertain_com_blocks_desktop():
    tool, backend, args = setup()
    tool.state.reconciliation_required = True
    with pytest.raises(CADOperationError, match="Reconcile"):
        tool.execute("catia_ui_action", args)
    backend.approve.assert_not_called()
    backend.send.assert_not_called()


def test_late_yes_never_sends():
    tool, backend, args = setup()
    times = iter([0, 0, 61])
    tool.clock = lambda: next(times)
    with pytest.raises(CADOperationError, match="expired"):
        tool.execute("catia_ui_action", args)
    backend.send.assert_not_called()


def test_cancelled_during_confirmation_never_sends():
    import threading
    tool, backend, args = setup()
    tool.cancel_event = threading.Event()
    def approve(_):
        tool.cancel_event.set()
        return True
    backend.approve.side_effect = approve
    with pytest.raises(CADOperationError, match="cancelled"):
        tool.execute("catia_ui_action", args)
    backend.send.assert_not_called()


def test_revision_change_rejects_old_image():
    tool, backend, args = setup()
    tool.state.revisions["doc"] = 1
    with pytest.raises(CADOperationError, match="fresh"):
        tool.execute("catia_ui_action", args)
    backend.approve.assert_not_called()
    backend.send.assert_not_called()
