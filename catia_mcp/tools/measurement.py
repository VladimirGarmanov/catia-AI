"""Measurement and analysis tools for CATIA V5.

Distance, angle, inertia, bounding box, and part property queries.
"""

from __future__ import annotations

import json
import math
from typing import Any

from catia_mcp.connection import CATIAConnection


class MeasurementTools:
    """Tools for measurement and analysis in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_measure_distance",
                "description": (
                    "Measure minimum distance between two uniquely named geometry elements "
                    "in the active CATPart. CATIA's raw length unit needs Windows calibration; "
                    "the result is not labelled mm until then. Search clears the current selection."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "element1": {
                            "type": "string",
                            "description": "Name of first element (feature, face, edge, point)",
                        },
                        "element2": {
                            "type": "string",
                            "description": "Name of second element",
                        },
                    },
                    "required": ["element1", "element2"],
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
                    },
                    "required": ["name", "value"],
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
                return self._measure_distance(arguments["element1"], arguments["element2"])
            case "catia_get_inertia":
                return self._get_inertia(arguments.get("density"))
            case "catia_get_bounding_box":
                return self._get_bounding_box()
            case "catia_get_parameters":
                return self._get_parameters(arguments.get("filter"))
            case "catia_set_parameter":
                return self._set_parameter(arguments["name"], arguments["value"])
            case "catia_update_part":
                return self._update_part()
            case _:
                raise ValueError(f"Unknown measurement tool: {tool_name}")

    def _measure_distance(self, elem1_name: str, elem2_name: str) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        doc = self.conn.active_document
        spa = doc.GetWorkbench("SPAWorkbench")

        sel = doc.Selection
        references = []
        for name in (elem1_name, elem2_name):
            if not name or any(char in name for char in ",*=\r\n"):
                raise ValueError("Element names must be nonempty literal names without search syntax")
            try:
                sel.Clear()
                sel.Search(f"Name={name},all")
                count = sel.Count2
                selected = sel.Item2(1) if count == 1 else None
                if count != 1:
                    raise RuntimeError(
                        f"Element {name!r} matched {count} objects; exact target is ambiguous"
                    )
                references.append(part.CreateReferenceFromObject(selected.Value))
            finally:
                sel.Clear()

        # Measure
        measurable = spa.GetMeasurable(references[0])
        distance = measurable.GetMinimumDistance(references[1])

        return json.dumps({
            "minimum_distance_raw": distance,
            "unit": "CATIA_SPA_length_unverified",
            "target_names": [elem1_name, elem2_name],
            "document": doc.Name,
            "selection_cleared": True,
            "note": "Calibrate against known geometry on this CATIA installation before treating the raw value as mm.",
        })

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
        self.conn.ensure_connected()
        self.conn.get_active_part()
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

    def _set_parameter(self, name: str, value: float) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        params = part.Parameters

        param = params.Item(name)
        old_value = param.Value
        param.Value = value
        part.Update()

        self.conn.refresh_display()
        return f"Parameter '{name}' changed: {old_value} -> {value}"

    def _update_part(self) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        part.Update()
        if not part.IsUpToDate(part.MainBody):
            raise RuntimeError("CATIA reports the main body is not up to date after Part.Update")
        self.conn.refresh_display()
        return "Part updated; CATIA reports the main body is up to date"
