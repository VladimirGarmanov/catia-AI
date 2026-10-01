"""Sketcher tools for CATIA V5.

2D sketch creation and editing: lines, circles, rectangles, arcs, splines, constraints.
All dimensions are in millimeters. CATIA COM API uses millimeters natively.
"""

from __future__ import annotations

import json
import math
from typing import Any

from catia_mcp.connection import CATIAConnection

# Plane name mapping
PLANE_MAP = {
    "xy": "PlaneXY",
    "yz": "PlaneYZ",
    "zx": "PlaneZX",
    "xz": "PlaneZX",  # alias
}

# CATIA V5 Automation CatConstraintType: (enum value, number of elements).
# Keep these explicit: pywin32 constants are not available in offline tests.
# Source: CAA V5 MecModInterfaces / enum_CatConstraintType_27587.htm.
CONSTRAINT_SPECS = {
    "distance": (1, 2),       # catCstTypeDistance; one-line length uses 5 below
    "radius": (14, 1),        # catCstTypeRadius
    "angle": (6, 2),          # catCstTypeAngle
    "coincidence": (2, 2),    # catCstTypeOn
    "tangent": (4, 2),        # catCstTypeTangency
    "perpendicular": (11, 2), # catCstTypePerpendicularity
    "parallel": (8, 2),       # catCstTypeParallelism
    "horizontal": (10, 1),    # catCstTypeHorizontality
    "vertical": (13, 1),      # catCstTypeVerticality
    "fix": (0, 1),            # catCstTypeReference
}


class SketcherTools:
    """Tools for 2D sketch operations in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection
        self._active_sketch: Any | None = None
        self._active_factory: Any | None = None
        self._active_document_identity: tuple[str, str] | None = None

    @staticmethod
    def _document_identity(document: Any) -> tuple[str, str]:
        return (str(document.Name), str(getattr(document, "FullName", "")))

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_create_sketch",
                "description": (
                    "Create a new 2D sketch on a reference plane (xy, yz, or zx). "
                    "The sketch is opened for editing. You must close it with catia_close_sketch "
                    "before creating 3D features."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "plane": {
                            "type": "string",
                            "description": "Reference plane: 'xy' (front), 'yz' (right), 'zx' (top)",
                            "enum": ["xy", "yz", "zx"],
                            "default": "xy",
                        },
                    },
                },
            },
            {
                "name": "catia_close_sketch",
                "description": (
                    "Close the active sketch and return to Part Design. "
                    "Must be called after finishing sketch geometry before applying 3D features."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_sketch_line",
                "description": (
                    "Draw a line in the active sketch from (x1, y1) to (x2, y2). "
                    "Coordinates in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x1": {"type": "number", "description": "Start X coordinate (mm)"},
                        "y1": {"type": "number", "description": "Start Y coordinate (mm)"},
                        "x2": {"type": "number", "description": "End X coordinate (mm)"},
                        "y2": {"type": "number", "description": "End Y coordinate (mm)"},
                    },
                    "required": ["x1", "y1", "x2", "y2"],
                },
            },
            {
                "name": "catia_sketch_rectangle",
                "description": (
                    "Draw a rectangle in the active sketch defined by two opposite corners. "
                    "Creates 4 lines forming a closed profile. Coordinates in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x1": {"type": "number", "description": "First corner X (mm)"},
                        "y1": {"type": "number", "description": "First corner Y (mm)"},
                        "x2": {"type": "number", "description": "Opposite corner X (mm)"},
                        "y2": {"type": "number", "description": "Opposite corner Y (mm)"},
                    },
                    "required": ["x1", "y1", "x2", "y2"],
                },
            },
            {
                "name": "catia_sketch_centered_rectangle",
                "description": (
                    "Draw a rectangle centered at (cx, cy) with given width and height. "
                    "Coordinates and dimensions in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cx": {"type": "number", "description": "Center X (mm)", "default": 0},
                        "cy": {"type": "number", "description": "Center Y (mm)", "default": 0},
                        "width": {"type": "number", "description": "Width in mm"},
                        "height": {"type": "number", "description": "Height in mm"},
                    },
                    "required": ["width", "height"],
                },
            },
            {
                "name": "catia_sketch_circle",
                "description": "Draw a circle in the active sketch. Coordinates and radius in mm.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cx": {"type": "number", "description": "Center X (mm)", "default": 0},
                        "cy": {"type": "number", "description": "Center Y (mm)", "default": 0},
                        "radius": {"type": "number", "description": "Radius in mm"},
                    },
                    "required": ["radius"],
                },
            },
            {
                "name": "catia_sketch_arc",
                "description": (
                    "Draw a circular arc defined by center, radius, and start/end angles (degrees). "
                    "Angles are measured counter-clockwise from the positive X axis."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cx": {"type": "number", "description": "Center X (mm)"},
                        "cy": {"type": "number", "description": "Center Y (mm)"},
                        "radius": {"type": "number", "description": "Radius (mm)"},
                        "start_angle": {"type": "number", "description": "Start angle (degrees)"},
                        "end_angle": {"type": "number", "description": "End angle (degrees)"},
                    },
                    "required": ["cx", "cy", "radius", "start_angle", "end_angle"],
                },
            },
            {
                "name": "catia_sketch_spline",
                "description": (
                    "Draw a spline through a list of control points. "
                    "Each point is [x, y] in mm."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "points": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 2,
                                "maxItems": 2,
                            },
                            "description": "List of [x, y] control points in mm",
                            "minItems": 2,
                        },
                        "closed": {
                            "type": "boolean",
                            "description": "Whether to close the spline (default: false)",
                            "default": False,
                        },
                    },
                    "required": ["points"],
                },
            },
            {
                "name": "catia_sketch_point",
                "description": "Create a point in the active sketch. Coordinates in mm.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate (mm)"},
                        "y": {"type": "number", "description": "Y coordinate (mm)"},
                    },
                    "required": ["x", "y"],
                },
            },
            {
                "name": "catia_sketch_constraint",
                "description": (
                    "Add a dimensional or geometric constraint to the active sketch. "
                    "Supported types: distance, radius, angle, coincidence, tangent, "
                    "perpendicular, parallel, horizontal, vertical, fix. "
                    "Refresh catia_sketch_get_geometry immediately before using indices; "
                    "they are transient positions, not stable IDs. Radius needs a circle/arc. "
                    "Distance with one element sets a line's length; with two it sets their "
                    "separation. Angle needs two lines. Close the sketch and update the part "
                    "after editing to check the solve."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Constraint type",
                            "enum": [
                                "distance", "radius", "angle",
                                "coincidence", "tangent", "perpendicular",
                                "parallel", "horizontal", "vertical", "fix",
                            ],
                        },
                        "value": {
                            "type": "number",
                            "description": "Constraint value (mm or degrees). Required for distance, radius, angle.",
                        },
                        "geometry_index_1": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Index of first geometry element (1-based, from sketch geometry list)",
                        },
                        "geometry_index_2": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Index of second geometry element (for relational constraints)",
                        },
                    },
                    "required": ["type", "geometry_index_1"],
                },
            },
            {
                "name": "catia_sketch_get_geometry",
                "description": "List all geometry elements in the active sketch with their indices and types.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_create_sketch":
                return self._create_sketch(arguments.get("plane", "xy"))
            case "catia_close_sketch":
                return self._close_sketch()
            case "catia_sketch_line":
                return self._draw_line(
                    arguments["x1"], arguments["y1"],
                    arguments["x2"], arguments["y2"],
                )
            case "catia_sketch_rectangle":
                return self._draw_rectangle(
                    arguments["x1"], arguments["y1"],
                    arguments["x2"], arguments["y2"],
                )
            case "catia_sketch_centered_rectangle":
                return self._draw_centered_rectangle(
                    arguments.get("cx", 0), arguments.get("cy", 0),
                    arguments["width"], arguments["height"],
                )
            case "catia_sketch_circle":
                return self._draw_circle(
                    arguments.get("cx", 0), arguments.get("cy", 0),
                    arguments["radius"],
                )
            case "catia_sketch_arc":
                return self._draw_arc(
                    arguments["cx"], arguments["cy"], arguments["radius"],
                    arguments["start_angle"], arguments["end_angle"],
                )
            case "catia_sketch_spline":
                return self._draw_spline(
                    arguments["points"], arguments.get("closed", False),
                )
            case "catia_sketch_point":
                return self._draw_point(arguments["x"], arguments["y"])
            case "catia_sketch_constraint":
                return self._add_constraint(arguments)
            case "catia_sketch_get_geometry":
                return self._get_geometry()
            case _:
                raise ValueError(f"Unknown sketcher tool: {tool_name}")

    def _ensure_sketch_open(self) -> None:
        if self._active_sketch is None:
            raise RuntimeError(
                "No active sketch. Use catia_create_sketch first to open a sketch."
            )
        if self._active_document_identity != self._document_identity(self.conn.active_document):
            raise RuntimeError(
                "Active CATIA document changed while a sketch was open. "
                "Return to the original document before editing or closing that sketch."
            )

    def _create_sketch(self, plane: str = "xy") -> str:
        if self._active_sketch is not None:
            raise RuntimeError("SKETCH_ALREADY_OPEN: close the current sketch before creating another")
        self.conn.ensure_connected()
        document = self.conn.active_document
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()

        # Get the reference plane
        origin = part.OriginElements
        plane_key = plane.lower()
        if plane_key not in PLANE_MAP:
            raise ValueError(f"Unknown plane '{plane}'. Use 'xy', 'yz', or 'zx'.")

        plane_attr = PLANE_MAP[plane_key]
        ref_plane = getattr(origin, plane_attr)
        ref = part.CreateReferenceFromObject(ref_plane)

        # Create the sketch on the plane
        sketches = body.Sketches
        previous_count = sketches.Count
        sketch = sketches.Add(ref)
        if sketches.Count != previous_count + 1:
            raise RuntimeError(
                "CATIA returned a new sketch but the target body sketch count did not increase "
                "by one. Inspect the model tree before retrying."
            )

        # Open the sketch for editing
        self._active_sketch = sketch
        self._active_document_identity = self._document_identity(document)
        self._active_factory = sketch.OpenEdition()

        plane_names = {"xy": "XY (front)", "yz": "YZ (right)", "zx": "ZX (top)"}
        return (
            f"Sketch {sketch.Name!r} created in {document.Name!r}/{body.Name!r} "
            f"on {plane_names.get(plane_key, plane)} plane; editing=true. "
            "Use fresh catia_sketch_get_geometry indices for constraints."
        )

    def _close_sketch(self) -> str:
        self._ensure_sketch_open()
        sketch = self._active_sketch
        sketch.CloseEdition()
        self._active_sketch = None
        self._active_factory = None
        self._active_document_identity = None
        self.conn.get_active_part().UpdateObject(sketch)
        self.conn.refresh_display()
        return "Sketch closed. You can now apply Part Design features (pad, pocket, etc.)."

    def _draw_line(self, x1: float, y1: float, x2: float, y2: float) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory
        line = factory.CreateLine(x1, y1, x2, y2)
        return f"Line created from ({x1}, {y1}) to ({x2}, {y2}) mm"

    def _draw_rectangle(self, x1: float, y1: float, x2: float, y2: float) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory

        # Create 4 lines forming a closed rectangle
        factory.CreateLine(x1, y1, x2, y1)  # bottom
        factory.CreateLine(x2, y1, x2, y2)  # right
        factory.CreateLine(x2, y2, x1, y2)  # top
        factory.CreateLine(x1, y2, x1, y1)  # left

        return (
            f"Rectangle created from ({x1}, {y1}) to ({x2}, {y2}) mm "
            f"[{abs(x2-x1):.1f} x {abs(y2-y1):.1f} mm]"
        )

    def _draw_centered_rectangle(
        self, cx: float, cy: float, width: float, height: float
    ) -> str:
        hw, hh = width / 2, height / 2
        return self._draw_rectangle(cx - hw, cy - hh, cx + hw, cy + hh)

    def _draw_circle(self, cx: float, cy: float, radius: float) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory
        factory.CreateClosedCircle(cx, cy, radius)
        return f"Circle created at ({cx}, {cy}) with radius {radius} mm"

    def _draw_arc(
        self, cx: float, cy: float, radius: float,
        start_angle: float, end_angle: float,
    ) -> str:
        self._ensure_sketch_open()
        values = (cx, cy, radius, start_angle, end_angle)
        if any(isinstance(item, bool) or not isinstance(item, (int, float))
               or not math.isfinite(item) for item in values):
            raise ValueError("Arc coordinates, radius, and angles must be finite numbers")
        if radius <= 0:
            raise ValueError("Arc radius must be positive")
        raw_span = end_angle - start_angle
        span = raw_span % 360
        if span == 0 or abs(raw_span) >= 360:
            raise ValueError("Arc must sweep strictly between 0 and 360 degrees; use circle for 360")
        factory = self._active_factory
        normalized_start = start_angle % 360
        start_rad = math.radians(normalized_start)
        end_rad = math.radians(normalized_start + span)
        arc = factory.CreateCircle(cx, cy, radius, start_rad, end_rad)
        return (
            f"Arc {getattr(arc, 'Name', '<unnamed>')!r} created at ({cx}, {cy}), "
            f"radius={radius} mm, from {start_angle}° to {end_angle}° "
            f"counter-clockwise (sweep {span}°). Close/update the sketch to validate it."
        )

    def _draw_spline(self, points: list[list[float]], closed: bool = False) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory

        # Create a spline using control points
        # CATIA V5 Sketch.OpenEdition() returns a Factory2D
        # Factory2D.CreateSpline expects an array of 2D points
        spline_pts = []
        for pt in points:
            ctrl_pt = factory.CreatePoint(pt[0], pt[1])
            spline_pts.append(ctrl_pt)

        spline = factory.CreateSpline(spline_pts)

        if closed and len(points) >= 3:
            # Close the spline by adding a line from last to first point
            factory.CreateLine(points[-1][0], points[-1][1], points[0][0], points[0][1])

        pts_str = ", ".join(f"({p[0]}, {p[1]})" for p in points)
        return f"Spline created through {len(points)} points: {pts_str}" + (
            " (closed)" if closed else ""
        )

    def _draw_point(self, x: float, y: float) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory
        factory.CreatePoint(x, y)
        return f"Point created at ({x}, {y}) mm"

    def _add_constraint(self, args: dict[str, Any]) -> str:
        self._ensure_sketch_open()
        sketch = self._active_sketch
        constraint_type = args["type"]
        value = args.get("value")
        idx1 = args.get("geometry_index_1")
        idx2 = args.get("geometry_index_2")

        if constraint_type not in CONSTRAINT_SPECS:
            raise ValueError(f"Unknown constraint type: {constraint_type}")
        cst_code, element_count = CONSTRAINT_SPECS[constraint_type]
        if constraint_type == "distance" and idx2 is None:
            cst_code, element_count = 5, 1  # catCstTypeLength, not catCstTypeReference

        dimensional = constraint_type in ("distance", "radius", "angle")
        if dimensional:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Constraint '{constraint_type}' requires a finite numeric value.")
            if not math.isfinite(value):
                raise ValueError("Constraint value must be finite.")
            if constraint_type == "radius" and value <= 0:
                raise ValueError("Radius must be greater than zero (mm).")
            if constraint_type == "distance" and (value < 0 or (element_count == 1 and value == 0)):
                raise ValueError("Distance must be nonnegative; line length must be positive (mm).")
            if constraint_type == "angle" and not 0 <= value <= 360:
                raise ValueError("Angle must be between 0 and 360 degrees.")
        elif value is not None:
            raise ValueError(f"Geometric constraint '{constraint_type}' does not accept a value.")

        if element_count == 1 and idx2 is not None:
            raise ValueError(f"Constraint '{constraint_type}' takes only geometry_index_1.")
        if element_count == 2 and idx2 is None:
            raise ValueError(f"Constraint '{constraint_type}' requires geometry_index_2.")

        geom = sketch.GeometricElements
        indices = [idx1] if element_count == 1 else [idx1, idx2]
        count = geom.Count
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= count:
                raise ValueError(
                    f"Invalid geometry index {index!r}; expected an integer in 1..{count}. "
                    "Refresh catia_sketch_get_geometry before applying constraints."
                )
        if element_count == 2 and idx1 == idx2:
            raise ValueError("A two-element constraint requires two distinct geometry indices.")

        # AddMonoEltCst/AddBiEltCst take Reference objects, not raw Geometry2D dispatches.
        part = self.conn.get_active_part()
        references = []
        for index in indices:
            try:
                references.append(part.CreateReferenceFromObject(geom.Item(index)))
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot create CATIA Reference for sketch geometry index {index}: {exc}"
                ) from exc

        constraints = sketch.Constraints
        method_name = "AddMonoEltCst" if element_count == 1 else "AddBiEltCst"
        try:
            constraint = getattr(constraints, method_name)(cst_code, *references)
        except Exception as exc:
            raise RuntimeError(
                f"CATIA {method_name} failed for '{constraint_type}' "
                f"(type={cst_code}, geometry_indices={indices}): {exc}. "
                "Check the current geometry types and existing constraints before retrying; "
                "radius requires a circle/arc, length a line, and angle two lines."
            ) from exc

        if dimensional:
            try:
                dimension = constraint.Dimension
                dimension.Value = value
                actual = float(dimension.Value)
                if not math.isclose(actual, value, rel_tol=1e-9, abs_tol=1e-7):
                    raise RuntimeError(f"Dimension readback is {actual}, expected {value}")
            except Exception as exc:
                # Creation has already changed the sketch. Do not hide that fact or add
                # a duplicate constraint by automatically retrying the whole operation.
                raise RuntimeError(
                    f"'{constraint_type}' constraint was created, but setting/verifying "
                    f"its dimension failed: {exc}. The new constraint remains in the sketch; "
                    "inspect it before retrying."
                ) from exc
            unit = "degrees" if constraint_type == "angle" else "mm"
            return (
                f"{constraint_type.capitalize()} constraint added: {value} {unit}. "
                "Dimension readback verified; close the sketch and update the part to check the solve."
            )

        return (
            f"{constraint_type.capitalize()} constraint added. "
            "Close the sketch and update the part to check the solve."
        )

    def _get_geometry(self) -> str:
        self._ensure_sketch_open()
        sketch = self._active_sketch
        geom = sketch.GeometricElements

        elements = []
        for i in range(1, geom.Count + 1):
            elem = geom.Item(i)
            info = {
                "index": i,
                "name": elem.Name,
            }
            # Try to get the geometry type
            try:
                info["type"] = elem.GeometricType
            except Exception:
                pass
            elements.append(info)

        if not elements:
            return "No geometry elements in the active sketch"
        return json.dumps(elements, indent=2)
