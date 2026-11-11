"""catia_point: GSD points defined the way CATIA's Point Definition dialog does.

Constructors, argument order and enum values follow the cached CAA V5
GSMInterfaces pages (HybridShapeFactory.AddNewPoint*, HybridShapePointCoord,
HybridShapePointOnCurve, HybridShapePointBetween, HybridShapePointCenter,
HybridShapePointTangent, HybridShapePointExplicit). Every reference is
resolved and every combination validated before the first factory call.
Live Windows validation is pending for all modes.
"""
from __future__ import annotations

import math

from catia_mcp.com_arrays import read_array
from catia_mcp.runtime import CADOperationError, same_object
from catia_mcp.tools.engineering import HANDLE, NUMBER
from catia_mcp.tools.operations import (
    BOOL, CURVE, LINE, POINT, SURFACE, VECTOR, OperationTools, array, group, unit_vector,
)

RATIO = {"type": "number", "minimum": 0, "maximum": 1}
NONNEG = {"type": "number", "minimum": 0}
# HybridShapePointOnCurve.DistanceType: 1 geodesic, -1 euclidean (CAA).
DISTANCE_TYPES = {"geodesic": 1, "euclidean": -1}
# HybridShapePointOnCurve.OnCurveType: 0 distance on curve, 1 along direction, 2 ratio (CAA).
ON_CURVE_TYPES = {"on_curve_distance": 0, "on_curve_direction": 1, "on_curve_ratio": 2}
TOLERANCE_MM = 1e-3
PLANE = {"plane", "face"}

MODES = {
    "coordinates": {"coordinates_mm": VECTOR},
    "on_curve_distance": {"curve_handle": HANDLE, "distance_mm": NUMBER},
    "on_curve_ratio": {"curve_handle": HANDLE, "ratio": RATIO},
    "on_curve_direction": {"curve_handle": HANDLE, "distance_mm": NUMBER},
    "on_plane": {"plane_handle": HANDLE, "plane_coordinates_mm": array(NUMBER, 2, 2)},
    "on_surface": {"surface_handle": HANDLE, "distance_mm": NONNEG},
    "center": {"element_handle": HANDLE},
    "tangent_on_curve": {"curve_handle": HANDLE},
    "between": {"first_point_handle": HANDLE, "second_point_handle": HANDLE},
    "datum": {"source_handle": HANDLE, "confirm_non_associative": {"const": True}},
}
REFERENCE = {"reference_point_handle": HANDLE}
DIRECTION = {"direction": VECTOR, "direction_handle": HANDLE}
OPTIONAL = {
    "coordinates": {**REFERENCE, "axis_system_handle": HANDLE},
    "on_curve_distance": {**REFERENCE, "reverse": BOOL, "distance_type": {"enum": list(DISTANCE_TYPES)}},
    "on_curve_ratio": {**REFERENCE, "reverse": BOOL},
    "on_curve_direction": {**REFERENCE, **DIRECTION, "reverse": BOOL},
    "on_plane": dict(REFERENCE),
    "on_surface": {**REFERENCE, **DIRECTION},
    "tangent_on_curve": dict(DIRECTION),
    "between": {"ratio": RATIO, "middle": {"const": True}, "support_handle": HANDLE},
}
COMMON_OPTIONAL = {"name": HANDLE}
KINDS = {"reference_point_handle": POINT, "axis_system_handle": {"axis_system"},
         "curve_handle": CURVE, "plane_handle": PLANE, "surface_handle": SURFACE,
         "element_handle": {"curve", "circle2d", "edge", "surface"}, "first_point_handle": POINT,
         "second_point_handle": POINT, "support_handle": CURVE | SURFACE,
         "direction_handle": LINE | {"plane"}, "source_handle": {"point"}}

DESCRIPTION = (
    "Create ONE GSD point like CATIA's Point Definition dialog, appended to an explicit geoset. "
    "Prefer relational definitions: on_curve_distance (geodesic|euclidean, optional reference point, reverse), "
    "on_curve_ratio, on_curve_direction, on_plane (H/V mm, optional reference point), on_surface "
    "(direction + geodesic distance), center (circle/ellipse/sphere center = concentric), tangent_on_curve "
    "(curve + direction; may yield several points), between (ratio or middle=true, optional support; CAA "
    "documents the ratio direction inconsistently, so the measured side is reported, never assumed). coordinates: Part mm, or relative to reference point and/or axis system. datum: explicit "
    "NON-associative copy, needs confirm_non_associative=true. Directions: vector in Part frame or line/plane "
    "handle (exactly one). Reads definition values and measured absolute mm coordinates back; mismatch is a "
    "failure that leaves the point behind. live_validated=false; Windows validation pending.")


def _with_optional(definition):
    """Optional per-mode fields: allowed by propertyNames, never required."""
    schema = definition["inputSchema"]
    for variant in schema["oneOf"]:
        extra = {**OPTIONAL.get(variant["properties"]["mode"]["const"], {}), **COMMON_OPTIONAL}
        variant["propertyNames"]["enum"] = sorted(set(variant["propertyNames"]["enum"]) | set(extra))
        for key, value in extra.items():
            current = schema["properties"].get(key)
            if current is None:
                schema["properties"][key] = value
            elif current != value and value not in current.get("anyOf", []):
                schema["properties"][key] = {"anyOf": [*current.get("anyOf", [current]), value]}
    return definition


def _finite(values, label):
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise CADOperationError("INVALID_ARGUMENT", f"{label} must contain finite numbers")
    return [float(v) for v in values]


def _close(left, right, tolerance=TOLERANCE_MM):
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


class PointTools(OperationTools):
    def get_tool_definitions(self):
        return [_with_optional(group("catia_point", DESCRIPTION, MODES, {"container_handle": HANDLE}))]

    def execute(self, name, a):
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition before 3D operations")
        return self.point(a)

    # Validation never calls the HybridShapeFactory.
    def validate(self, a):
        m = a["mode"]
        allowed = {"mode", "container_handle", *MODES[m], *OPTIONAL.get(m, {}), *COMMON_OPTIONAL,
                   "document_id", "expected_revision", "request_id"}
        unexpected = sorted(set(a) - allowed)
        missing = sorted(set(MODES[m]) - set(a))
        if unexpected or missing:
            raise CADOperationError("INVALID_ARGUMENT", f"{m}: unexpected {unexpected}, missing {missing}")
        if set(DIRECTION) & set(OPTIONAL.get(m, {})):
            supplied = [k for k in DIRECTION if k in a]
            if len(supplied) != 1:
                raise CADOperationError("INVALID_ARGUMENT", f"{m} requires exactly one of direction or direction_handle")
            if "direction" in a:
                unit_vector(_finite(a["direction"], "direction"))
        for key in ("coordinates_mm", "plane_coordinates_mm"):
            if key in a:
                _finite(a[key], key)
        for key in ("distance_mm", "ratio"):
            if key in a:
                _finite([a[key]], key)
        if "ratio" in a and not 0 <= a["ratio"] <= 1:
            raise CADOperationError("INVALID_ARGUMENT", "ratio must be within [0, 1]")
        if m == "on_curve_distance" and a.get("distance_type") == "euclidean" and a["distance_mm"] < 0:
            raise CADOperationError("INVALID_ARGUMENT", "Euclidean distance is a circle radius and must be >= 0")
        if m == "on_surface" and a["distance_mm"] < 0:
            raise CADOperationError("INVALID_ARGUMENT", "on_surface geodesic distance must be >= 0")
        if m == "between" and ("ratio" in a) == ("middle" in a):
            raise CADOperationError("INVALID_ARGUMENT", "between requires exactly one of ratio or middle=true")
        if m == "datum" and a.get("confirm_non_associative") is not True:
            raise CADOperationError("INVALID_ARGUMENT", "datum requires confirm_non_associative=true")
        handles = [a[k] for k in KINDS if k in a]
        if len(set(handles)) != len(handles):
            raise CADOperationError("INVALID_ARGUMENT", "Each reference role needs a distinct handle")

    def point(self, a):
        self.validate(a)
        m = a["mode"]
        container = self.obj(a["container_handle"], {"geoset"})
        refs = {key: self.ref(a[key], kinds) for key, kinds in KINDS.items() if key in a}
        if m == "between" and same_object(refs["first_point_handle"], refs["second_point_handle"]):
            raise CADOperationError("INVALID_ARGUMENT", "between needs two distinct points")
        if m == "datum":
            source = self.obj(a["source_handle"], {"point"})
            try:
                inside = same_object(source.Parent.Parent, container)
            except Exception as exc:
                raise CADOperationError("INVALID_ARGUMENT", f"Cannot verify datum source container: {exc}") from exc
            if not inside:
                raise CADOperationError("INVALID_ARGUMENT", "CAA requires the datum source to be in the target geoset")
        f = self.conn.get_active_part().HybridShapeFactory
        direction = None
        if "direction" in a:
            direction = f.AddNewDirectionByCoord(*unit_vector(a["direction"]))
        elif "direction_handle" in a:
            direction = f.AddNewDirection(refs["direction_handle"])
        ref_pt, reverse = refs.get("reference_point_handle"), bool(a.get("reverse", False))
        warnings = []
        if m == "coordinates":
            x, y, z = a["coordinates_mm"]
            obj = f.AddNewPointCoordWithReference(x, y, z, ref_pt) if ref_pt is not None else f.AddNewPointCoord(x, y, z)
            if "axis_system_handle" in a:
                self.state.mark_created(obj, "point")
                obj.RefAxisSystem = refs["axis_system_handle"]
        elif m in ON_CURVE_TYPES:
            crv = refs["curve_handle"]
            if m == "on_curve_distance":
                obj = (f.AddNewPointOnCurveWithReferenceFromDistance(crv, ref_pt, a["distance_mm"], reverse) if ref_pt is not None
                       else f.AddNewPointOnCurveFromDistance(crv, a["distance_mm"], reverse))
                if a.get("distance_type", "geodesic") == "euclidean":
                    self.state.mark_created(obj, "point")
                    obj.DistanceType = DISTANCE_TYPES["euclidean"]
            elif m == "on_curve_ratio":
                obj = (f.AddNewPointOnCurveWithReferenceFromPercent(crv, ref_pt, a["ratio"], reverse) if ref_pt is not None
                       else f.AddNewPointOnCurveFromPercent(crv, a["ratio"], reverse))
            else:
                obj = (f.AddNewPointOnCurveWithReferenceAlongDirection(crv, ref_pt, a["distance_mm"], reverse, direction) if ref_pt is not None
                       else f.AddNewPointOnCurveAlongDirection(crv, a["distance_mm"], reverse, direction))
        elif m == "on_plane":
            h, v = a["plane_coordinates_mm"]
            plane = refs["plane_handle"]
            obj = f.AddNewPointOnPlaneWithReference(plane, ref_pt, h, v) if ref_pt is not None else f.AddNewPointOnPlane(plane, h, v)
        elif m == "on_surface":
            surface = refs["surface_handle"]
            obj = (f.AddNewPointOnSurfaceWithReference(surface, ref_pt, direction, a["distance_mm"]) if ref_pt is not None
                   else f.AddNewPointOnSurface(surface, direction, a["distance_mm"]))
            if ref_pt is None:
                warnings.append("No reference point: CAA takes the middle point of the surface")
        elif m == "center":
            obj = f.AddNewPointCenter(refs["element_handle"])
        elif m == "tangent_on_curve":
            obj = f.AddNewPointTangent(refs["curve_handle"], direction)
            warnings.append("CAA: a tangent point feature can contain several points")
        elif m == "between":
            ratio = 0.5 if a.get("middle") else float(a["ratio"])
            # CAA conflict: Orientation=1 "measured from the second point", yet Ratio = d1/d2 from the
            # FIRST point. Pass the ratio unchanged (same as catia_reference_point) and report the
            # measured side in verify(); never assert either meaning as fact.
            obj = f.AddNewPointBetween(refs["first_point_handle"], refs["second_point_handle"], ratio, 1)
            warnings.append("Between ratio direction is unverified on live CATIA; check coordinates.ratio_measured_from")
            if "support_handle" in a:
                self.state.mark_created(obj, "point")
                obj.Support = refs["support_handle"]
        else:
            obj = f.AddNewPointDatum(refs["source_handle"])
            warnings.append("Datum is an explicit non-associative copy: it will not follow later source edits")
        result = self.engineering.finish(obj, "point", a, container)
        result["mode"], result["live_validated"] = m, False
        result["warnings"] += warnings
        result["definition"] = self.definition(obj, m, a)
        result["coordinates"] = self.verify(obj, m, a, refs, result["handle"])
        return result

    def definition(self, obj, m, a):
        """Native parameter readback; a mismatch is a failed postcondition."""
        def value(attr):
            return float(getattr(obj, attr).Value)
        data, expected = {}, {}
        try:
            if m == "coordinates":
                data = {"x_mm": value("X"), "y_mm": value("Y"), "z_mm": value("Z")}
                expected = dict(zip(("x_mm", "y_mm", "z_mm"), a["coordinates_mm"]))
            elif m in ON_CURVE_TYPES:
                data = {"on_curve_type": int(obj.OnCurveType), "orientation": int(obj.Orientation)}
                expected = {"on_curve_type": ON_CURVE_TYPES[m]}
                if m == "on_curve_ratio":
                    data["ratio"], expected["ratio"] = value("Ratio"), a["ratio"]
                else:
                    data["offset_mm"], expected["offset_mm"] = value("Offset"), a["distance_mm"]
                if m == "on_curve_distance":
                    data["distance_type"] = int(obj.DistanceType)
                    expected["distance_type"] = DISTANCE_TYPES[a.get("distance_type", "geodesic")]
            elif m == "on_plane":
                data = {"h_mm": value("XOffset"), "v_mm": value("YOffset")}
                expected = dict(zip(("h_mm", "v_mm"), a["plane_coordinates_mm"]))
            elif m == "on_surface":
                data["offset_mm"], expected["offset_mm"] = value("Offset"), a["distance_mm"]
            elif m == "between":
                data = {"native_ratio": value("Ratio"), "orientation": int(obj.Orientation),
                        "orientation_semantics": "unverified_on_live_catia"}
        except Exception as exc:
            return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
        wrong = {k: (data[k], v) for k, v in expected.items() if abs(data[k] - v) > 1e-6}  # numeric keys only
        if wrong:
            raise CADOperationError("POSTCONDITION_FAILED", f"Point created and left in the geoset, but definition readback differs: {wrong}")
        return {"status": "verified" if expected else "reported", "values": data}

    def measure(self, reference, getter="GetPoint", types=frozenset({11})):
        measurable = self.conn.active_document.GetWorkbench("SPAWorkbench").GetMeasurable(reference)
        geometry = int(measurable.GeometryName)
        if geometry not in types:
            raise CADOperationError("WRONG_GEOMETRY_TYPE", f"CatMeasurableName={geometry}")
        return read_array(getattr(measurable, getter), 3)

    def verify(self, obj, m, a, refs, handle):
        """Absolute Part coordinates via SPA Measurable (mm), plus checks where expectation is computable."""
        try:
            actual = self.measure(self.conn.get_active_part().CreateReferenceFromObject(obj))
        except Exception as exc:
            return {"status": "unverified", "unit": "mm", "reason": f"Measurable.GetPoint unavailable: {exc}"}
        report = {"status": "measured", "value": actual, "unit": "mm", "frame": "active Part"}
        expected, sides = None, None
        try:
            if m == "coordinates" and "reference_point_handle" not in a and "axis_system_handle" not in a:
                expected = a["coordinates_mm"]
            elif m == "between" and "support_handle" in a:
                report["check"] = "point is computed on the support; no straight-line expectation"
            elif m == "between":
                p1, p2 = self.measure(refs["first_point_handle"]), self.measure(refs["second_point_handle"])
                ratio = 0.5 if a.get("middle") else a["ratio"]
                from_first = [u + ratio * (v - u) for u, v in zip(p1, p2)]
                from_second = [v + ratio * (u - v) for u, v in zip(p1, p2)]
                sides = (("first_point", from_first), ("second_point", from_second))
            elif m == "center":
                expected = self.measure(refs["element_handle"], "GetCenter", frozenset({5, 9}))
        except Exception as exc:
            report["check"] = f"expected position unavailable: {exc}"
            sides = None
        if m == "between" and "support_handle" not in a and sides is not None:
            symmetric = _close(sides[0][1], sides[1][1])
            for side, candidate in sides:
                if _close(actual, candidate):
                    report.update(status="verified", expected=candidate, tolerance_mm=TOLERANCE_MM,
                                  ratio_measured_from="either (symmetric)" if symmetric else side)
                    if side == "second_point" and not symmetric:
                        report["warning"] = "CATIA measured the ratio from the SECOND point; use 1-ratio for the first"
                    return report
            raise CADOperationError("POSTCONDITION_FAILED", f"{handle} created, but measured {actual} matches neither "
                                    f"ratio side {sides[0][1]} / {sides[1][1]} mm")
        if expected is not None:
            if not _close(actual, expected):
                raise CADOperationError("POSTCONDITION_FAILED", f"{handle} created, but measured {actual} differs from expected {expected} mm")
            report.update(status="verified", expected=list(expected), tolerance_mm=TOLERANCE_MM)
        return report
