"""Sketcher tools for CATIA V5.

2D sketch creation and editing: lines, circles, rectangles, arcs, splines, constraints.
All dimensions are in millimeters. CATIA COM API uses millimeters natively.
"""

from __future__ import annotations

import json
import math
from typing import Any

from catia_mcp.connection import CATIAConnection
from catia_mcp.runtime import same_object

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
    "concentricity": (3, 2),
    "symmetry": (15, 3),
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
    "length": (5, 1),
    "midpoint": (16, 2),
    "equidistance": (17, 3),
    "major_radius": (18, 1),
    "minor_radius": (19, 1),
}


class SketcherTools:
    """Tools for 2D sketch operations in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection
        self._active_sketch: Any | None = None
        self._active_factory: Any | None = None
        self._active_document_identity: tuple[str, str] | None = None
        self._active_document = None
        self._adopted_ui_sketch = False

    @staticmethod
    def _document_identity(document: Any) -> tuple[str, str]:
        return (str(document.Name), str(getattr(document, "FullName", "")))

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_sketch_set_axis",
                "description": "Set a fresh Line2D index as sketch revolution axis. Marks it Construction so it is not an extra profile contour, then assigns Sketch.CenterLine. Indices are transient.",
                "inputSchema": {"type": "object", "properties": {
                    "geometry_index": {"type": "integer", "minimum": 1}}, "required": ["geometry_index"]},
            },
            {
                "name": "catia_sketch_ellipse",
                "description": "Create a full ellipse in the edited sketch; lengths mm, major axis direction angle degrees.",
                "inputSchema": {"type": "object", "properties": {
                    "cx": {"type": "number", "default": 0}, "cy": {"type": "number", "default": 0},
                    "major_radius": {"type": "number", "exclusiveMinimum": 0},
                    "minor_radius": {"type": "number", "exclusiveMinimum": 0},
                    "angle_deg": {"type": "number", "default": 0}}, "required": ["major_radius", "minor_radius"]},
            },
            {
                "name": "catia_sketch_diagnose",
                "description": "Read constraint statuses in the edited sketch; this is not a full GUI Sketch Analysis or proof of profile closure.",
                "inputSchema": {"type": "object", "properties": {}}, "readOnlyHint": True,
            },
            {
                "name": "catia_sketch_import_geometry",
                "description": "Project or intersect an exact geometry handle into the currently edited sketch. This is not a support-change operation.",
                "inputSchema": {"type": "object", "properties": {
                    "mode": {"enum": ["project", "intersect"]},
                    "geometry_handle": {"type": "string"},
                    "construction": {"type": "boolean", "default": False}},
                    "required": ["mode", "geometry_handle"]},
            },
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
                        "support_handle": {"type": "string", "description": "Plane handle from catia_list_objects; not an unverified arbitrary face"},
                        "body_handle": {"type": "string"},
                        "axis_data": {"type": "array", "items": {"type": "number"}, "minItems": 9, "maxItems": 9,
                                      "description": "Part-frame origin XYZ in mm, horizontal unit vector XYZ, vertical unit vector XYZ. Vectors must be orthonormal and compatible with support."},
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
                        "construction": {"type": "boolean", "default": False},
                        "as_axis": {"type": "boolean", "default": False,
                                    "description": "Set Construction=true and Sketch.CenterLine for Shaft/Groove"},
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
                        "anchor_origin": {"type": "boolean", "default": False, "description": "Require first corner (0,0); constrain it coincident to the sketch origin, alongside H/V and size constraints. No blanket Fix."},
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
                        "anchor_origin": {"type": "boolean", "default": False, "description": "Require center (0,0); add concentricity to origin and a driving radius. Native iso-constraint status still requires CATIA verification."},
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
                    "Supports distance, length, radius, angle, coincidence, tangent, "
                    "perpendicular, parallel, horizontal, vertical, fix, concentricity, symmetry, midpoint, equidistance and ellipse radii. "
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
                                "concentricity", "symmetry", "length", "midpoint",
                                "equidistance", "major_radius", "minor_radius",
                            ],
                        },
                        "value": {
                            "type": "number",
                            "description": "Constraint value (mm or degrees). Required for distance, radius, angle.",
                        },
                        "geometry_index_3": {"type": "integer", "minimum": 1},
                        "driving": {"type": "boolean", "default": True},
                        **{f"element_{i}": {
                            "type": "string", "enum": ["whole", "start", "end", "origin", "horizontal_axis", "vertical_axis"],
                            "description": "Exact sub-element; start/end require a Line2D index. Absolute-axis selectors omit the corresponding geometry index."
                        } for i in (1, 2, 3)},
                        "distance_direction": {"type": "string", "enum": ["normal", "horizontal", "vertical"]},
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
                    "required": ["type"],
                },
            },
            {
                "name": "catia_sketch_get_geometry",
                "description": "List geometry with transient indices/types. Constraint selectors start/end address exact Line2D endpoints; origin and horizontal_axis/vertical_axis need no index.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        match tool_name:
            case "catia_sketch_set_axis":
                self._ensure_sketch_open()
                geometry = self._active_sketch.GeometricElements
                index = arguments["geometry_index"]
                if not 1 <= index <= geometry.Count:
                    raise ValueError("Refresh sketch geometry; axis index is out of range")
                return self._set_axis(geometry.Item(index))
            case "catia_sketch_ellipse":
                self._ensure_sketch_open()
                major, minor = arguments["major_radius"], arguments["minor_radius"]
                if not 0 < minor <= major:
                    raise ValueError("Ellipse needs 0 < minor_radius <= major_radius")
                angle = math.radians(arguments.get("angle_deg", 0))
                ellipse = self._active_factory.CreateClosedEllipse(arguments.get("cx", 0), arguments.get("cy", 0), math.cos(angle), math.sin(angle), major, minor)
                self._track(ellipse, "ellipse2d")
                return f"Ellipse created: {ellipse.Name}; radii {major}, {minor} mm"
            case "catia_sketch_diagnose":
                return self._diagnose()
            case "catia_sketch_import_geometry":
                self._ensure_sketch_open()
                reference = self.conn.session.reference(arguments["geometry_handle"], {"point", "curve", "line", "plane", "surface", "face", "edge"})
                factory = self._active_factory
                geometry = (factory.CreateProjection if arguments["mode"] == "project" else factory.CreateIntersection)(reference)
                handle = self.conn.session.mark_created(geometry, "geometry")
                geometry.Construction = arguments.get("construction", False)
                self._active_sketch.Evaluate()
                return {"ok": True, "handle": handle, "warnings": ["Close/update sketch to verify resulting geometry"]}
            case "catia_create_sketch":
                if arguments.get("body_handle"):
                    self.conn.operation_body = self.conn.session.resolve(arguments["body_handle"], {"body"}).value
                if "plane" in arguments and "support_handle" in arguments:
                    raise ValueError("Choose plane OR support_handle")
                return self._create_sketch(arguments.get("plane", "xy"), arguments.get("support_handle"), arguments.get("axis_data"))
            case "catia_close_sketch":
                return self._close_sketch()
            case "catia_sketch_line":
                return self._draw_line(
                    arguments["x1"], arguments["y1"],
                    arguments["x2"], arguments["y2"],
                    arguments.get("construction", False), arguments.get("as_axis", False),
                )
            case "catia_sketch_rectangle":
                return self._draw_rectangle(
                    arguments["x1"], arguments["y1"],
                    arguments["x2"], arguments["y2"],
                    arguments.get("anchor_origin", False),
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
                    arguments.get("anchor_origin", False),
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
                "No bound sketch. Use catia_sketch_context and catia_sketch_begin_edit for an existing sketch, or catia_create_sketch for a new sketch."
            )
        if self._active_document is not None and not same_object(self._active_document, self.conn.active_document):
            raise RuntimeError("Active document identity changed; return to the bound document")
        if self._adopted_ui_sketch and not same_object(self.conn.get_active_part().InWorkObject, self._active_sketch):
            raise RuntimeError("UI sketch target changed; stop and inspect sketch context")
        if self._active_document_identity != self._document_identity(self.conn.active_document):
            raise RuntimeError(
                "Active CATIA document changed while a sketch was open. "
                "Return to the original document before editing or closing that sketch."
            )

    def _track(self, value, kind):
        state = getattr(self.conn, "session", None)
        if state is not None:
            state.mark_created(value, kind)
        return value

    def _create_sketch(self, plane: str = "xy", support_handle=None, axis_data=None) -> str:
        if self._active_sketch is not None:
            raise RuntimeError("SKETCH_ALREADY_OPEN: close the current sketch before creating another")
        self.conn.ensure_connected()
        document = self.conn.active_document
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        if axis_data is not None:
            if len(axis_data) != 9 or any(not math.isfinite(x) for x in axis_data):
                raise ValueError("axis_data must contain nine finite numbers")
            horizontal, vertical = axis_data[3:6], axis_data[6:9]
            if not all(math.isclose(sum(x*x for x in vector), 1, abs_tol=1e-9) for vector in (horizontal, vertical)) or not math.isclose(sum(x*y for x, y in zip(horizontal, vertical)), 0, abs_tol=1e-9):
                raise ValueError("Sketch horizontal and vertical axes must be orthonormal")

        # Get the reference plane
        origin = part.OriginElements
        plane_key = plane.lower()
        if plane_key not in PLANE_MAP:
            raise ValueError(f"Unknown plane '{plane}'. Use 'xy', 'yz', or 'zx'.")

        plane_attr = PLANE_MAP[plane_key]
        ref_plane = getattr(origin, plane_attr)
        ref = part.CreateReferenceFromObject(ref_plane)
        if support_handle:
            ref = self.conn.session.reference(support_handle, {"plane"})

        # Create the sketch on the plane
        sketches = body.Sketches
        previous_count = sketches.Count
        sketch = sketches.Add(ref)
        state = getattr(self.conn, "session", None)
        if state is not None:
            state.mark_created(sketch, "sketch")
        if axis_data is not None:
            sketch.SetAbsoluteAxisData(tuple(axis_data))
        if sketches.Count != previous_count + 1:
            raise RuntimeError(
                "CATIA returned a new sketch but the target body sketch count did not increase "
                "by one. Inspect the model tree before retrying."
            )

        # Open the sketch for editing
        factory = sketch.OpenEdition()
        self._active_sketch = sketch
        self._active_document = document
        self._adopted_ui_sketch = False
        self._active_document_identity = self._document_identity(document)
        self._active_factory = factory

        plane_names = {"xy": "XY (front)", "yz": "YZ (right)", "zx": "ZX (top)"}
        return (
            f"Sketch {sketch.Name!r} created in {document.Name!r}/{body.Name!r} "
            f"on {support_handle or plane_names.get(plane_key, plane)} plane; editing=true. "
            "Use fresh catia_sketch_get_geometry indices for constraints."
        )

    def _close_sketch(self) -> str:
        self._ensure_sketch_open()
        sketch = self._active_sketch
        sketch.CloseEdition()
        self._active_sketch = None
        self._active_factory = None
        self._active_document_identity = None
        self._active_document = None
        self._adopted_ui_sketch = False
        self.conn.get_active_part().UpdateObject(sketch)
        self.conn.refresh_display()
        return "Sketch closed. You can now apply Part Design features (pad, pocket, etc.)."

    def _draw_line(self, x1: float, y1: float, x2: float, y2: float,
                   construction=False, as_axis=False) -> str:
        self._ensure_sketch_open()
        if any(not math.isfinite(v) for v in (x1, y1, x2, y2)) or (x1 == x2 and y1 == y2):
            raise ValueError("Line endpoints must be finite and distinct")
        factory = self._active_factory
        line = self._track(factory.CreateLine(x1, y1, x2, y2), "line2d")
        if construction or as_axis:
            line.Construction = True
        if as_axis:
            return self._set_axis(line)
        return f"Line created from ({x1}, {y1}) to ({x2}, {y2}) mm"

    def _set_axis(self, line):
        if int(line.GeometricType) != 3:  # CatGeometricType.catGeoTypeLine2D
            raise ValueError("Sketch revolution axis must be a Line2D, not an arbitrary edge")
        line.Construction = True
        self._active_sketch.CenterLine = line
        if not bool(line.Construction):
            raise RuntimeError("Axis created but Construction readback failed")
        from catia_mcp.runtime import same_object
        if not same_object(self._active_sketch.CenterLine, line):
            raise RuntimeError("Sketch.CenterLine readback differs; inspect before retrying")
        return f"Sketch axis set to {line.Name!r}; construction=true (excluded from profile)"

    def _diagnose(self):
        self._ensure_sketch_open()
        constraints = self._active_sketch.Constraints
        labels = ["satisfied", "strongly_not_satisfied", "wrong_orientation_or_side",
                  "wrong_value", "wrong_geometry_type", "broken"]
        statuses = []
        for i in range(1, constraints.Count + 1):
            c = constraints.Item(i)
            status = int(c.Status)
            inactive = bool(c.IsInactive())
            statuses.append({"index": i, "name": str(c.Name), "status": status,
                             "diagnosis": labels[status] if 0 <= status < len(labels) else "unknown",
                             "inactive": inactive})
        return {"ok": True, "constraints": statuses,
                "all_constraints_satisfied": all(c["status"] == 0 for c in statuses if not c["inactive"]),
                "inactive_count": sum(c["inactive"] for c in statuses),
                "profile_closed": "not_verified", "remaining_dof": None,
                "iso_constrained": None,
                "warning": "Satisfied constraints do not prove zero DOF or absence of redundancy. This documented Automation interface exposes no full sketch DOF status. Verify Sketch Analysis in CATIA; never fix everything merely to turn it green."}

    def _draw_rectangle(self, x1: float, y1: float, x2: float, y2: float, anchor_origin: bool = False) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory

        if x1 == x2 or y1 == y2:
            raise ValueError("Rectangle width and height must be nonzero")
        if anchor_origin and (x1 != 0 or y1 != 0):
            raise ValueError("anchor_origin requires first corner (0,0)")

        # Create 4 lines forming a closed rectangle
        vertices = [self._track(factory.CreatePoint(x, y), "point2d") for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
        lines = [self._track(factory.CreateLine(*coordinates), "line2d") for coordinates in
                 ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1))]
        part = self.conn.get_active_part()
        constraints = self._active_sketch.Constraints
        for index, line in enumerate(lines):
            line.StartPoint = vertices[index]
            line.EndPoint = vertices[(index + 1) % 4]
            self._track(constraints.AddMonoEltCst(10 if index % 2 == 0 else 13, part.CreateReferenceFromObject(line)), "constraint")
        for line, length in ((lines[0], abs(x2-x1)), (lines[1], abs(y2-y1))):
            constraint = constraints.AddMonoEltCst(5, part.CreateReferenceFromObject(line))
            self._track(constraint, "constraint")
            constraint.Dimension.ValuateFromString(f"{length}mm")
        if anchor_origin:
            self._track(constraints.AddBiEltCst(2, part.CreateReferenceFromObject(vertices[0]),
                        part.CreateReferenceFromObject(self._active_sketch.AbsoluteAxis.Origin)), "constraint")
        self._active_sketch.Evaluate()
        if not self._diagnose()["all_constraints_satisfied"]:
            raise RuntimeError("Rectangle created but sketch constraints are not satisfied")

        return (
            f"Rectangle created from ({x1}, {y1}) to ({x2}, {y2}) mm "
            f"[{abs(x2-x1):.1f} x {abs(y2-y1):.1f} mm]; shared endpoints, H/V and length constraints. "
            + ("First corner constrained to origin; native iso-constrained status not available through this API."
               if anchor_origin else "Position is not constrained.")
        )

    def _draw_centered_rectangle(
        self, cx: float, cy: float, width: float, height: float
    ) -> str:
        hw, hh = width / 2, height / 2
        return self._draw_rectangle(cx - hw, cy - hh, cx + hw, cy + hh)

    def _draw_circle(self, cx: float, cy: float, radius: float, anchor_origin: bool = False) -> str:
        self._ensure_sketch_open()
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError("Circle radius must be positive and finite")
        if anchor_origin and (cx != 0 or cy != 0):
            raise ValueError("anchor_origin requires center (0,0)")
        factory = self._active_factory
        circle = self._track(factory.CreateClosedCircle(cx, cy, radius), "circle2d")
        if anchor_origin:
            part = self.conn.get_active_part()
            constraints = self._active_sketch.Constraints
            ref = part.CreateReferenceFromObject(circle)
            self._track(constraints.AddBiEltCst(3, part.CreateReferenceFromObject(self._active_sketch.AbsoluteAxis.Origin), ref), "constraint")
            c = self._track(constraints.AddMonoEltCst(14, ref), "constraint")
            c.Mode = 0
            c.Dimension.ValuateFromString(f"{radius}mm")
            self._active_sketch.Evaluate()
            if not self._diagnose()["all_constraints_satisfied"]:
                raise RuntimeError("Circle created but constraint system is not satisfied; inspect before retrying")
        return (f"Circle created at ({cx}, {cy}) with radius {radius} mm. "
                + ("Origin concentricity and driving radius added; native iso-constrained status unverified."
                   if anchor_origin else "No constraints added."))

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
        self._track(arc, "circle2d")
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
            ctrl_pt = factory.CreateControlPoint(pt[0], pt[1])
            self._track(ctrl_pt, "controlpoint2d")
            spline_pts.append(ctrl_pt)

        spline = factory.CreateSpline(spline_pts)
        self._track(spline, "curve")

        if closed and len(points) >= 3:
            # Close the spline by adding a line from last to first point
            self._track(factory.CreateLine(points[-1][0], points[-1][1], points[0][0], points[0][1]), "line2d")

        pts_str = ", ".join(f"({p[0]}, {p[1]})" for p in points)
        return f"Spline created through {len(points)} points: {pts_str}" + (
            " (closed)" if closed else ""
        )

    def _draw_point(self, x: float, y: float) -> str:
        self._ensure_sketch_open()
        factory = self._active_factory
        self._track(factory.CreatePoint(x, y), "point2d")
        return f"Point created at ({x}, {y}) mm"

    def _add_constraint(self, args: dict[str, Any]) -> str:
        self._ensure_sketch_open()
        sketch = self._active_sketch
        constraint_type = args["type"]
        value = args.get("value")
        idx1 = args.get("geometry_index_1")
        idx2 = args.get("geometry_index_2")
        idx3 = args.get("geometry_index_3")

        if constraint_type not in CONSTRAINT_SPECS:
            raise ValueError(f"Unknown constraint type: {constraint_type}")
        cst_code, element_count = CONSTRAINT_SPECS[constraint_type]
        if constraint_type == "distance" and idx2 is None and "element_2" not in args:
            cst_code, element_count = 5, 1  # catCstTypeLength, not catCstTypeReference

        dimensional = constraint_type in ("distance", "length", "radius", "major_radius", "minor_radius", "angle")
        driving = args.get("driving", True)
        if not dimensional and not driving:
            raise ValueError("Reference mode applies only to dimensional constraints")
        if dimensional and not driving:
            if value is not None:
                raise ValueError("A reference dimension must omit value; it measures the geometry")
        elif dimensional:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Constraint '{constraint_type}' requires a finite numeric value.")
            if not math.isfinite(value):
                raise ValueError("Constraint value must be finite.")
            if constraint_type in {"radius", "major_radius", "minor_radius", "length"} and value <= 0:
                raise ValueError("Radius must be greater than zero (mm).")
            if constraint_type == "distance" and (value < 0 or (element_count == 1 and value == 0)):
                raise ValueError("Distance must be nonnegative; line length must be positive (mm).")
            if constraint_type == "angle" and not 0 <= value <= 360:
                raise ValueError("Angle must be between 0 and 360 degrees.")
        elif value is not None:
            raise ValueError(f"Geometric constraint '{constraint_type}' does not accept a value.")

        if element_count == 1 and (idx2 is not None or "element_2" in args):
            raise ValueError(f"Constraint '{constraint_type}' takes only geometry_index_1.")
        if element_count == 2 and idx2 is None and "element_2" not in args:
            raise ValueError(f"Constraint '{constraint_type}' requires geometry_index_2.")
        if element_count == 3 and ((idx2 is None and "element_2" not in args) or (idx3 is None and "element_3" not in args)):
            raise ValueError("This constraint requires three explicit elements")
        if element_count < 3 and (idx3 is not None or "element_3" in args):
            raise ValueError("Third geometry is supported only for symmetry")

        geom = sketch.GeometricElements
        indices = [idx1, idx2, idx3][:element_count]
        count = geom.Count
        elements = []
        for position, index in enumerate(indices, 1):
            selector = args.get(f"element_{position}", "whole")
            axis_properties = {"origin": "Origin", "horizontal_axis": "HorizontalReference", "vertical_axis": "VerticalReference"}
            if selector in axis_properties:
                if index is not None:
                    raise ValueError("Absolute-axis elements must omit their geometry index")
                elements.append(getattr(sketch.AbsoluteAxis, axis_properties[selector]))
                continue
            if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= count:
                raise ValueError(
                    f"Invalid geometry index {index!r}; expected an integer in 1..{count}. "
                    "Refresh catia_sketch_get_geometry before applying constraints."
                )
            obj = geom.Item(index)
            if selector in {"start", "end"}:
                if int(obj.GeometricType) != 3:
                    raise ValueError("Endpoint selection requires Line2D")
                obj = obj.StartPoint if selector == "start" else obj.EndPoint
            elif selector != "whole":
                raise ValueError("Unknown geometry selector")
            elements.append(obj)
        if any(same_object(obj, previous) for i, obj in enumerate(elements) for previous in elements[:i]):
            raise ValueError("Constraint requires distinct elements")

        # AddMonoEltCst/AddBiEltCst take Reference objects, not raw Geometry2D dispatches.
        part = self.conn.get_active_part()
        types = [int(obj.GeometricType) for obj in elements]
        direction = args.get("distance_direction", "normal")
        if direction not in {"normal", "horizontal", "vertical"} or ("distance_direction" in args and cst_code != 1):
            raise ValueError("distance_direction applies only to two-element distance")
        if cst_code == 5 and types != [3]:
            raise ValueError("Length requires a Line2D")
        if constraint_type == "midpoint" and types != [2, 3]:
            raise ValueError("Midpoint requires Point2D then Line2D")
        if constraint_type == "equidistance" and not (types[0] == types[1] and types[0] in {2, 3} and types[2] == 2):
            raise ValueError("Equidistance requires two points or two lines, followed by a point")
        if constraint_type in {"major_radius", "minor_radius"} and types != [8]:
            raise ValueError("Ellipse radius requires Ellipse2D")
        if constraint_type == "radius" and types != [5]:
            raise ValueError("Radius requires Circle2D/arc geometry")
        if constraint_type in {"horizontal", "vertical", "angle", "parallel", "perpendicular"} and any(t != 3 for t in types):
            raise ValueError("This constraint requires Line2D geometry")
        if constraint_type == "symmetry" and types[-1] != 3:
            raise ValueError("Symmetry third element must be a Line2D axis")
        if constraint_type == "symmetry" and types[0] != types[1]:
            raise ValueError("Symmetric elements must have matching geometry types")
        if constraint_type == "tangent" and types == [3, 3]:
            raise ValueError("CATIA tangency does not accept two lines; use parallelism or coincidence as intended")
        references = []
        for index, obj in zip(indices, elements):
            try:
                references.append(part.CreateReferenceFromObject(obj))
            except Exception as exc:
                raise RuntimeError(
                    f"Cannot create CATIA Reference for sketch geometry index {index}: {exc}"
                ) from exc

        constraints = sketch.Constraints
        method_name = {1: "AddMonoEltCst", 2: "AddBiEltCst", 3: "AddTriEltCst"}[element_count]
        try:
            constraint = getattr(constraints, method_name)(cst_code, *references)
            self._track(constraint, "constraint")
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
                constraint.Mode = 0 if driving else 1
                if cst_code == 1:
                    constraint.DistanceDirection = {"normal": 0, "horizontal": 1, "vertical": 2}[direction]
                if driving:
                    dimension.ValuateFromString(f"{value}deg" if constraint_type == "angle" else f"{value}mm")
                readback = str(dimension.ValueAsString())
            except Exception as exc:
                # Creation has already changed the sketch. Do not hide that fact or add
                # a duplicate constraint by automatically retrying the whole operation.
                raise RuntimeError(
                    f"'{constraint_type}' constraint was created, but setting/verifying "
                    f"its dimension failed: {exc}. The new constraint remains in the sketch; "
                    "inspect it before retrying."
                ) from exc
            unit = "degrees" if constraint_type == "angle" else "mm"
            sketch.Evaluate()
            if int(constraint.Status) != 0 or not self._diagnose()["all_constraints_satisfied"]:
                raise RuntimeError(f"Constraint created but not solved: status={constraint.Status}")
            return (
                f"{constraint_type.capitalize()} constraint added; driving={driving}, readback={readback}. "
                "Constraint status OK; close the sketch and update the part to check geometry."
            )

        sketch.Evaluate()
        if int(constraint.Status) != 0 or not self._diagnose()["all_constraints_satisfied"]:
            raise RuntimeError(f"Constraint created but not solved: status={constraint.Status}")
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
            try:
                info["construction"] = bool(elem.Construction)
                from catia_mcp.runtime import same_object
                info["is_revolution_axis"] = same_object(sketch.CenterLine, elem)
            except Exception:
                pass
            if getattr(self.conn, "session", None) is not None:
                from catia_mcp.tools.engineering import geometry_kind
                info["handle"] = self.conn.session.register(elem, geometry_kind(elem))
            elements.append(info)

        if not elements:
            return "No geometry elements in the active sketch"
        return json.dumps(elements, indent=2)
