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
from catia_mcp.runtime import CADOperationError


class PartDesignTools:
    """Tools for 3D Part Design features in CATIA V5."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        definitions = [
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
                        "axis_geometry_index": {"type": "integer", "minimum": 1,
                            "description": "Fresh Line2D index in this sketch; explicitly marks it Construction and CenterLine"},
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
                                "When true, require exactly one currently selected straight axis/line. "
                                "When false, require a construction Sketch.CenterLine, optionally "
                                "assigned via axis_geometry_index."
                            ),
                            "default": False,
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
                        "axis_from_selection": {"type": "boolean", "default": False},
                        "axis_geometry_index": {"type": "integer", "minimum": 1},
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
                    "Create a simple, counterbored or countersunk flat-bottom Hole from a positioning sketch "
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
                                "Head dimensions are mandatory for counterbored/countersunk modes"
                            ),
                            "enum": ["simple", "counterbored", "countersunk"],
                            "default": "simple",
                        },
                        "threaded": {
                            "type": "boolean",
                            "description": "Whether to add threading (default: false)",
                            "default": False,
                        },
                        "head_diameter": {"type": "number", "exclusiveMinimum": 0},
                        "head_depth": {"type": "number", "exclusiveMinimum": 0},
                        "head_angle": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 180},
                        "sketch_name": {
                            "type": "string",
                            "description": "Sketch containing the hole center point",
                        },
                    },
                    "required": ["diameter", "depth"],
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

        for definition in definitions:
            properties = definition["inputSchema"]["properties"]
            if definition["name"] == "catia_draft":
                definition["description"] = "Standard Draft with explicit face, neutral and parting References and a Part-frame pulling vector. No guessed supports or DraftDomains.Add."
                properties.clear()
                properties.update({
                    "face_handle": {"type": "string"}, "neutral_handle": {"type": "string"},
                    "parting_handle": {"type": "string"},
                    "pulling_direction": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "frame_id": {"const": "part"},
                    "angle": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 90},
                    "neutral_propagation": {"enum": ["none", "smooth"], "default": "none"},
                })
                definition["inputSchema"]["required"] = ["face_handle", "neutral_handle", "parting_handle", "pulling_direction", "frame_id", "angle"]
            if definition["name"] in {"catia_pad", "catia_pocket"}:
                properties["limit_mode"] = {"enum": ["dimension", "up_to_next", "up_to_last", "up_to_plane", "up_to_surface"], "default": "dimension"}
                properties["limit_handle"] = {"type": "string"}
                length_key = "height" if definition["name"] == "catia_pad" else "depth"
                definition["inputSchema"]["required"] = []
                properties[length_key]["description"] += "; required only for dimension mode"
            if definition["name"] not in {"catia_list_features", "catia_list_edges"}:
                properties["body_handle"] = {"type": "string", "minLength": 1}
            if "sketch_name" in properties:
                properties["sketch_handle"] = {"type": "string", "minLength": 1}
            if definition["name"] in {"catia_fillet", "catia_chamfer", "catia_shell", "catia_thickness"}:
                properties["selection_handle"] = {"type": "string", "minLength": 1}
        return definitions

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str | dict[str, Any]:
        self._arguments = arguments
        if arguments.get("body_handle"):
            self.conn.operation_body = self.conn.session.resolve(arguments["body_handle"], {"body"}).value
        if tool_name not in {"catia_list_features", "catia_list_edges"}:
            self.conn.get_active_part().InWorkObject = self.conn.get_active_part_body()
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
        handle = getattr(self, "_arguments", {}).get("sketch_handle")
        if handle:
            if sketch_name:
                raise ValueError("Choose sketch_handle OR sketch_name")
            sketch = self.conn.session.resolve(handle, {"sketch"}).value
            from catia_mcp.runtime import same_object
            if not any(same_object(sketches.Item(i), sketch) for i in range(1, sketches.Count + 1)):
                raise ValueError("Sketch must belong to the target body")
            return sketch

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
        handle = getattr(self, "_arguments", {}).get("selection_handle")
        if handle:
            return self.conn.session.reference(handle, {expected.lower()})
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
        raise CADOperationError("STALE_REFERENCE", "Selected BRep Reference unavailable; refusing to substitute its parent feature")

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
        mode, limit_reference, height = self._limit_arguments(args, "height")
        direction = args.get("direction", "normal")
        symmetric = args.get("symmetric", False)

        if isinstance(height, bool) or not math.isfinite(height) or height <= 0:
            raise ValueError("Pad height must be finite and positive in mm")
        if symmetric and direction == "reverse":
            raise ValueError("Symmetric and reverse are incompatible")
        part.InWorkObject = body
        symmetric = symmetric or direction == "both"
        pad = sf.AddNewPad(sketch, height / 2 if symmetric else height)
        self._created(pad)
        self._apply_limit(pad, mode, limit_reference)

        if symmetric:
            pad.IsSymmetric = True
        elif direction == "reverse":
            pad.DirectionOrientation = 1  # catReverse
        elif direction == "both":
            pad.IsSymmetric = True

        self._updated(part, pad)
        self.conn.refresh_display()
        return f"Pad created: limit={args.get('limit_mode', 'dimension')}, requested height={args.get('height')} mm ({direction}). Feature: '{pad.Name}'"

    def _pocket(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        mode, limit_reference, depth = self._limit_arguments(args, "depth")

        if isinstance(depth, bool) or not math.isfinite(depth) or depth <= 0:
            raise ValueError("Pocket depth must be finite and positive in mm")
        before = self._volume(part, body)
        part.InWorkObject = body
        pocket = sf.AddNewPocket(sketch, depth)
        self._created(pocket)
        self._apply_limit(pocket, mode, limit_reference)

        if args.get("direction") == "reverse":
            pocket.DirectionOrientation = 1

        self._updated(part, pocket)
        after = self._volume(part, body)
        if before is not None and after is not None and not after < before - max(abs(before) * 1e-10, 1e-15):
            raise CADOperationError("POSTCONDITION_FAILED", f"Pocket {pocket.Name!r} exists but removed no measurable material: {before} -> {after} m^3; inspect direction/intersection")
        self.conn.refresh_display()
        return f"Pocket created: limit={args.get('limit_mode', 'dimension')}, requested depth={args.get('depth')} mm. Feature: '{pocket.Name}'. Volume m^3: {before} -> {after}; None means unverified"

    def _created(self, obj):
        state = getattr(self.conn, "session", None)
        if state is not None:
            state.mark_created(obj, "feature")

    def _limit_arguments(self, args, length_key):
        mode = args.get("limit_mode", "dimension")
        codes = {"dimension": 0, "up_to_next": 1, "up_to_last": 2,
                 "up_to_plane": 3, "up_to_surface": 4}
        if mode not in codes:
            raise ValueError("Unsupported prism limit")
        reference = None
        if mode == "dimension":
            if length_key not in args or "limit_handle" in args:
                raise ValueError(f"Dimension limit needs {length_key} and no limit_handle")
            length = args[length_key]
        else:
            if length_key in args or args.get("symmetric") or args.get("direction") == "both":
                raise ValueError("Non-dimensional limits reject length/symmetric extent")
            length = 1.0  # constructor seed only; final extent is the explicit limit
            if mode in {"up_to_plane", "up_to_surface"}:
                if not args.get("limit_handle"):
                    raise ValueError("This limit needs limit_handle")
                reference = self.conn.session.reference(args["limit_handle"], {"plane"} if mode == "up_to_plane" else {"surface", "face"})
            elif "limit_handle" in args:
                raise ValueError("Next/last limit does not accept a support")
        return codes[mode], reference, length

    @staticmethod
    def _apply_limit(feature, mode, reference):
        feature.FirstLimit.LimitMode = mode
        if reference is not None:
            feature.FirstLimit.LimitingElement = reference
        if int(feature.FirstLimit.LimitMode) != mode:
            raise CADOperationError("POSTCONDITION_FAILED", "Prism limit mode readback differs")

    def _updated(self, part, obj):
        try:
            part.UpdateObject(obj)
            part.Update()
        except Exception as exc:
            raise CADOperationError("UPDATE_FAILED", f"Feature {obj.Name!r} exists; update failed: {exc}") from exc
        if not part.IsUpToDate(obj):
            raise CADOperationError("POSTCONDITION_FAILED", f"Feature {obj.Name!r} is not up to date")
        state = getattr(self.conn, "session", None)
        if state is not None:
            state.updated = True

    def _volume(self, part, body):
        try:
            reference = part.CreateReferenceFromObject(body)
            return float(self.conn.active_document.GetWorkbench("SPAWorkbench").GetMeasurable(reference).Volume)
        except Exception:
            return None

    def _prepare_revolution_axis(self, sketch, args):
        index = args.get("axis_geometry_index")
        if index is not None:
            if args.get("axis_from_selection", False):
                raise ValueError("Choose sketch axis index OR current selection, not both")
            geometry = sketch.GeometricElements
            if not 1 <= index <= geometry.Count:
                raise ValueError("Axis index is out of range; reread sketch geometry")
            line = geometry.Item(index)
            if int(line.GeometricType) != 3:
                raise ValueError("Revolution axis must be a Line2D")
            sketch.OpenEdition()
            try:
                line.Construction = True
                sketch.CenterLine = line
            finally:
                sketch.CloseEdition()
            self.conn.get_active_part().UpdateObject(sketch)
        if args.get("axis_from_selection", False):
            return self._selected_axis_reference(required=True)
        try:
            line = sketch.CenterLine
            if line is None or not bool(line.Construction):
                raise ValueError("CenterLine must be construction geometry")
            return (self.conn.get_active_part().CreateReferenceFromObject(line), str(line.Name), "Line2D")
        except Exception as exc:
            raise ValueError("Sketch has no verified construction CenterLine. Use catia_sketch_line(as_axis=true) or axis_geometry_index before Shaft/Groove") from exc

    def _shaft(self, args: dict[str, Any]) -> str:
        self.conn.ensure_connected()
        part = self.conn.get_active_part()
        body = self.conn.get_active_part_body()
        sf = part.ShapeFactory

        sketch = self._get_last_sketch(args.get("sketch_name"))
        angle = args.get("angle", 360)
        if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 < angle <= 360:
            raise ValueError("Shaft angle must be finite and in (0, 360] degrees")

        use_selection = args.get("axis_from_selection", False)
        if not isinstance(use_selection, bool):
            raise ValueError("axis_from_selection must be a boolean")
        axis_info = self._prepare_revolution_axis(sketch, args)
        part.InWorkObject = body

        try:
            shaft = sf.AddNewShaft(sketch)
            self._created(shaft)
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
        shaft.FirstAngle.ValuateFromString(f"{angle}deg")
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
            if normalized_type.endswith("edge"):
                raise CADOperationError("STALE_REFERENCE", "Exact edge Reference unavailable; parent feature cannot replace an axis edge")
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

        axis_reference, _, _ = self._prepare_revolution_axis(sketch, args)
        part.InWorkObject = body
        groove = sf.AddNewGroove(sketch)
        self._created(groove)
        groove.RevoluteAxis = axis_reference
        groove.FirstAngle.ValuateFromString(f"{angle}deg")
        if not math.isclose(float(groove.FirstAngle.Value), angle, abs_tol=1e-7):
            raise RuntimeError("Groove was created, but CATIA did not apply the requested angle")

        self._updated(part, groove)
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

        self._created(fillet)
        self._updated(part, fillet)
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

        self._created(chamfer)
        self._updated(part, chamfer)
        self.conn.refresh_display()
        return f"Chamfer created: {length} mm at {angle}°. Feature: '{chamfer.Name}'"

    def _hole(self, args: dict[str, Any]) -> str:
        hole_type = args.get("type", "simple")
        codes = {"simple": 0, "counterbored": 2, "countersunk": 3}
        if hole_type not in codes:
            raise ValueError("Unsupported hole type")
        expected_head = {"simple": set(), "counterbored": {"head_diameter", "head_depth"},
                         "countersunk": {"head_diameter", "head_angle"}}[hole_type]
        supplied_head = {k for k in ("head_diameter", "head_depth", "head_angle") if k in args}
        if supplied_head != expected_head:
            raise ValueError(f"{hole_type} requires exactly these head fields: {sorted(expected_head)}")
        if expected_head and args["head_diameter"] <= args["diameter"]:
            raise ValueError("Head diameter must exceed the bore diameter")
        if hole_type == "counterbored" and args["head_depth"] >= args["depth"]:
            raise ValueError("Counterbore head depth must be less than bore depth")
        if args.get("threaded", False):
            raise ValueError("Threaded holes need explicit thread parameters and are unsupported")
        if not args.get("sketch_name") and not args.get("sketch_handle"):
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
            if int(element.GeometricType) == 2 and not bool(element.Construction):
                point_count += 1
        if point_count != 1:
            raise ValueError(
                f"Hole positioning sketch needs exactly one identifiable user Point; "
                f"found {point_count}. Built-in sketch axes are not positioning points."
            )

        before = self._volume(part, self.conn.get_active_part_body())
        hole = sf.AddNewHoleFromSketch(sketch, depth)
        self._created(hole)
        hole.Type = codes[hole_type]
        hole.Diameter.ValuateFromString(f"{diameter}mm")
        if expected_head:
            hole.HeadDiameter.ValuateFromString(f"{args['head_diameter']}mm")
        if hole_type == "counterbored":
            hole.HeadDepth.ValuateFromString(f"{args['head_depth']}mm")
        if hole_type == "countersunk":
            hole.HeadAngle.ValuateFromString(f"{args['head_angle']}deg")
        hole.BottomType = 0  # catFlatBottom
        if not math.isclose(float(hole.Diameter.Value), diameter, abs_tol=1e-7):
            raise RuntimeError("Hole was created, but its diameter did not match the request")

        self._updated(part, hole)
        after = self._volume(part, self.conn.get_active_part_body())
        if before is not None and after is not None and after >= before:
            raise CADOperationError("POSTCONDITION_FAILED", "Hole updated but did not remove material; inspect the existing feature before retrying")
        self.conn.refresh_display()
        return f"{hole_type} Hole: D{diameter} mm, depth {depth} mm. Feature: '{hole.Name}'; volume m^3 {before} -> {after} (None=unverified)"

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

        self._created(pattern)
        self._updated(part, pattern)
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

        self._created(pattern)
        self._updated(part, pattern)
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

        self._created(mirror)
        self._updated(part, mirror)
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

        self._created(shell)
        self._updated(part, shell)
        self.conn.refresh_display()
        return f"Shell created: {thickness} mm wall thickness. Feature: '{shell.Name}'"

    def _draft(self, args: dict[str, Any]) -> str:
        state = self.conn.session
        face = state.reference(args["face_handle"], {"face"})
        neutral = state.reference(args["neutral_handle"], {"face", "plane"})
        parting = state.reference(args["parting_handle"], {"face", "plane"})
        direction = args["pulling_direction"]
        norm = math.sqrt(sum(v*v for v in direction))
        if not math.isfinite(norm) or norm == 0:
            raise ValueError("Draft pulling vector must be finite and nonzero")
        direction = [v/norm for v in direction]
        part = self.conn.get_active_part()
        draft = part.ShapeFactory.AddNewDraft(face, neutral,
            1 if args.get("neutral_propagation") == "smooth" else 0,
            parting, *direction, 0, args["angle"], 0)
        self._created(draft)
        self._updated(part, draft)
        return f"Standard Draft {draft.Name!r} updated; exact face geometry requires Windows verification"

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

        self._created(thickness)
        self._updated(part, thickness)
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
