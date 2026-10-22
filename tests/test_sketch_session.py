from types import SimpleNamespace as NS
from unittest.mock import Mock
import pytest

from catia_mcp.runtime import SessionState, CADOperationError
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.sketcher import SketcherTools
from catia_mcp.tools.sketch_session import SketchSessionTools


def collection(items):
    return NS(Count=len(items), Item=lambda i: items[i-1])


def setup():
    sketch = NS(Name="Existing", Factory2D=object(), OpenEdition=Mock(return_value=object()),
                GeometricElements=collection([]), Constraints=collection([]))
    part = NS(InWorkObject=sketch, Bodies=collection([NS(Sketches=collection([sketch]))]), HybridBodies=collection([]))
    doc = NS(Name="Test.CATPart", FullName="", Selection=NS(Count2=0))
    conn = NS(active_document=doc, get_active_part=lambda: part)
    state = SessionState(conn)
    editor = SketcherTools(conn)
    tool = SketchSessionTools(EngineeringTools(conn, state, editor))
    return tool, sketch, editor, part, conn


def test_adopt_does_not_reopen_or_create():
    tool, sketch, editor, part, conn = setup()
    result = tool.execute("catia_sketch_begin_edit", {"source": "in_work", "mode": "adopt_user_open", "user_confirmed_open": True})
    assert result["created_sketch"] is False and editor._active_factory is sketch.Factory2D
    sketch.OpenEdition.assert_not_called()
    editor._ensure_sketch_open()
    part.InWorkObject = NS(Name="Other")
    with pytest.raises(RuntimeError, match="target changed"):
        editor._ensure_sketch_open()


def test_open_existing_and_wrong_document_identity():
    tool, sketch, editor, part, conn = setup()
    tool.execute("catia_sketch_begin_edit", {"source": "in_work", "mode": "open"})
    sketch.OpenEdition.assert_called_once_with()
    conn.active_document = NS(Name="Test.CATPart", FullName="")
    with pytest.raises(RuntimeError, match="identity changed"):
        editor._ensure_sketch_open()


def test_unconfirmed_adoption_refused():
    tool, sketch, editor, part, conn = setup()
    with pytest.raises(CADOperationError, match="confirmation"):
        tool.execute("catia_sketch_begin_edit", {"source": "in_work", "mode": "adopt_user_open"})
    assert editor._active_sketch is None
    sketch.OpenEdition.assert_not_called()


def test_context_does_not_open_edition():
    tool, sketch, editor, part, conn = setup()
    result = tool.execute("catia_sketch_context", {})
    assert result["ui_edition"] == "unknown" and result["sketches"][0]["in_work"]
    sketch.OpenEdition.assert_not_called()


@pytest.mark.parametrize("initial,target", [(False, True), (True, False), (True, True)])
def test_construction_existing_geometry(initial, target):
    tool, sketch, editor, part, conn = setup()
    geometry = NS(Name="Line.1", Construction=initial)
    sketch.GeometricElements = collection([geometry])
    sketch.CenterLine = None
    sketch.Evaluate = Mock()
    tool.execute("catia_sketch_begin_edit", {"source": "in_work", "mode": "open"})
    handle = tool.state.register(geometry, "line2d")
    result = tool.execute("catia_sketch_set_construction", {"geometry_handle": handle, "construction": target})
    assert geometry.Construction is target and result["construction"] is target
    assert sketch.Evaluate.call_count == int(initial != target)


def test_construction_rejects_foreign_geometry_and_axis():
    tool, sketch, editor, part, conn = setup()
    geometry = NS(Name="Line.1", Construction=True)
    sketch.Evaluate = Mock()
    tool.execute("catia_sketch_begin_edit", {"source": "in_work", "mode": "open"})
    handle = tool.state.register(geometry, "line2d")
    args = {"geometry_handle": handle, "construction": False}
    with pytest.raises(CADOperationError, match="belong"):
        tool.execute("catia_sketch_set_construction", args)
    sketch.GeometricElements = collection([geometry])
    sketch.CenterLine = geometry
    with pytest.raises(CADOperationError, match="axis"):
        tool.execute("catia_sketch_set_construction", args)
    assert geometry.Construction is True
    sketch.Evaluate.assert_not_called()
