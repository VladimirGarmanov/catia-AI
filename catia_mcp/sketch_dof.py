"""Gruebler-style DOF estimate for a sketch; an upper-bound proof of under-constraint only.

total = 2 per unique Point2D + intrinsic curve parameters; removed = sum of weights of
active driving non-Fix constraints. Redundant constraints only make the true DOF
LARGER than the estimate, so estimated_dof > 0 with everything resolved proves
under-constraint. <= 0 never proves full constraint. Every assumption below must
only lower `total` or raise `removed`, keeping that proof direction sound.
Sources: CAA SketcherInterfaces (CatGeometricType, Curve2D.StartPoint/EndPoint,
Circle2D/Ellipse2D.CenterPoint, Sketch.AbsoluteAxis, Axis2D) and MecModInterfaces
(CatConstraintType, CatConstraintMode, Constraint.GetConstraintElement -> Reference,
InfInterfaces Reference.DisplayName). Windows validation pending.
"""
from catia_mcp.runtime import CADOperationError, same_object

# CatGeometricType: 1 Axis2D, 2 Point2D, 3 Line2D, 4 ControlPoint2D, 5 Circle2D,
# 6 Hyperbola2D, 7 Parabola2D, 8 Ellipse2D, 9 Spline2D.
POINT, LINE, CIRCLE, ELLIPSE = 2, 3, 5, 8
KINDS = {POINT: "point", LINE: "line", CIRCLE: "circle", ELLIPSE: "ellipse"}
# CatConstraintType element counts (enum_CatConstraintType_27587).
ELEMENTS = {0: 1, 1: 2, 2: 2, 3: 2, 4: 2, 5: 1, 6: 2, 8: 2, 10: 1, 11: 2, 13: 1,
            14: 1, 15: 3, 16: 2, 17: 3, 18: 1, 19: 1}
DIMENSIONAL = {1, 5, 6, 14, 18, 19}
UNIT = {1, 4, 5, 6, 8, 10, 11, 13, 14, 17, 18, 19}
TYPE_NAMES = {0: "fix", 1: "distance", 2: "on", 3: "concentricity", 4: "tangency", 5: "length",
              6: "angle", 8: "parallelism", 10: "horizontality", 11: "perpendicularity",
              13: "verticality", 14: "radius", 15: "symmetry", 16: "midpoint",
              17: "equidistance", 18: "major_radius", 19: "minor_radius"}
CURVES = {"line", "circle", "ellipse"}


def _get(obj, attr):
    try:
        return getattr(obj, attr)
    except Exception:
        return None


def _weight(kind, kinds):
    if kind in UNIT:
        return 1, None
    if kind in {3, 16}:
        return 2, None
    if kind == 2:
        a, b = sorted(kinds, key=lambda k: k != "point")
        if a == b == "point":
            return 2, None
        if a == "point" and b in CURVES:
            return 1, None
        if a == b == "line":
            return 2, None  # collinear supports
        if a == b == "circle":
            return 3, None  # identical supports: center and radius
        return None, f"on() between {a} and {b} is not modelled"
    if kind == 15:
        # Lines count 2 (support angle and offset), not 1: a lower weight would
        # inflate the estimate and could falsely prove under-constraint.
        weight = {"point": 2, "line": 2, "circle": 3}.get(kinds[0])
        if kinds[0] != kinds[1] or kinds[2] != "line" or weight is None:
            return None, "symmetry element kinds are not modelled"
        return weight, None
    return None, f"constraint type {kind} is not modelled"


def estimate_dof(sketch, part, *, register=None, max_constraints=1000, max_elements=5000,
                 fixed_geometry=(), provenance_complete=True):
    """fixed_geometry: elements known to be projected/intersected 3D links (0 DOF).
    provenance_complete=False: the sketch may hold such links this session did not
    create; COM cannot identify them, so no proof is drawn from a positive estimate."""
    if isinstance(max_constraints, bool) or not isinstance(max_constraints, int) or not 1 <= max_constraints <= 5000:
        raise CADOperationError("INVALID_ARGUMENT", "max_constraints must be an integer in 1..5000")
    entities, unknown, assumptions, failures = [], [], [], []

    def entity(obj, kind, dof, fixed=False, name=None):
        for old in entities:
            if same_object(old["obj"], obj):
                return old
        row = {"obj": obj, "kind": kind, "dof": dof, "fixed": fixed, "points": [],
               "name": name or str(_get(obj, "Name") or f"{kind}.{len(entities) + 1}")}
        entities.append(row)
        return row

    axis = _get(sketch, "AbsoluteAxis")
    if axis is None:
        failures.append("AbsoluteAxis unavailable; constraints to origin/axes stay unresolved")
    else:
        for attr, kind in (("Origin", "point"), ("HorizontalReference", "line"), ("VerticalReference", "line")):
            value = _get(axis, attr)
            if value is not None:
                entity(value, kind, 0, True, f"AbsoluteAxis.{attr}")
    try:
        geometry = sketch.GeometricElements
        count = int(geometry.Count)
    except Exception as exc:
        raise CADOperationError("GEOMETRY_READ_FAILED", f"Cannot read sketch geometry: {exc}") from exc
    for index in range(1, min(count, max_elements) + 1):
        try:
            obj = geometry.Item(index)
        except Exception as exc:
            failures.append(f"geometry {index}: {exc}")
            continue
        if any(row["fixed"] and same_object(row["obj"], obj) for row in entities) or \
                (axis is not None and same_object(obj, axis)):
            continue
        try:
            gtype = int(obj.GeometricType)
        except Exception:
            gtype = None
        if gtype == 1:
            continue  # the sketch absolute axis itself: 0 DOF
        if gtype not in KINDS:
            unknown.append({"index": index, "name": str(_get(obj, "Name")), "geometric_type": gtype})
            continue
        if any(same_object(obj, linked) for linked in fixed_geometry):
            row = entity(obj, KINDS.get(gtype, "geometry"), 0, True)
            row["linked"] = True
            for attr in ("StartPoint", "EndPoint", "CenterPoint"):
                point = _get(obj, attr)
                if point is not None:
                    entity(point, "point", 0, True)  # endpoints of an immobile 3D link
            continue
        if gtype == POINT:
            entity(obj, "point", 2)
            continue
        ends = [p for p in (_get(obj, "StartPoint"), _get(obj, "EndPoint")) if p is not None]
        center = _get(obj, "CenterPoint") if gtype != LINE else None
        if gtype == LINE:
            # Segment endpoints without Point2D objects remain intrinsic (2 each).
            # Both missing could be an infinite line: count only its 2-DOF support.
            intrinsic = 2 if len(ends) < 2 else 0
            if not ends:
                assumptions.append(f"{_get(obj, 'Name')}: no endpoint Point2D; counted as a 2-DOF support (lower bound)")
        else:
            base = 1 if gtype == CIRCLE else 3  # radius / major, minor radius and angle
            if not ends:
                intrinsic = base  # assumed closed: an arc would only add DOF
                assumptions.append(f"{_get(obj, 'Name')}: no end points; assumed closed (lower bound)")
            else:
                intrinsic = base + (2 - len(ends)) - len(ends)  # free end angle, point-on-curve
            if center is None:
                intrinsic += 2
        curve = entity(obj, KINDS[gtype], intrinsic)
        try:
            curve["construction"] = bool(obj.Construction)
        except Exception:
            pass
        for point in ends + ([center] if center is not None else []):
            curve["points"].append(entity(point, "point", 2))  # dedupes shared and fixed points
    truncated = count > max_elements
    names = {}
    for row in entities:
        keys = {row["name"], str(_get(row["obj"], "Name"))}
        try:
            keys.add(str(part.CreateReferenceFromObject(row["obj"]).DisplayName))
        except Exception:
            pass
        for key in keys:
            names.setdefault(key, []).append(row)

    try:
        constraints = sketch.Constraints
        total_constraints = int(constraints.Count)
    except Exception as exc:
        raise CADOperationError("CONSTRAINT_READ_FAILED", f"Cannot read sketch constraints: {exc}") from exc
    rows, credit, touched = [], {}, set()
    for index in range(1, min(total_constraints, max_constraints) + 1):
        row = {"index": index, "name": None, "type": None, "weight": 0, "counted": False, "elements": []}
        rows.append(row)
        try:
            cst = constraints.Item(index)
            row["name"] = str(_get(cst, "Name"))
            kind = row["type"] = int(cst.Type)
            inactive = bool(cst.IsInactive())
        except Exception as exc:
            row["unresolved"] = f"cannot read type/activation: {exc}"
            continue
        try:
            mode = int(cst.Mode)
        except Exception as exc:
            if kind in DIMENSIONAL:
                row["unresolved"] = f"cannot read dimension mode: {exc}"
                continue
            mode = 0  # geometric relations have no driven/measurement mode
            row["mode_assumed"] = "driving"
        row["type_name"] = TYPE_NAMES.get(kind)
        if inactive:
            row["reason"] = "inactive"
            continue
        if mode == 1:
            row["reason"] = "reference (driven) mode"
            continue
        if mode != 0:
            row["unresolved"] = f"unknown mode {mode}"
            continue
        if kind == 0:
            row["unresolved"] = "existing active Fix constraint; its removed DOF is not modelled (Fix is forbidden)"
            continue
        if kind not in ELEMENTS:
            row["unresolved"] = f"constraint type {kind} is not modelled"
            continue
        resolved = []
        for position in range(1, ELEMENTS[kind] + 1):
            try:
                key = str(cst.GetConstraintElement(position).DisplayName)
            except Exception as exc:
                row["unresolved"] = f"element {position} unreadable: {exc}"
                break
            matches = names.get(key, [])
            unique = [m for i, m in enumerate(matches) if all(m is not o for o in matches[:i])]
            if len(unique) != 1:
                row["unresolved"] = f"element {position} {key!r} {'is ambiguous' if unique else 'matches no sketch geometry'}"
                break
            resolved.append(unique[0])
        if "unresolved" in row:
            continue
        row["elements"] = [m["name"] for m in resolved]
        weight, problem = _weight(kind, [m["kind"] for m in resolved])
        if problem:
            row["unresolved"] = problem
            continue
        if kind == 1 and all(m["kind"] in CURVES for m in resolved):
            # CatConstraintDistConfig: nonzero (parallel variants) also forces parallelism.
            try:
                config = int(cst.DistanceConfig)
            except Exception as exc:
                row["unresolved"] = f"cannot read DistanceConfig of a curve-curve distance: {exc}"
                continue
            row["distance_config"] = config
            if config and all(m["kind"] == "line" for m in resolved):
                weight = 2
            elif config:
                row["unresolved"] = f"DistanceConfig {config} between non-line curves is not modelled"
                continue
        row.update(weight=weight, counted=True)
        for m in resolved:
            touched.add(id(m))
            for target in [m] + m["points"]:
                credit[id(target)] = credit.get(id(target), 0) + weight
    if int(constraints.Count) != total_constraints:
        raise CADOperationError("SESSION_STATE_UNKNOWN", "Constraint collection changed during inspection; reread the sketch")

    free = [row for row in entities if not row["fixed"]]
    total = sum(row["dof"] for row in free)
    removed = sum(row["weight"] for row in rows)
    estimate = total - removed
    unresolved = [{"index": r["index"], "name": r["name"], "type": r["type"], "reason": r["unresolved"]}
                  for r in rows if "unresolved" in r]
    truncated = truncated or total_constraints > max_constraints
    certain = not (unknown or unresolved or truncated or failures or not provenance_complete)
    status = ("unknown" if not certain else "under_constrained" if estimate > 0 else
              "possibly_fully_constrained" if estimate == 0 else "over_or_redundant")
    owners = {id(p) for row in free for p in row["points"]}
    likely = []
    for row in free:
        got = credit.get(id(row), 0)
        if row["kind"] == "point":
            loose = got < 2
        else:
            loose = (id(row) not in touched and not any(id(p) in touched for p in row["points"])) or got < row["dof"]
        if loose:
            item = {"name": row["name"], "kind": row["kind"], "removed_dof_credit": got}
            if register is not None:
                item["handle"] = register(row["obj"], row["kind"] + "2d" if row["kind"] != "point" else "point2d")
            likely.append(item)
    hints = []
    anchored = any(id(row) in touched for row in entities if row["fixed"])
    if status == "under_constrained" and not anchored:
        hints.append("No counted constraint references the sketch origin or H/V axes: position is probably free. "
                     "Locate a point/curve from the origin with coincidence, distances or concentricity.")
    if status == "under_constrained" and not likely:
        hints.append("Every element carries some constraint; the remaining freedom is probably a rigid motion "
                     "or a missing size/angle. Add the intended dimension, never Fix/AutoConstraint.")
    proof = {
        "under_constrained": "estimated_dof > 0 with every element and constraint resolved. Redundant constraints only "
                             "increase the true DOF, so the sketch is under-constrained.",
        "possibly_fully_constrained": "estimated_dof == 0 is NOT proof: redundant constraints may hide free DOF. "
                                      "Native Sketch Analysis remains authoritative.",
        "over_or_redundant": "estimated_dof < 0: at least one constraint is redundant or conflicting; free DOF may "
                             "still exist. Inspect constraint statuses and native Sketch Analysis.",
        "unknown": "Some geometry or constraints could not be modelled, or the sketch may contain projected/"
                   "intersected 3D links this session did not create (COM cannot identify them); no conclusion is drawn.",
    }[status]
    return {
        "ok": True, "method": "gruebler_count", "status": status, "certain": certain,
        "estimated_dof": estimate if certain else None,
        "partial_estimated_dof": None if certain else estimate,
        "provenance_complete": provenance_complete,
        "linked_geometry_count": sum(bool(r.get("linked")) for r in entities),
        "total_dof": total, "removed_dof": removed, "proof": proof,
        "fully_constrained": None, "live_validated": False,
        "element_count": len(free), "point_count": sum(r["kind"] == "point" for r in free),
        "curve_owned_point_count": len(owners),
        "elements": [{"name": r["name"], "kind": r["kind"], "dof": r["dof"],
                      **({"construction": r["construction"]} if "construction" in r else {})} for r in free],
        "constraints": rows, "constraint_count": total_constraints, "truncated": truncated,
        "unknown_elements": unknown, "unresolved_constraints": unresolved, "read_failures": failures,
        "likely_free_elements": likely, "hints": hints, "assumptions": assumptions + [
            "Weights: dimension/H/V/parallel/perpendicular/tangency/equidistance 1; point-point and "
            "line-line coincidence, concentricity, midpoint 2; point-on-curve 1; symmetry 2 (points/lines), 3 (circles).",
            "Projected/intersected geometry created by catia_sketch_import_geometry counts as fixed (0 DOF); "
            "a sketch whose links this session cannot account for (opened/adopted) yields status unknown.",
            "A line-line distance with nonzero DistanceConfig also imposes parallelism (weight 2).",
            "Constraint elements are matched to sketch geometry by Reference.DisplayName (Windows validation pending)."],
        "warning": "DOF estimate by counting, not CATIA solver rank. Only estimated_dof > 0 with certain=true is a "
                   "conclusion (under-constrained). Never use Fix or AutoConstraint to reach zero.",
    }


def dof_summary(report):
    return {key: report.get(key) for key in ("status", "certain", "estimated_dof", "partial_estimated_dof",
                                             "likely_free_elements", "unknown_elements", "unresolved_constraints",
                                             "hints")}
