"""catia_point contract checks on mocks: CAA constructor names, argument order, rejection before mutation.

No Windows geometry is asserted here; live validation remains pending.
"""
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from catia_mcp.runtime import CADOperationError, SessionState
from catia_mcp.tools import points as points_module
from catia_mcp.tools.engineering import EngineeringTools
from catia_mcp.tools.points import MODES, PointTools


def length(value):
    return NS(Value=value)


def fixture(monkeypatch, measured=None, centers=None):
    point = NS(Name="Point.1", X=length(1), Y=length(2), Z=length(3), OnCurveType=0, Orientation=1,
               DistanceType=1, Offset=length(5), Ratio=length(0.25), XOffset=length(4), YOffset=length(6))
    factory = Mock()
    for name in [
            "AddNewPointCoord", "AddNewPointCoordWithReference", "AddNewPointOnCurveFromDistance",
            "AddNewPointOnCurveWithReferenceFromDistance", "AddNewPointOnCurveFromPercent",
            "AddNewPointOnCurveWithReferenceFromPercent", "AddNewPointOnCurveAlongDirection",
            "AddNewPointOnCurveWithReferenceAlongDirection", "AddNewPointOnPlane",
            "AddNewPointOnPlaneWithReference", "AddNewPointOnSurface", "AddNewPointOnSurfaceWithReference",
            "AddNewPointCenter", "AddNewPointTangent", "AddNewPointBetween", "AddNewPointDatum"]:
        getattr(factory, name).return_value = point
    factory.AddNewDirectionByCoord.return_value = "dir_vec"
    factory.AddNewDirection.return_value = "dir_ref"
    part = NS(HybridShapeFactory=factory, CreateReferenceFromObject=lambda x: x,
              UpdateObject=Mock(), Update=Mock(), IsUpToDate=lambda x: True)
    measured = measured or {}

    def measurable(reference):
        geometry = 9 if centers and id(reference) in centers else 11
        return NS(GeometryName=geometry, GetPoint=lambda: measured.get(id(reference)),
                  GetCenter=lambda: (centers or {}).get(id(reference)))
    workbench = NS(GetMeasurable=measurable)
    conn = NS(active_document=NS(Name="T.CATPart", GetWorkbench=lambda name: workbench),
              get_active_part=lambda: part)
    def read_array(method, count):
        values = method()
        if values is None:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", "no array on this host")
        return [float(v) for v in values]
    monkeypatch.setattr(points_module, "read_array", read_array)
    state = SessionState(conn)
    tool = PointTools(EngineeringTools(conn, state, NS(_active_sketch=None)))
    container = NS(Name="Geometrical Set.1", AppendHybridShape=Mock())

    def handle(kind, value=None):
        return state.register(value if value is not None else NS(Name=kind), kind), value
    geoset, _ = handle("geoset", container)
    return tool, factory, point, handle, geoset, container, measured


def objs(handle, kind, n=1):
    return [handle(kind, NS(Name=f"{kind}{i}")) for i in range(n)]


CASES = [
    ("coordinates", {}, "AddNewPointCoord", lambda r: (1, 2, 3)),
    ("coordinates", {"reference_point_handle": "point"}, "AddNewPointCoordWithReference", lambda r: (1, 2, 3, r["reference_point_handle"])),
    ("on_curve_distance", {}, "AddNewPointOnCurveFromDistance", lambda r: (r["curve_handle"], 5, False)),
    ("on_curve_distance", {"reference_point_handle": "point", "reverse": True}, "AddNewPointOnCurveWithReferenceFromDistance",
     lambda r: (r["curve_handle"], r["reference_point_handle"], 5, True)),
    ("on_curve_ratio", {}, "AddNewPointOnCurveFromPercent", lambda r: (r["curve_handle"], 0.25, False)),
    ("on_curve_ratio", {"reference_point_handle": "point"}, "AddNewPointOnCurveWithReferenceFromPercent",
     lambda r: (r["curve_handle"], r["reference_point_handle"], 0.25, False)),
    ("on_curve_direction", {"direction": [0, 0, 2]}, "AddNewPointOnCurveAlongDirection", lambda r: (r["curve_handle"], 5, False, "dir_vec")),
    ("on_curve_direction", {"direction_handle": "line", "reference_point_handle": "point"}, "AddNewPointOnCurveWithReferenceAlongDirection",
     lambda r: (r["curve_handle"], r["reference_point_handle"], 5, False, "dir_ref")),
    ("on_plane", {}, "AddNewPointOnPlane", lambda r: (r["plane_handle"], 4, 6)),
    ("on_plane", {"reference_point_handle": "point"}, "AddNewPointOnPlaneWithReference", lambda r: (r["plane_handle"], r["reference_point_handle"], 4, 6)),
    ("on_surface", {"direction": [1, 0, 0]}, "AddNewPointOnSurface", lambda r: (r["surface_handle"], "dir_vec", 5)),
    ("on_surface", {"direction": [1, 0, 0], "reference_point_handle": "point"}, "AddNewPointOnSurfaceWithReference",
     lambda r: (r["surface_handle"], r["reference_point_handle"], "dir_vec", 5)),
    ("center", {}, "AddNewPointCenter", lambda r: (r["element_handle"],)),
    ("tangent_on_curve", {"direction_handle": "plane"}, "AddNewPointTangent", lambda r: (r["curve_handle"], "dir_ref")),
    ("between", {"middle": True}, "AddNewPointBetween", lambda r: (r["first_point_handle"], r["second_point_handle"], 0.5, 1)),
    ("between", {"ratio": 0.25}, "AddNewPointBetween", lambda r: (r["first_point_handle"], r["second_point_handle"], 0.25, 1)),
]
REQUIRED = {"coordinates_mm": [1, 2, 3], "distance_mm": 5, "ratio": 0.25, "plane_coordinates_mm": [4, 6]}
HANDLE_KINDS = {"curve_handle": "curve", "plane_handle": "plane", "surface_handle": "surface",
                "element_handle": "curve", "first_point_handle": "point", "second_point_handle": "point"}


@pytest.mark.parametrize("mode,extra,method,expected", CASES)
def test_constructor_and_argument_order(monkeypatch, mode, extra, method, expected):
    tool, factory, point, handle, geoset, container, _ = fixture(monkeypatch)
    args, refs = {"mode": mode, "container_handle": geoset, "name": "P"}, {}
    for key in MODES[mode]:
        if key in HANDLE_KINDS:
            args[key], refs[key] = handle(HANDLE_KINDS[key], NS(Name=key))
        else:
            args[key] = REQUIRED[key]
    for key, value in extra.items():
        if key.endswith("_handle"):
            args[key], refs[key] = handle(value, NS(Name=key))
        else:
            args[key] = value
    if mode == "on_curve_ratio":
        point.OnCurveType, point.Ratio = 2, length(0.25)
    if mode == "on_curve_direction":
        point.OnCurveType = 1
    result = tool.execute("catia_point", args)
    calls = [c for c in factory.mock_calls if c[0].startswith("AddNewPoint")]
    assert [c[0] for c in calls] == [method]
    assert calls[0].args == expected(refs)
    container.AppendHybridShape.assert_called_once_with(point)
    assert result["ok"] and result["live_validated"] is False and point.Name == "P"
    if "direction" in extra:
        factory.AddNewDirectionByCoord.assert_called_once()
        norm = sum(v * v for v in extra["direction"]) ** 0.5
        assert factory.AddNewDirectionByCoord.call_args.args == tuple(v / norm for v in extra["direction"])


def test_euclidean_axis_system_and_support_are_set(monkeypatch):
    tool, factory, point, handle, geoset, *_ = fixture(monkeypatch)
    curve, _ = handle("curve")
    assert point.DistanceType == 1  # geodesic default is untouched
    tool.execute("catia_point", {"mode": "on_curve_distance", "container_handle": geoset, "curve_handle": curve,
                                 "distance_mm": 5})
    assert point.DistanceType == 1
    tool.execute("catia_point", {"mode": "on_curve_distance", "container_handle": geoset, "curve_handle": curve,
                                 "distance_mm": 5, "distance_type": "euclidean"})
    assert point.DistanceType == -1  # written by the tool
    axis, axis_obj = handle("axis_system", NS(Name="Axis"))
    tool.execute("catia_point", {"mode": "coordinates", "container_handle": geoset,
                                 "coordinates_mm": [1, 2, 3], "axis_system_handle": axis})
    assert point.RefAxisSystem is axis_obj
    p1, _ = handle("point", NS(Name="A"))
    p2, _ = handle("point", NS(Name="B"))
    support, support_obj = handle("surface", NS(Name="S"))
    tool.execute("catia_point", {"mode": "between", "container_handle": geoset, "first_point_handle": p1,
                                 "second_point_handle": p2, "middle": True, "support_handle": support})
    assert point.Support is support_obj


def test_datum_requires_source_in_target_geoset(monkeypatch):
    tool, factory, point, handle, geoset, container, _ = fixture(monkeypatch)
    inside, _ = handle("point", NS(Name="In", Parent=NS(Parent=container)))
    result = tool.execute("catia_point", {"mode": "datum", "container_handle": geoset,
                                          "source_handle": inside, "confirm_non_associative": True})
    assert factory.AddNewPointDatum.call_count == 1 and any("non-associative" in w for w in result["warnings"])
    outside, _ = handle("point", NS(Name="Out", Parent=NS(Parent=NS(Name="Other"))))
    with pytest.raises(CADOperationError, match="target geoset"):
        tool.execute("catia_point", {"mode": "datum", "container_handle": geoset,
                                     "source_handle": outside, "confirm_non_associative": True})
    assert factory.AddNewPointDatum.call_count == 1


@pytest.mark.parametrize("mode,extra", [
    ("on_curve_direction", {}),                                         # no direction
    ("on_curve_direction", {"direction": [0, 0, 1], "direction_handle": "line"}),  # both
    ("on_surface", {"direction": [0, 0, 0]}),                           # zero vector
    ("between", {}),                                                    # neither ratio nor middle
    ("between", {"ratio": 0.3, "middle": True}),                        # both
    ("on_curve_distance", {"distance_type": "euclidean", "distance_mm": -1}),
    ("coordinates", {"distance_mm": 3}),                                # irrelevant field
    ("center", {"reference_point_handle": "point"}),                    # option not offered by mode
    ("datum", {"confirm_non_associative": False}),
])
def test_invalid_combinations_rejected_before_constructor(monkeypatch, mode, extra):
    tool, factory, point, handle, geoset, container, _ = fixture(monkeypatch)
    args = {"mode": mode, "container_handle": geoset}
    for key in MODES[mode]:
        if key in HANDLE_KINDS:
            args[key], _ = handle(HANDLE_KINDS[key], NS(Name=key))
        elif key == "source_handle":
            args[key], _ = handle("point", NS(Name="S", Parent=NS(Parent=container)))
        elif key == "confirm_non_associative":
            args[key] = True
        else:
            args[key] = REQUIRED[key]
    for key, value in extra.items():
        args[key] = handle(value, NS(Name=key))[0] if key.endswith("_handle") else value
    with pytest.raises(CADOperationError):
        tool.execute("catia_point", args)
    assert not factory.mock_calls and not container.AppendHybridShape.called


def test_same_point_twice_and_wrong_kind_rejected(monkeypatch):
    tool, factory, point, handle, geoset, *_ = fixture(monkeypatch)
    p, _ = handle("point")
    with pytest.raises(CADOperationError, match="distinct"):
        tool.execute("catia_point", {"mode": "between", "container_handle": geoset,
                                     "first_point_handle": p, "second_point_handle": p, "middle": True})
    surface, _ = handle("surface")
    with pytest.raises(CADOperationError) as error:
        tool.execute("catia_point", {"mode": "on_curve_ratio", "container_handle": geoset,
                                     "curve_handle": surface, "ratio": 0.5})
    assert error.value.code == "WRONG_GEOMETRY_TYPE" and not factory.mock_calls


def test_measured_coordinates_verify_and_fail(monkeypatch):
    tool, factory, point, handle, geoset, container, measured = fixture(monkeypatch)
    measured[id(point)] = (1.0, 2.0, 3.0)
    result = tool.execute("catia_point", {"mode": "coordinates", "container_handle": geoset, "coordinates_mm": [1, 2, 3]})
    assert result["coordinates"]["status"] == "verified" and result["definition"]["status"] == "verified"
    measured[id(point)] = (1.0, 2.0, 9.0)
    with pytest.raises(CADOperationError, match="differs"):
        tool.execute("catia_point", {"mode": "coordinates", "container_handle": geoset, "coordinates_mm": [1, 2, 3]})


def test_between_reports_measured_ratio_side_without_assuming_it(monkeypatch):
    tool, factory, point, handle, geoset, container, measured = fixture(monkeypatch)
    a, a_obj = handle("point", NS(Name="A"))
    b, b_obj = handle("point", NS(Name="B"))
    args = {"mode": "between", "container_handle": geoset, "first_point_handle": a, "second_point_handle": b, "ratio": 0.25}
    measured.update({id(a_obj): (0, 0, 0), id(b_obj): (100, 0, 0), id(point): (25.0, 0, 0)})
    result = tool.execute("catia_point", args)
    assert result["coordinates"]["ratio_measured_from"] == "first_point"
    assert result["definition"]["values"]["orientation_semantics"] == "unverified_on_live_catia"
    measured[id(point)] = (75.0, 0, 0)  # the documented "from the second point" reading
    result = tool.execute("catia_point", args)
    assert result["coordinates"]["ratio_measured_from"] == "second_point" and "SECOND" in result["coordinates"]["warning"]
    measured[id(point)] = (40.0, 0, 0)
    with pytest.raises(CADOperationError, match="matches neither"):
        tool.execute("catia_point", args)


def test_between_on_curved_support_skips_straight_line_check(monkeypatch):
    tool, factory, point, handle, geoset, container, measured = fixture(monkeypatch)
    a, a_obj = handle("point", NS(Name="A"))
    b, b_obj = handle("point", NS(Name="B"))
    support, _ = handle("curve", NS(Name="Arc"))
    measured.update({id(a_obj): (0, 0, 0), id(b_obj): (10, 0, 0), id(point): (5.0, 3.0, 0)})
    result = tool.execute("catia_point", {"mode": "between", "container_handle": geoset, "first_point_handle": a,
                                          "second_point_handle": b, "middle": True, "support_handle": support})
    assert result["coordinates"]["status"] == "measured" and "support" in result["coordinates"]["check"]


def test_center_rejects_straight_lines_before_constructor(monkeypatch):
    tool, factory, point, handle, geoset, *_ = fixture(monkeypatch)
    for kind in ("line", "line2d"):
        h, _ = handle(kind)
        with pytest.raises(CADOperationError):
            tool.execute("catia_point", {"mode": "center", "container_handle": geoset, "element_handle": h})
    factory.AddNewPointCenter.assert_not_called()


def test_center_checked_against_circle_center_and_unverified_without_array(monkeypatch):
    circle = NS(Name="Circle")
    tool, factory, point, handle, geoset, container, measured = fixture(monkeypatch, centers={id(circle): (5, 5, 0)})
    h, _ = handle("curve", circle)
    measured[id(point)] = (5, 5, 0)
    result = tool.execute("catia_point", {"mode": "center", "container_handle": geoset, "element_handle": h})
    assert result["coordinates"]["status"] == "verified"
    curve, _ = handle("curve")
    result = tool.execute("catia_point", {"mode": "tangent_on_curve", "container_handle": geoset,
                                          "curve_handle": curve, "direction": [1, 0, 0]})
    assert result["coordinates"]["status"] in {"measured", "unverified"}


def test_definition_readback_mismatch_is_failure(monkeypatch):
    tool, factory, point, handle, geoset, *_ = fixture(monkeypatch)
    curve, _ = handle("curve")
    point.Offset = length(7)
    with pytest.raises(CADOperationError, match="definition readback differs"):
        tool.execute("catia_point", {"mode": "on_curve_distance", "container_handle": geoset,
                                     "curve_handle": curve, "distance_mm": 5})


def test_schema_offers_optional_fields_per_mode_only():
    definition = PointTools(NS(conn=None)).get_tool_definitions()[0]
    variants = {v["properties"]["mode"]["const"]: set(v["propertyNames"]["enum"]) for v in definition["inputSchema"]["oneOf"]}
    assert set(variants) == set(MODES)
    assert "reference_point_handle" in variants["on_curve_distance"] and "reference_point_handle" not in variants["center"]
    assert {"direction", "direction_handle"} <= variants["tangent_on_curve"]
    assert "name" in variants["datum"] and definition["readOnlyHint"] is False
