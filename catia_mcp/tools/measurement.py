"""Measurement and analysis tools for CATIA V5.

Distance, angle, inertia, bounding box, and part property queries.
"""

from __future__ import annotations

import json
import math
from typing import Any

from catia_mcp.connection import CATIAConnection
from catia_mcp.runtime import CADOperationError


class MeasurementTools:
    """Tools for measurement and analysis in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_measure_distance",
                "description": (
                    "Measure the minimum distance in mm between two geometries of the active CATPart. "
                    "Prefer first_handle/second_handle from catia_list_objects or a fresh selection "
                    "(faces/edges included); element1/element2 accept unique whole-feature names only. "
                    "CATIA SPA returns the distance in the model length unit (mm); bodies cannot be "
                    "measured between. Same contract as catia_measure_exact mode=distance."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "first_handle": {"type": "string", "minLength": 1},
                        "second_handle": {"type": "string", "minLength": 1},
                        "element1": {"type": "string", "description": "Unique whole-feature/sketch/GSD name"},
                        "element2": {"type": "string", "description": "Unique whole-feature/sketch/GSD name"},
                    },
                },
            },
            {
                "name": "catia_get_inertia",
                "description": (
                    "Read MainBody volume and area in SI units; optional mass uses a supplied "
                    "uniform density. An inertia tensor is reported only when available and "
                    "scope-compatible."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "density": {
                            "type": "number",
                            "description": "Material density in kg/m3 (optional, for mass calculation)",
                        },
                    },
                },
            },
            {
                "name": "catia_get_bounding_box",
                "description": (
                    "Report that exact active-part AABB measurement is not yet supported. "
                    "No fake min/max coordinates are returned."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_get_parameters",
                "description": (
                    "List all user-defined and computed parameters of the active part. "
                    "Includes dimensions, formulas, and design tables."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Optional name filter (partial match)",
                        },
                    },
                },
            },
            {
                "name": "catia_set_parameter",
                "description": (
                    "Set the value of a named parameter in the active part. "
                    "Useful for parametric design modifications."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Full parameter name (e.g., 'Part1\\\\Pad.1\\\\FirstLimit\\\\Length')",
                        },
                        "value": {
                            "type": "number",
                            "description": "New value for the parameter",
                        },
                        "parameter_handle": {"type": "string"},
                        "unit": {"enum": ["mm", "deg", "native"], "default": "native",
                                 "description": "Prefer explicit mm/deg for dimensions; native retains legacy raw Value semantics"},
                    },
                    "required": ["value"],
                },
            },
            {
                "name": "catia_update_part",
                "description": "Force update/rebuild of the active part. Recalculates all features.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str | dict[str, Any]:
        match tool_name:
            case "catia_measure_distance":
                return self._measure_distance(arguments)
            case "catia_get_inertia":
                return self._get_inertia(arguments.get("density"))
            case "catia_get_bounding_box":
                return self._get_bounding_box()
            case "catia_get_parameters":
                return self._get_parameters(arguments.get("filter"))
            case "catia_set_parameter":
                return self._set_parameter(arguments.get("name"), arguments["value"], arguments.get("unit", "native"), arguments.get("parameter_handle"))
            case "catia_update_part":
                return self._update_part()
            case _:
                raise ValueError(f"Unknown measurement tool: {tool_name}")

    def _measure_distance(self, args: dict[str, Any]) -> dict[str, Any]:
        by_handle = "first_handle" in args or "second_handle" in args
        by_name = "element1" in args or "element2" in args
        if by_handle == by_name or (by_handle and not {"first_handle", "second_handle"} <= args.keys()) \
                or (by_name and not {"element1", "element2"} <= args.keys()):
            raise CADOperationError("INVALID_ARGUMENT", "Pass both first_handle/second_handle OR both element1/element2")
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        doc = self.conn.active_document
        if by_handle:
            kinds = {"point", "vertex", "line", "curve", "edge", "face", "surface", "plane", "feature",
                     "sketch", "geometry", "point2d", "line2d", "circle2d", "ellipse2d"}
            references = [self.conn.session.reference(args[key], kinds) for key in ("first_handle", "second_handle")]
            targets = [args["first_handle"], args["second_handle"]]
        else:
            targets = [args["element1"], args["element2"]]
            references = [part.CreateReferenceFromObject(self._unique_geometry(part, name)) for name in targets]
        distance = float(doc.GetWorkbench("SPAWorkbench").GetMeasurable(references[0]).GetMinimumDistance(references[1]))
        if not math.isfinite(distance) or distance < 0:
            raise CADOperationError("POSTCONDITION_FAILED", f"CATIA returned an invalid distance: {distance}")
        return {"ok": True, "value": distance, "unit": "mm", "api_value": distance, "api_unit": "mm",
                "targets": targets, "document": str(doc.Name), "frame": "active Part",
                "unit_basis": "CATIA SPA model length unit (mm); not rescaled", "live_validated": False}

    @staticmethod
    def _unique_geometry(part, name):
        candidates = []

        def collect(collection):
            candidates.extend(collection.Item(index) for index in range(1, collection.Count + 1))

        def geosets(collection):
            for index in range(1, collection.Count + 1):
                container = collection.Item(index)
                collect(container.HybridShapes)
                collect(container.HybridSketches)
                geosets(container.HybridBodies)

        for index in range(1, part.Bodies.Count + 1):
            body = part.Bodies.Item(index)
            collect(body.Shapes)
            collect(body.Sketches)
        geosets(part.HybridBodies)
        matches = [obj for obj in candidates if str(obj.Name) == name]
        if len(matches) != 1:
            raise CADOperationError("AMBIGUOUS_REFERENCE", f"Name {name!r} matched {len(matches)} whole geometries; "
                                    "faces/edges need handles from catia_list_objects or a fresh selection")
        return matches[0]

    def _get_inertia(self, density: float | None = None) -> dict[str, Any]:
        self.conn.ensure_connected()
        if density is not None and (
            isinstance(density, bool) or not isinstance(density, (int, float))
            or not math.isfinite(density) or density <= 0
        ):
            raise ValueError("density must be finite and positive in kg/m^3")
        doc = self.conn.active_document
        spa = doc.GetWorkbench("SPAWorkbench")
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        ref = part.CreateReferenceFromObject(body)
        measurable = spa.GetMeasurable(ref)
        result: dict[str, Any] = {"scope": "MainBody", "document": doc.Name,
                                  "unavailable_fields": {}}
        try:
            volume_m3 = float(measurable.Volume)
            if not math.isfinite(volume_m3) or volume_m3 < 0:
                raise ValueError(f"Invalid CATIA volume: {volume_m3}")
            result.update(volume_m3=volume_m3, volume_mm3=volume_m3 * 1e9)
            if density is not None:
                result.update(mass_kg=density * volume_m3, density_kg_m3=density,
                              density_source="explicit uniform user input")
        except Exception as exc:
            result["unavailable_fields"]["volume"] = str(exc)
        try:
            area_m2 = float(measurable.Area)
            if not math.isfinite(area_m2) or area_m2 < 0:
                raise ValueError(f"Invalid CATIA area: {area_m2}")
            result.update(area_m2=area_m2, area_mm2=area_m2 * 1e6)
        except Exception as exc:
            result["unavailable_fields"]["area"] = str(exc)
        result["unavailable_fields"]["inertia_matrix"] = (
            "MainBody tensor and its reference point are not available from Measurable; "
            "Product.GetTechnologicalObject('Inertia') has a different scope."
        )
        result["unavailable_fields"]["center_of_gravity"] = (
            "Coordinate units and COM output marshalling require Windows validation."
        )
        if "volume_m3" not in result and "area_m2" not in result:
            return {"ok": False, "code": "MEASUREMENT_UNAVAILABLE", "data": result,
                    "message": "CATIA provided neither volume nor area for MainBody"}
        return {"ok": True, "code": "PARTIAL_MEASUREMENT", "data": result}

    def _get_bounding_box(self) -> dict[str, Any]:
        return {
            "ok": False, "code": "UNSUPPORTED_EXACT_BOUNDING_BOX",
            "message": "Measurable.GetBoundingBox is not a documented CATIA V5 method. "
                       "Exact AABB requires a validated geometry-extremum implementation; "
                       "no dimensions were measured or inferred.",
        }

    def _get_parameters(self, name_filter: str | None = None) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        params = part.Parameters

        result = []
        for i in range(1, params.Count + 1):
            param = params.Item(i)
            name = param.Name

            if name_filter and name_filter.lower() not in name.lower():
                continue

            info: dict[str, Any] = {"name": name}
            try:
                info["value"] = param.Value
            except Exception:
                info["value"] = "N/A"
            try:
                info["comment"] = param.Comment
            except Exception:
                pass

            result.append(info)

        if not result:
            return "No parameters found" + (f" matching '{name_filter}'" if name_filter else "")
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _set_parameter(self, name: str | None, value: float, unit="native", handle=None) -> dict:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        params = part.Parameters

        if bool(name) == bool(handle):
            raise ValueError("Specify exactly one of name or parameter_handle")
        if not math.isfinite(value):
            raise ValueError("Parameter value must be finite")
        if handle:
            param = self.conn.session.resolve(handle, {"parameter"}).value
        else:
            matches = [params.Item(i) for i in range(1, params.Count + 1) if str(params.Item(i).Name) == name]
            if len(matches) != 1:
                raise ValueError(f"Parameter name matched {len(matches)} objects; use an exact handle")
            param = matches[0]
        old_value = param.Value
        state = getattr(self.conn, "session", None)
        if state is not None:
            handle = handle or state.register(param, "parameter")
            state.modified.append(handle)
        if unit == "native":
            param.Value = value
        else:
            param.ValuateFromString(f"{value}{unit}")
        part.Update()
        readback = str(param.ValueAsString())
        if unit == "native" and not math.isclose(float(param.Value), value, rel_tol=1e-9, abs_tol=1e-9):
            raise RuntimeError("Parameter readback differs from requested native value")
        if state is not None:
            state.updated = True

        self.conn.refresh_display()
        return {"ok": True, "handle": handle, "name": str(param.Name), "old_native_value": old_value,
                "requested_value": value, "requested_unit": unit, "readback": readback,
                "warnings": ["Dependent geometric effect not measured; native unit is parameter-specific"]}

    def _update_part(self) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        part.Update()
        if not part.IsUpToDate(part.MainBody):
            raise RuntimeError("CATIA reports the main body is not up to date after Part.Update")
        if getattr(self.conn, "session", None) is not None:
            self.conn.session.updated = True
        self.conn.refresh_display()
        return "Part updated; CATIA reports the main body is up to date"
