"""Part Design tools for CATIA V5.

3D feature creation: Pad, Pocket, Fillet, Chamfer, Shaft, Groove, Hole,
RectPattern, CircPattern, Mirror, Rib, Slot, Shell, Thickness, Draft.
"""

from __future__ import annotations

import json
import math
import ntpath
from typing import Any

from catia_mcp.connection import CATIAConnection


class PartDesignTools:
    """Tools for 3D Part Design features in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_pad",
                "description": (
                    "Create a Pad (extrusion) from the last sketch. "
                    "Extrudes a 2D profile into a 3D solid along the normal to the sketch plane."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "height": {
                            "type": "number",
                            "description": "Extrusion height/depth in mm",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Extrusion direction: 'normal' (default), 'reverse', 'both'",
                            "enum": ["normal", "reverse", "both"],
                            "default": "normal",
                        },
                        "symmetric": {
                            "type": "boolean",
                            "description": "If true, extrude equally on both sides (total = height)",
                            "default": False,
                        },
                        "sketch_name": {
                            "type": "string",
                            "description": "Name of sketch to use. If not specified, uses the last created sketch.",
                        },
                    },
                    "required": ["height"],
                },
            },
            {
                "name": "catia_pocket",
                "description": (
                    "Create a Pocket (cut extrusion) from the last sketch. "
                    "Removes material by extruding a 2D profile inward."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "depth": {
                            "type": "number",
                            "description": "Cut depth in mm",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Cut direction: 'normal' (default), 'reverse'",
                            "enum": ["normal", "reverse"],
                            "default": "normal",
                        },
                        "sketch_name": {
                            "type": "string",
                            "description": "Name of sketch to use. If not specified, uses the last sketch.",
                        },
                    },
                    "required": ["depth"],
                },
            },
            {
                "name": "catia_shaft",
                "description": (
                    "Create a Shaft from a sketch. CATIA normally uses an axis inside the sketch. "
                    "To override it, select one straight axis in CATIA and set "
                    "axis_from_selection=true; the tool assigns its live Reference to RevoluteAxis."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "angle": {
                            "type": "number",
                            "description": "Revolution angle in degrees (default: 360 for full revolution)",
                            "default": 360,
                        },
                        "sketch_name": {
                            "type": "string",
                            "description": "Name of sketch to use.",
                        },
                        "axis_from_selection": {
                            "type": "boolean",
                            "description": (
                                "Use the one currently selected straight axis/line. With no "
                                "selection CATIA uses the sketch's own axis. A non-line or "
                                "multiple selection is rejected."
                            ),
                            "default": True,
                        },
                    },
                },
            },
            {
                "name": "catia_groove",
                "description": (
                    "Create a Groove (revolution cut). "
                    "Removes material by revolving a 2D profile around an axis."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "angle": {
                            "type": "number",
                            "description": "Revolution angle in degrees (default: 360)",
                            "default": 360,
                        },
                        "sketch_name": {
                            "type": "string",
                            "description": "Name of sketch to use.",
                        },
                    },
                },
            },
            {
                "name": "catia_fillet",
                "description": (
                    "Fillet the one edge currently selected in CATIA. Selection is read "
                    "immediately and is not a persistent edge ID. Edge names are unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "radius": {
                            "type": "number",
                            "description": "Fillet radius in mm",
                        },
                        "edge_name": {
                            "type": "string",
                            "description": (
                                "Legacy argument; rejected because names are not "
                                "exact references"
                            ),
                        },
                    },
                    "required": ["radius"],
                },
            },
            {
                "name": "catia_chamfer",
                "description": (
                    "Chamfer the one edge currently selected in CATIA using length+angle mode. "
                    "Edge names and stale selections are unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "length": {
                            "type": "number",
                            "description": "Chamfer length in mm",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Chamfer angle in degrees (default: 45)",
                            "default": 45,
                        },
                        "edge_name": {
                            "type": "string",
                            "description": (
                                "Legacy argument; rejected because names are not "
                                "exact references"
                            ),
                        },
                    },
                    "required": ["length"],
                },
            },
            {
                "name": "catia_hole",
                "description": (
                    "Create a simple flat-bottom Hole from a named positioning sketch "
                    "containing exactly one user point. The sketch and direction must "
                    "be checked against the target solid. Threading is unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "diameter": {
                            "type": "number",
                            "description": "Hole diameter in mm",
                        },
                        "depth": {
                            "type": "number",
                            "description": "Hole depth in mm",
                        },
                        "type": {
                            "type": "string",
                            "description": (
                                "Only 'simple' is implemented; other values "
                                "fail explicitly"
                            ),
                            "enum": ["simple", "counterbored", "countersunk", "tapered"],
                            "default": "simple",
                        },
                        "threaded": {
                            "type": "boolean",
                            "description": "Whether to add threading (default: false)",
                            "default": False,
                        },
                        "sketch_name": {
                            "type": "string",
                            "description": "Sketch containing the hole center point",
                        },
                    },
                    "required": ["diameter", "depth", "sketch_name"],
                },
            },
            {
                "name": "catia_rect_pattern",
                "description": (
                    "Pattern an explicitly named feature. Select two linear direction "
                    "supports in CATIA immediately before calling. Counts include source."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dir1_count": {
                            "type": "integer",
                            "description": "Number of instances in first direction",
                        },
                        "dir1_spacing": {
                            "type": "number",
                            "description": "Spacing in first direction (mm)",
                        },
                        "dir2_count": {
                            "type": "integer",
                            "description": "Number of instances in second direction (default: 1)",
                            "default": 1,
                        },
                        "dir2_spacing": {
                            "type": "number",
                            "description": "Spacing in second direction (mm)",
                            "default": 0,
                        },
                        "feature_name": {
                            "type": "string",
                            "description": "Unique name of a MainBody feature to pattern (required).",
                        },
                    },
                    "required": ["feature_name", "dir1_count", "dir1_spacing"],
                },
            },
            {
                "name": "catia_circ_pattern",
                "description": (
                    "Pattern an explicitly named feature around a selected point and "
                    "selected linear axis. Counts include source; default is a closed ring."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of instances around the circle",
                        },
                        "angular_spacing": {
                            "type": "number",
                            "description": "Angular spacing in degrees (default: equal spacing = 360/count)",
                        },
                        "feature_name": {
                            "type": "string",
                            "description": "Unique name of a MainBody feature to pattern (required).",
                        },
                    },
                    "required": ["feature_name", "count"],
                },
            },
            {
                "name": "catia_mirror",
                "description": (
                    "Mirror the current MainBody about an origin plane. "
                    "Mirroring one named feature is unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "plane": {
                            "type": "string",
                            "description": "Mirror plane: 'xy', 'yz', or 'zx'",
                            "enum": ["xy", "yz", "zx"],
                        },
                        "feature_name": {
                            "type": "string",
                            "description": "Legacy unsupported argument; omit it to mirror MainBody.",
                        },
                    },
                    "required": ["plane"],
                },
            },
            {
                "name": "catia_shell",
                "description": (
                    "Shell the active solid inward by removing the one face currently selected "
                    "in CATIA; inner thickness=t, outer thickness=0. Face names are unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "thickness": {
                            "type": "number",
                            "description": "Wall thickness in mm",
                        },
                        "faces_to_remove": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Legacy argument; non-empty values are rejected because "
                                "face names are not exact references"
                            ),
                        },
                    },
                    "required": ["thickness"],
                },
            },
            {
                "name": "catia_draft",
                "description": (
                    "Draft is unavailable until a selected face, neutral plane, pulling vector "
                    "and all CATIA mode arguments can be validated. No model change is made."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "angle": {
                            "type": "number",
                            "description": "Draft angle in degrees",
                        },
                        "face_name": {
                            "type": "string",
                            "description": "Legacy argument; rejected if supplied",
                        },
                        "pulling_direction": {
                            "type": "string",
                            "description": "Pulling direction plane: 'xy', 'yz', 'zx'",
                            "enum": ["xy", "yz", "zx"],
                            "default": "xy",
                        },
                    },
                    "required": ["angle"],
                },
            },
            {
                "name": "catia_thickness",
                "description": (
                    "Offset the one currently selected solid face; direction/sign still needs "
                    "live CATIA validation. Face names are unsupported."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "offset": {
                            "type": "number",
                            "description": "Thickness offset in mm; physical sign requires live CATIA calibration",
                        },
                        "face_name": {
                            "type": "string",
                            "description": "Legacy argument; rejected if supplied",
                        },
                    },
                    "required": ["offset"],
                },
            },
            {
                "name": "catia_list_features",
                "description": "List shapes in MainBody only; unknown COM types are reported honestly.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "catia_list_edges",
                "description": (
                    "Report the exact-topology limitation without changing the user's selection. "
                    "Names or indices cannot target a particular edge reliably."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
                "readOnlyHint": True,
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str | dict[str, Any]:
        match tool_name:
            case "catia_pad":
                return self._pad(arguments)
            case "catia_pocket":
                return self._pocket(arguments)
            case "catia_shaft":
                return self._shaft(arguments)
            case "catia_groove":
                return self._groove(arguments)
            case "catia_fillet":
                return self._fillet(arguments)
            case "catia_chamfer":
                return self._chamfer(arguments)
            case "catia_hole":
                return self._hole(arguments)
            case "catia_rect_pattern":
                return self._rect_pattern(arguments)
            case "catia_circ_pattern":
                return self._circ_pattern(arguments)
            case "catia_mirror":
                return self._mirror(arguments)
            case "catia_shell":
                return self._shell(arguments)
            case "catia_draft":
                return self._draft(arguments)
            case "catia_thickness":
                return self._thickness(arguments)
            case "catia_list_features":
                return self._list_features()
            case "catia_list_edges":
                return self._list_edges()
            case _:
                raise ValueError(f"Unknown part design tool: {tool_name}")

    def _get_last_sketch(self, sketch_name: str | None = None) -> Any:
        """Get a sketch by name or the last sketch in the body."""
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sketches = body.Sketches

        if sketch_name:
            matches = [sketches.Item(index) for index in range(1, sketches.Count + 1)
                       if str(sketches.Item(index).Name) == sketch_name]
            if len(matches) != 1:
                raise ValueError(
                    f"Sketch name {sketch_name!r} matched {len(matches)} sketches in "
                    f"{body.Name}; choose a unique name"
                )
            return matches[0]

        # Get the last sketch
        if sketches.Count == 0:
            raise RuntimeError("No sketches found in the active body. Create a sketch first.")
        return sketches.Item(sketches.Count)

    def _get_last_shape(self, feature_name: str | None = None) -> Any:
        """Get a shape/feature by name or the last one in the body."""
        body = self.conn.get_active_part_body()
        shapes = body.Shapes

        if feature_name:
            matches = [shapes.Item(index) for index in range(1, shapes.Count + 1)
                       if str(shapes.Item(index).Name) == feature_name]
            if len(matches) != 1:
                raise ValueError(
                    f"Feature name {feature_name!r} matched {len(matches)} shapes in "
                    f"{body.Name}; choose a unique name"
                )
            return matches[0]

        if shapes.Count == 0:
            raise RuntimeError("No features found in the active body.")
        return shapes.Item(shapes.Count)

    def _selected_geometry_reference(self, expected: str) -> Any:
        """Resolve the current CATIA selection once, never by a feature name/index."""
        document = self.conn.active_document
        selection = document.Selection
        if selection.Count2 != 1:
            raise ValueError(f"Select exactly one {expected.lower()} in the active CATPart")
        selected = selection.Item2(1)
        selected_type = str(selected.Type)
        if not selected_type.lower().endswith(expected.lower()):
            raise ValueError(
                f"Selected CATIA type {selected_type!r} is not a {expected.lower()}; "
                "select exact geometry, not its parent feature"
            )
        try:
            owner = selected.Document
        except AttributeError:
            owner = None
        if owner is not None:
            owner_path = str(getattr(owner, "FullName", ""))
            active_path = str(getattr(document, "FullName", ""))
            if owner_path and active_path and (
                ntpath.normcase(ntpath.normpath(owner_path))
                != ntpath.normcase(ntpath.normpath(active_path))
            ):
                raise RuntimeError("Selected topology belongs to a different document")
        part = self.conn.get_active_part()
        try:
            reference = selected.Reference
            if reference is not None:
                return reference
        except Exception:
            pass
        return part.CreateReferenceFromObject(selected.Value)

    def _selected_support_references(self, expected: tuple[str, str]) -> tuple[Any, Any]:
        """Capture two exact selected supports, in their current selection order."""
        document = self.conn.active_document
        selection = document.Selection
        if selection.Count2 != 2:
            raise ValueError(f"Select exactly two supports in CATIA: {expected}")
        part = self.conn.get_active_part()
        references = []
        for position, expected_type in enumerate(expected, start=1):
            selected = selection.Item2(position)
            actual_type = str(selected.Type)
            if not actual_type.lower().endswith(expected_type.lower()):
                raise ValueError(
                    f"Selection position {position} is {actual_type!r}; "
                    f"expected a {expected_type.lower()} support"
                )
            try:
                owner = selected.Document
            except AttributeError:
                owner = None
            if owner is not None:
                owner_path = str(getattr(owner, "FullName", ""))
                document_path = str(getattr(document, "FullName", ""))
                if owner_path and document_path and (
                    ntpath.normcase(ntpath.normpath(owner_path))
                    != ntpath.normcase(ntpath.normpath(document_path))
                ):
                    raise RuntimeError("Selected support belongs to another CATIA document")
            try:
                reference = selected.Reference
                if reference is None:
                    raise ValueError("Selection has no COM Reference")
                references.append(reference)
            except Exception:
                references.append(part.CreateReferenceFromObject(selected.Value))
        return references[0], references[1]

    def _pad(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        height = args["height"]
        direction = args.get("direction", "normal")
        symmetric = args.get("symmetric", False)

        pad = sf.AddNewPad(sketch, height)

        if symmetric:
            pad.IsSymmetric = True
        elif direction == "reverse":
            pad.DirectionOrientation = 1  # catReverse
        elif direction == "both":
            pad.IsSymmetric = True

        part.UpdateObject(pad)
        self.conn.refresh_display()
        return f"Pad created: {height} mm ({direction}). Feature: '{pad.Name}'"

    def _pocket(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        depth = args["depth"]

        pocket = sf.AddNewPocket(sketch, depth)

        if args.get("direction") == "reverse":
            pocket.DirectionOrientation = 1

        part.UpdateObject(pocket)
        self.conn.refresh_display()
        return f"Pocket created: {depth} mm deep. Feature: '{pocket.Name}'"

    def _shaft(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        angle = args.get("angle", 360)
        if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 < angle <= 360:
            raise ValueError("Shaft angle must be finite and in (0, 360] degrees")

        use_selection = args.get("axis_from_selection", True)
        if not isinstance(use_selection, bool):
            raise ValueError("axis_from_selection must be a boolean")
        axis_info = None
        if use_selection:
            axis_info = self._selected_axis_reference(required=False)

        try:
            shaft = sf.AddNewShaft(sketch)
        except Exception as exc:
            axis_note = (
                " A selected axis was captured, but AddNewShaft failed before CATIA could "
                "accept the RevoluteAxis override; CATIA may require the sketch itself to "
                "contain a valid axis."
                if axis_info is not None else ""
            )
            raise RuntimeError(
                f"CATIA could not create Shaft from sketch {sketch.Name!r}: {exc}.{axis_note}"
            ) from exc
        if axis_info is not None:
            axis_reference, axis_name, selection_type = axis_info
            try:
                shaft.RevoluteAxis = axis_reference
                if shaft.RevoluteAxis is None:
                    raise RuntimeError("CATIA returned an empty RevoluteAxis after assignment")
            except Exception as exc:
                raise RuntimeError(
                    f"Shaft {shaft.Name!r} was created, but CATIA rejected the selected "
                    f"axis {axis_name!r} ({selection_type}): {exc}. Inspect the feature "
                    "tree before retrying."
                ) from exc
        shaft.FirstAngle.Value = angle
        if not math.isclose(float(shaft.FirstAngle.Value), angle, abs_tol=1e-7):
            raise RuntimeError(
                f"Shaft {shaft.Name!r} was created, but CATIA did not apply the requested "
                "angle. Inspect the feature tree before retrying."
            )

        try:
            part.UpdateObject(shaft)
        except Exception as exc:
            raise RuntimeError(
                f"Shaft {shaft.Name!r} was created but UpdateObject failed: {exc}. "
                "Inspect the feature tree before retrying."
            ) from exc
        try:
            part.Update()
        except Exception as exc:
            raise RuntimeError(
                f"Shaft {shaft.Name!r} was created, but full Part.Update failed: {exc}. "
                "Inspect the model before retrying."
            ) from exc
        try:
            up_to_date = bool(part.IsUpToDate(shaft))
        except Exception as exc:
            raise RuntimeError(
                f"Shaft {shaft.Name!r} was updated, but CATIA status readback failed: {exc}. "
                "Inspect the feature before retrying."
            ) from exc
        if not up_to_date:
            raise RuntimeError(
                f"Shaft {shaft.Name!r} exists but CATIA reports it is not up to date. "
                "Inspect it before retrying."
            )
        self.conn.refresh_display()
        axis_message = (
            f"selected axis {axis_name!r} ({selection_type})"
            if axis_info is not None else "axis taken from the sketch"
        )
        return f"Shaft created: {angle}°; {axis_message}. Feature: '{shaft.Name}'"

    def _selected_axis_reference(self, *, required: bool) -> tuple[Any, str, str] | None:
        """Capture one currently selected straight axis as a short-lived COM Reference."""
        document = self.conn.active_document
        selection = document.Selection
        count = selection.Count2
        if count == 0:
            if required:
                raise ValueError("Select one straight revolution axis in CATIA first")
            return None
        if count != 1:
            raise ValueError("Select exactly one straight revolution axis in CATIA")

        selected = selection.Item2(1)
        selection_type = str(selected.Type)
        normalized_type = selection_type.casefold()
        allowed = {
            "line2d", "axis2d", "line", "rectilineartridimfeatedge",
            "rectilinearbidimfeatedge", "rectilinearmonodimfeatedge",
        }
        if normalized_type not in allowed:
            raise ValueError(
                f"Selected CATIA type {selection_type!r} is not a supported straight axis. "
                "Select a line/axis itself, not its sketch or parent feature."
            )

        try:
            owner = selected.Document
        except Exception:
            owner = None
        if owner is not None:
            owner_path = str(getattr(owner, "FullName", ""))
            active_path = str(getattr(document, "FullName", ""))
            if owner_path and active_path and (
                ntpath.normcase(ntpath.normpath(owner_path))
                != ntpath.normcase(ntpath.normpath(active_path))
            ):
                raise ValueError("Selected revolution axis belongs to a different document")

        value = selected.Value
        name = str(getattr(value, "Name", "<unnamed selected axis>"))
        part = self.conn.get_active_part()
        try:
            reference = selected.Reference
        except Exception:
            reference = None
        if reference is None:
            reference = part.CreateReferenceFromObject(value)
        if reference is None:
            raise RuntimeError("CATIA could not create a Reference for the selected axis")
        return reference, name, selection_type

    def _groove(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        angle = args.get("angle", 360)
        if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 < angle <= 360:
            raise ValueError("Groove angle must be finite and in (0, 360] degrees")

        groove = sf.AddNewGroove(sketch)
        groove.FirstAngle.Value = angle
        if not math.isclose(float(groove.FirstAngle.Value), angle, abs_tol=1e-7):
            raise RuntimeError("Groove was created, but CATIA did not apply the requested angle")

        part.UpdateObject(groove)
        self.conn.refresh_display()
        return f"Groove (revolution cut) created: {angle}°. Feature: '{groove.Name}'"

    def _fillet(self, args: dict[str, Any]) -> str:
        if args.get("edge_name"):
            raise ValueError(
                "Exact edge targeting by name is unsupported. Select the edge in CATIA; "
                "this server does not yet validate selected-edge fillet creation."
            )
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        radius = args["radius"]
        if not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius <= 0:
            raise ValueError("Fillet radius must be finite and positive in mm")
        edge_ref = self._selected_geometry_reference("Edge")

        fillet = sf.AddNewSolidEdgeFilletWithConstantRadius(
            edge_ref,
            1,       # catTangencyFilletEdgePropagation
            radius,
        )

        part.UpdateObject(fillet)
        self.conn.refresh_display()
        return f"Fillet created: R{radius} mm. Feature: '{fillet.Name}'"

    def _chamfer(self, args: dict[str, Any]) -> str:
        if args.get("edge_name"):
            raise ValueError("Exact edge targeting by name is unsupported")
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        length = args["length"]
        angle = args.get("angle", 45)
        if any(not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (length, angle)) or length <= 0 or not 0 < angle < 90:
            raise ValueError("Chamfer needs a positive length and an angle strictly between 0 and 90°")
        edge_ref = self._selected_geometry_reference("Edge")

        chamfer = sf.AddNewChamfer(
            edge_ref,
            1,       # catMinimalChamfer
            1,       # catLengthAngleChamfer
            0,       # orientation
            length,
            angle,
        )

        part.UpdateObject(chamfer)
        self.conn.refresh_display()
        return f"Chamfer created: {length} mm at {angle}°. Feature: '{chamfer.Name}'"

    def _hole(self, args: dict[str, Any]) -> str:
        if args.get("type", "simple") != "simple":
            raise ValueError("Only a simple hole is implemented; requested type is unsupported")
        if args.get("threaded", False):
            raise ValueError("Threaded holes need explicit thread parameters and are unsupported")
        if not args.get("sketch_name"):
            raise ValueError("A named positioning sketch with one user point is required")
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        diameter = args["diameter"]
        depth = args["depth"]
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0
               for value in (diameter, depth)):
            raise ValueError("Hole diameter and depth must be finite and positive in mm")
        geometry = sketch.GeometricElements
        point_count = 0
        for index in range(1, geometry.Count + 1):
            element = geometry.Item(index)
            if str(element.Name).lower().startswith("point."):
                point_count += 1
        if point_count != 1:
            raise ValueError(
                f"Hole positioning sketch needs exactly one identifiable user Point; "
                f"found {point_count}. Built-in sketch axes are not positioning points."
            )

        hole = sf.AddNewHoleFromSketch(sketch, depth)
        hole.Diameter.Value = diameter
        hole.BottomType = 0  # catFlatBottom
        if not math.isclose(float(hole.Diameter.Value), diameter, abs_tol=1e-7):
            raise RuntimeError("Hole was created, but its diameter did not match the request")

        part.UpdateObject(hole)
        self.conn.refresh_display()
        return f"Hole created: D{diameter} mm, depth {depth} mm. Feature: '{hole.Name}'"

    def _rect_pattern(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        if not args.get("feature_name"):
            raise ValueError("feature_name is required; the last feature is not an exact target")
        feature = self._get_last_shape(args["feature_name"])
        d1_count = args["dir1_count"]
        d1_spacing = args["dir1_spacing"]
        d2_count = args.get("dir2_count", 1)
        d2_spacing = args.get("dir2_spacing", 0)
        if any(isinstance(count, bool) or not isinstance(count, int) or count < 1
               for count in (d1_count, d2_count)):
            raise ValueError("Pattern counts must be positive integers including the source")
        if any(not isinstance(spacing, (int, float)) or not math.isfinite(spacing)
               for spacing in (d1_spacing, d2_spacing)):
            raise ValueError("Pattern spacing must be finite in mm")
        dir1_ref, dir2_ref = self._selected_support_references(("Line", "Line"))

        pattern = sf.AddNewRectPattern(
            feature,
            d1_count, d2_count,
            d1_spacing, d2_spacing,
            1, 1,
            dir1_ref, dir2_ref,
            True, True,
            0,
        )

        part.UpdateObject(pattern)
        self.conn.refresh_display()
        return (
            f"Rectangular pattern created: {d1_count}x{d2_count}, "
            f"spacing {d1_spacing}x{d2_spacing} mm. Feature: '{pattern.Name}'"
        )

    def _circ_pattern(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        if not args.get("feature_name"):
            raise ValueError("feature_name is required; the last feature is not an exact target")
        feature = self._get_last_shape(args["feature_name"])
        count = args["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 2:
            raise ValueError("Circular pattern count must be an integer >= 2")
        angular_spacing = args.get("angular_spacing")
        if angular_spacing is None:
            angular_spacing = 360.0 / count
        if not isinstance(angular_spacing, (int, float)) or not math.isfinite(angular_spacing) or angular_spacing <= 0:
            raise ValueError("Angular spacing must be finite and positive")
        center_ref, axis_ref = self._selected_support_references(("Point", "Line"))

        pattern = sf.AddNewCircPattern(
            feature,
            1, count,
            0, angular_spacing,
            1, 1,
            center_ref, axis_ref,
            True, 0,
            True,
        )

        part.UpdateObject(pattern)
        self.conn.refresh_display()
        return (
            f"Circular pattern created: {count} instances, "
            f"{angular_spacing}° spacing. Feature: '{pattern.Name}'"
        )

    def _mirror(self, args: dict[str, Any]) -> str:
        if args.get("feature_name"):
            raise ValueError(
                "Mirroring one named feature is unsupported: AddNewMirror uses the current body. "
                "Omit feature_name to operate on the active MainBody."
            )
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        plane_key = args["plane"].lower()
        planes = self.conn.get_origin_elements()
        if plane_key not in planes:
            raise ValueError(f"Unknown plane '{plane_key}'. Use 'xy', 'yz', or 'zx'.")

        mirror_plane = planes[plane_key]
        ref = part.CreateReferenceFromObject(mirror_plane)

        mirror = sf.AddNewMirror(ref)

        part.UpdateObject(mirror)
        self.conn.refresh_display()
        return f"Mirror created about {plane_key.upper()} plane. Feature: '{mirror.Name}'"

    def _shell(self, args: dict[str, Any]) -> str:
        if args.get("faces_to_remove"):
            raise ValueError("Exact face removal by name is unsupported")
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        thickness = args["thickness"]
        if not isinstance(thickness, (int, float)) or not math.isfinite(thickness) or thickness <= 0:
            raise ValueError("Shell wall thickness must be finite and positive in mm")
        face_ref = self._selected_geometry_reference("Face")
        shell = sf.AddNewShell(face_ref, thickness, 0)

        part.UpdateObject(shell)
        self.conn.refresh_display()
        return f"Shell created: {thickness} mm wall thickness. Feature: '{shell.Name}'"

    def _draft(self, args: dict[str, Any]) -> str:
        raise RuntimeError(
            "UNSUPPORTED_DRAFT: AddNewDraft needs ten arguments including exact face, "
            "neutral support, pulling vector and validated modes. The current angle/plane "
            "schema cannot specify them, so no CATIA feature was created."
        )

    def _thickness(self, args: dict[str, Any]) -> str:
        if args.get("face_name"):
            raise ValueError("Exact thickness face targeting by name is unsupported")
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        sf = part.ShapeFactory

        offset = args["offset"]
        if not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset == 0:
            raise ValueError("Thickness offset must be finite and nonzero in mm")
        face_ref = self._selected_geometry_reference("Face")
        thickness = sf.AddNewThickness(face_ref, offset)

        part.UpdateObject(thickness)
        self.conn.refresh_display()
        return f"Thickness added: {offset} mm offset. Feature: '{thickness.Name}'"

    def _list_features(self) -> str:
        self.conn.ensure_connected()
        body = self.conn.get_active_part_body()
        shapes = body.Shapes

        features = []
        for i in range(1, shapes.Count + 1):
            shape = shapes.Item(i)
            features.append({
                "index": i,
                "name": shape.Name,
                "container": body.Name,
                "category": "solid_shape",
                "type": str(shape.Type) if hasattr(shape, "Type") else None,
                "type_status": "reported_by_com" if hasattr(shape, "Type") else "unavailable",
            })

        if not features:
            return "No features in the active body"
        return json.dumps({"scope": "MainBody.Shapes only", "features": features}, indent=2)

    def _list_edges(self) -> dict[str, Any]:
        return {
            "ok": False,
            "code": "UNSUPPORTED_EXACT_TOPOLOGY",
            "message": (
                "This server cannot provide stable edge IDs from names or list indices. "
                "Select an edge in CATIA and inspect it with catia_get_selection. "
                "Exact edge-consuming COM operations need a live Windows validation."
            ),
        }
