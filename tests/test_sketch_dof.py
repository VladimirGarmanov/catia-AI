"""DOF counting estimate and close enforcement; mocks do not run CATIA's solver."""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import CADOperationError
from catia_mcp.server import CATIAMCPServer
from catia_mcp.sketch_dof import estimate_dof


class Collection:
    def __init__(self, *items):
        self.items = list(items)

    @property
    def Count(self):
        return len(self.items)

    def Item(self, index):
        return self.items[index - 1]


def point(name):
    return NS(Name=name, GeometricType=2, Construction=False)


def line(name, start=None, end=None):
    return NS(Name=name, GeometricType=3, StartPoint=start, EndPoint=end, Construction=False)


def cst(kind, *elements, mode=0, inactive=False, **extra):
    refs = [NS(DisplayName=e.Name) for e in elements]
    return NS(Name=f"C{kind}", Type=kind, Mode=mode, IsInactive=Mock(return_value=inactive),
              GetConstraintElement=lambda i: refs[i - 1], **extra)


AXIS = NS(Name="AbsoluteAxis", GeometricType=1, Origin=NS(Name="Origin", GeometricType=2),
          HorizontalReference=NS(Name="HDirection", GeometricType=3),
          VerticalReference=NS(Name="VDirection", GeometricType=3))
PART = NS(CreateReferenceFromObject=lambda obj: NS(DisplayName=obj.Name))


def rectangle(shared=True, anchor=False):
    """Four lines; shared vertices or own endpoints joined by four coincidences."""
    if shared:
        v = [point(f"Point.{i}") for i in range(1, 5)]
        lines = [line(f"Line.{i + 1}", v[i], v[(i + 1) % 4]) for i in range(4)]
        geometry, constraints = [AXIS, *v, *lines], []
    else:
        ends = [(point(f"P{i}a"), point(f"P{i}b")) for i in range(4)]
        lines = [line(f"Line.{i + 1}", *ends[i]) for i in range(4)]
        geometry = [AXIS, *lines]
        constraints = [cst(2, ends[i][1], ends[(i + 1) % 4][0]) for i in range(4)]
        v = [ends[i][0] for i in range(4)]
    constraints += [cst(10, lines[0]), cst(13, lines[1]), cst(10, lines[2]), cst(13, lines[3]),
                    cst(5, lines[0]), cst(5, lines[1])]
    if anchor:
        constraints.append(cst(2, v[0], AXIS.Origin))
    return NS(Name="Sketch.1", AbsoluteAxis=AXIS, GeometricElements=Collection(*geometry),
              Constraints=Collection(*constraints))


@pytest.mark.parametrize("shared", [True, False])
def test_unanchored_rectangle_is_proven_under_constrained(shared):
    report = estimate_dof(rectangle(shared), PART)
    assert report["status"] == "under_constrained" and report["certain"]
    assert report["estimated_dof"] == 2 and report["total_dof"] == (8 if shared else 16)
    assert report["fully_constrained"] is None and report["live_validated"] is False
    assert any("origin" in hint for hint in report["hints"])


@pytest.mark.parametrize("shared", [True, False])
def test_anchored_rectangle_is_only_possibly_fully_constrained(shared):
    report = estimate_dof(rectangle(shared, anchor=True), PART)
    assert report["status"] == "possibly_fully_constrained" and report["estimated_dof"] == 0
    assert "NOT proof" in report["proof"] and report["fully_constrained"] is None


def test_reference_inactive_and_redundant_constraints():
    sketch = rectangle(anchor=True)
    lines = sketch.GeometricElements.items[5:]
    sketch.Constraints.items += [cst(5, lines[2], mode=1), cst(5, lines[3], inactive=True)]
    assert estimate_dof(sketch, PART)["estimated_dof"] == 0
    sketch.Constraints.items.append(cst(5, lines[2]))
    report = estimate_dof(sketch, PART)
    assert report["status"] == "over_or_redundant" and report["estimated_dof"] == -1


def test_free_point_and_circle_arc_counts():
    free = point("Point.9")
    center = point("Center")
    circle = NS(Name="Circle.1", GeometricType=5, CenterPoint=center, StartPoint=None, EndPoint=None)
    a, b = point("A"), point("B")
    arc = NS(Name="Arc.1", GeometricType=5, CenterPoint=center, StartPoint=a, EndPoint=b)
    sketch = NS(AbsoluteAxis=AXIS, GeometricElements=Collection(AXIS, free, circle, arc),
                Constraints=Collection(cst(3, circle, AXIS.Origin), cst(14, circle)))
    report = estimate_dof(sketch, PART)
    # free 2 + center 2 + circle radius 1 + arc ends 4 + arc (-1) = 8; removed 3.
    assert report["total_dof"] == 8 and report["estimated_dof"] == 5
    names = {item["name"] for item in report["likely_free_elements"]}
    assert {"Point.9", "A", "B"} <= names and "Center" not in names


def test_spline_and_unmatched_constraint_make_estimate_unknown():
    sketch = rectangle()
    sketch.GeometricElements.items.append(NS(Name="Spline.1", GeometricType=9))
    report = estimate_dof(sketch, PART)
    assert report["status"] == "unknown" and report["estimated_dof"] is None
    assert report["unknown_elements"][0]["name"] == "Spline.1"
    sketch = rectangle()
    sketch.Constraints.items.append(cst(1, NS(Name="Pad.1\\Face"), sketch.GeometricElements.items[1]))
    assert estimate_dof(sketch, PART)["unresolved_constraints"][0]["reason"].endswith("matches no sketch geometry")
    sketch = rectangle()
    sketch.Constraints.items.append(cst(0, sketch.GeometricElements.items[1]))
    assert "Fix" in estimate_dof(sketch, PART)["unresolved_constraints"][0]["reason"]


@pytest.fixture
def rig():
    server = CATIAMCPServer()
    sketch = rectangle()
    sketch.CloseEdition, sketch.Evaluate = Mock(), Mock()
    part = NS(Bodies=Collection(NS(Sketches=Collection(sketch))), HybridBodies=Collection(),
              IsUpToDate=Mock(return_value=True), UpdateObject=Mock(), Update=Mock(),
              CreateReferenceFromObject=PART.CreateReferenceFromObject, InWorkObject=None)
    document = NS(Name="Part.CATPart", FullName="", Part=part)
    server.connection.app = NS(Caption="Mock CATIA", ActiveDocument=document, RefreshDisplay=True)
    server.connection.refresh_display = Mock()
    context = server.session.bind()
    editor = server.sketcher_tools
    editor._active_sketch, editor._active_document = sketch, document
    editor._active_document_identity = editor._document_identity(document)
    editor._provenance_complete = True  # as if created by catia_create_sketch in this session
    yield NS(server=server, sketch=sketch, part=part, context=context, document=document)
    server.worker.shutdown()


def close(rig, request_id, **args):
    return rig.server._execute_serial("catia_close_sketch", {
        "document_id": rig.context["document_id"], "request_id": request_id,
        "expected_revision": rig.server.session.revisions[rig.context["document_id"]], **args})


def test_read_tool_reports_bound_sketch_without_edition_change(rig):
    result = rig.server._execute_serial("catia_sketch_dof", {})
    assert result["ok"] and result["status"] == "under_constrained" and result["server_bound_open"]
    assert "catia_sketch_dof" in rig.server.read_tool_names()
    rig.sketch.CloseEdition.assert_not_called()
    rig.sketch.Evaluate.assert_not_called()


def test_close_refuses_under_constrained_without_partial_failure(rig):
    result = close(rig, "c1")
    assert not result["ok"] and result["code"] == "SKETCH_UNDER_CONSTRAINED"
    assert result["status"] == "failed" and result["error"]["details"]["edition_left_open"]
    assert result["error"]["details"]["dof_check"]["estimated_dof"] == 2
    rig.sketch.CloseEdition.assert_not_called()
    assert rig.server.sketcher_tools._active_sketch is rig.sketch
    assert not rig.server.session.reconciliation_required
    bad = close(rig, "c2", accept_under_constrained=True)
    assert bad["code"] == "INVALID_ARGUMENT"
    blank = close(rig, "c3", accept_under_constrained=True, under_constrained_reason="  ")
    assert blank["code"] == "INVALID_ARGUMENT"
    rig.sketch.CloseEdition.assert_not_called()


def test_close_override_with_reason_is_logged(rig):
    result = close(rig, "c4", accept_under_constrained=True,
                   under_constrained_reason="Position set later by an assembly mate")
    assert result["ok"] and result["under_constrained_override"]["reason"].startswith("Position")
    assert any("override" in warning for warning in result["warnings"])
    rig.sketch.CloseEdition.assert_called_once()
    assert rig.server.sketcher_tools._active_sketch is None


def test_close_passes_possibly_fully_constrained_and_warns_on_unknown(rig):
    anchored = rectangle(anchor=True)
    rig.sketch.Constraints = anchored.Constraints
    rig.sketch.GeometricElements = anchored.GeometricElements
    result = close(rig, "c5")
    assert result["ok"] and result["dof_check"]["status"] == "possibly_fully_constrained"
    rig.sketch.CloseEdition.assert_called_once()


def test_close_does_not_block_unknown_spline_estimate(rig):
    rig.sketch.GeometricElements.items.append(NS(Name="Spline.1", GeometricType=9))
    result = close(rig, "c6")
    assert result["ok"] and result["dof_check"]["status"] == "unknown"
    assert any("unknown" in warning for warning in result["warnings"])


def test_direct_guard_raises_typed_code():
    server = CATIAMCPServer()
    editor = server.sketcher_tools
    sketch = rectangle()
    document = NS(Name="Part.CATPart", FullName="")
    editor.conn = NS(active_document=document, get_active_part=lambda: PART)
    editor._active_sketch, editor._active_document = sketch, document
    editor._active_document_identity = editor._document_identity(document)
    editor._provenance_complete = True
    with pytest.raises(CADOperationError) as error:
        editor._close_sketch({})
    assert error.value.code == "SKETCH_UNDER_CONSTRAINED"
    server.worker.shutdown()


def parallel_distance_rectangle(config):
    """Shared-vertex rectangle anchored at the origin: H(L1), V(L2), V(L4), Length(L1) and a
    distance L3-L1 that is fully determining only when DistanceConfig forces parallelism."""
    v = [point(f"Point.{i}") for i in range(1, 5)]
    lines = [line(f"Line.{i + 1}", v[i], v[(i + 1) % 4]) for i in range(4)]
    constraints = [cst(2, v[0], AXIS.Origin), cst(10, lines[0]), cst(13, lines[1]), cst(13, lines[3]),
                   cst(5, lines[0]), cst(1, lines[2], lines[0], DistanceConfig=config)]
    return NS(Name="Sketch.1", AbsoluteAxis=AXIS, GeometricElements=Collection(AXIS, *v, *lines),
              Constraints=Collection(*constraints))


def test_parallel_distance_config_removes_two_dof():
    assert estimate_dof(parallel_distance_rectangle(1), PART)["status"] == "possibly_fully_constrained"
    report = estimate_dof(parallel_distance_rectangle(0), PART)
    assert report["status"] == "under_constrained" and report["estimated_dof"] == 1


def test_unreadable_distance_config_between_curves_is_unresolved():
    sketch = parallel_distance_rectangle(1)
    distance = sketch.Constraints.items[-1]
    del distance.DistanceConfig
    report = estimate_dof(sketch, PART)
    assert report["status"] == "unknown" and "DistanceConfig" in report["unresolved_constraints"][0]["reason"]


def test_projected_geometry_is_fixed_and_unknown_provenance_draws_no_proof():
    sketch = rectangle(anchor=True)
    projected = line("Mark.1", point("Mark.1a"), point("Mark.1b"))
    sketch.GeometricElements.items.append(projected)
    assert estimate_dof(sketch, PART)["status"] == "under_constrained"  # counted free: the old false proof
    linked = estimate_dof(sketch, PART, fixed_geometry=(projected,))
    assert linked["status"] == "possibly_fully_constrained" and linked["linked_geometry_count"] == 1
    opened = estimate_dof(rectangle(), PART, provenance_complete=False)
    assert opened["status"] == "unknown" and opened["certain"] is False and opened["estimated_dof"] is None


def test_close_does_not_refuse_sketch_with_unknown_provenance(rig):
    rig.server.sketcher_tools._provenance_complete = False
    rig.sketch.Constraints.items.pop()  # under-constrained by count, but provenance is unknown
    result = close(rig, "c7")
    assert result["ok"] and result["dof_check"]["status"] == "unknown"
    rig.sketch.CloseEdition.assert_called_once()


@pytest.mark.parametrize("kind,elements,weight", [
    (4, ("line", "circle"), 1), (16, ("point", "line"), 2), (17, ("point", "point", "line"), 1),
    (15, ("point", "point", "line"), 2), (15, ("line", "line", "line"), 2), (15, ("circle", "circle", "line"), 3),
    (2, ("line", "line"), 2), (2, ("circle", "circle"), 3), (2, ("point", "circle"), 1),
])
def test_modelled_weights(kind, elements, weight):
    from catia_mcp.sketch_dof import _weight
    assert _weight(kind, list(elements)) == (weight, None)


@pytest.mark.parametrize("kind,elements", [(15, ("point", "line", "line")), (2, ("line", "circle"))])
def test_unmodelled_combinations_are_rejected(kind, elements):
    from catia_mcp.sketch_dof import _weight
    weight, problem = _weight(kind, list(elements))
    assert weight is None and problem


def test_ellipse_counts_and_truncation():
    center = point("C")
    ellipse = NS(Name="Ellipse.1", GeometricType=8, CenterPoint=center, Construction=False)
    sketch = NS(Name="S", AbsoluteAxis=AXIS, GeometricElements=Collection(AXIS, center, ellipse),
                Constraints=Collection())
    report = estimate_dof(sketch, PART)
    assert report["total_dof"] == 5 and report["status"] == "under_constrained"
    many = NS(Name="S", AbsoluteAxis=AXIS, GeometricElements=Collection(AXIS, point("A"), point("B")),
              Constraints=Collection())
    assert estimate_dof(many, PART, max_elements=1)["status"] == "unknown"


def test_dimension_mode_read_failure_is_unresolved_and_geometric_assumed_driving():
    sketch = rectangle(anchor=True)
    length = next(c for c in sketch.Constraints.items if c.Type == 5)
    del length.Mode
    horizontal = next(c for c in sketch.Constraints.items if c.Type == 10)
    del horizontal.Mode
    report = estimate_dof(sketch, PART)
    assert report["status"] == "unknown"
    assert any(r.get("mode_assumed") == "driving" for r in report["constraints"])
    assert any("dimension mode" in r.get("unresolved", "") for r in report["constraints"])


def test_sketch_dof_is_routed_by_capabilities():
    from catia_mcp.tools.capabilities import IMPLEMENTATIONS as LINKS
    assert "catia_sketch_dof" in LINKS[33] and "catia_sketch_dof" in LINKS[210]
