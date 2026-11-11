"""One validated Hole option contract shared by every Hole constructor path.

Enum values are taken from the cached CAA V5 PartInterfaces reference:
CatHoleType, CatCSHoleMode, CatHoleBottomType and CatLimitMode. Validation
happens before any constructor runs, so a rejected option never leaves a
half-configured Hole behind. Live Windows geometry is still not proven here.
"""
from __future__ import annotations

import math

from catia_mcp.runtime import CADOperationError

HOLE_TYPES = {"simple": 0, "counterbored": 2, "countersunk": 3, "counterdrilled": 4}
LIMITS = {"blind": 0, "up_to_next": 1, "up_to_last": 2}
BOTTOMS = {"flat": 0, "v": 1}
# CatCSHoleMode: which two of depth/diameter/angle drive a countersink.
COUNTERSINK_MODES = {frozenset({"head_depth_mm", "head_angle_deg"}): 0,
                     frozenset({"head_depth_mm", "head_diameter_mm"}): 1,
                     frozenset({"head_angle_deg", "head_diameter_mm"}): 2}
HEAD_FIELDS = ("head_diameter_mm", "head_depth_mm", "head_angle_deg")
REQUIRED_HEAD = {"simple": set(), "counterbored": {"head_diameter_mm", "head_depth_mm"},
                 "counterdrilled": {"head_diameter_mm", "head_depth_mm", "head_angle_deg"}}

POSITIVE = {"type": "number", "exclusiveMinimum": 0}
OPTION_PROPERTIES = {
    "hole_type": {"enum": list(HOLE_TYPES), "default": "simple",
                  "description": "counterbored: head diameter+depth; countersunk: exactly two of head diameter/depth/angle; counterdrilled: all three"},
    "head_diameter_mm": POSITIVE, "head_depth_mm": POSITIVE,
    "head_angle_deg": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 180},
    "limit": {"enum": list(LIMITS), "default": "blind",
              "description": "blind uses depth; up_to_next/up_to_last are through holes and CATIA ignores depth"},
    "bottom": {"enum": list(BOTTOMS), "default": "flat", "description": "Blind-hole bottom shape"},
    "bottom_angle_deg": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 180,
                         "description": "Drill-point angle, only with bottom=v"},
    "reverse_direction": {"type": "boolean", "default": False,
                          "description": "Call Hole.Reverse once after creation (drill to the other side)"},
}


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise CADOperationError("INVALID_ARGUMENT", f"{name} must be finite and positive")
    return float(value)


def normalize(args: dict, diameter_mm, depth_mm) -> dict:
    """Return a complete, consistent option set or raise before CAD mutation."""
    spec = {"hole_type": args.get("hole_type", "simple"), "limit": args.get("limit", "blind"),
            "bottom": args.get("bottom", "flat"), "reverse_direction": bool(args.get("reverse_direction", False)),
            "diameter_mm": _number(diameter_mm, "Hole diameter"), "depth_mm": _number(depth_mm, "Hole depth")}
    if spec["hole_type"] not in HOLE_TYPES or spec["limit"] not in LIMITS or spec["bottom"] not in BOTTOMS:
        raise CADOperationError("INVALID_ARGUMENT", "Unsupported hole_type, limit or bottom")
    head = {key: _number(args[key], key) for key in HEAD_FIELDS if key in args}
    supplied = set(head)
    if spec["hole_type"] == "countersunk":
        if frozenset(supplied) not in COUNTERSINK_MODES:
            raise CADOperationError("INVALID_ARGUMENT", "countersunk requires exactly two of head_diameter_mm, head_depth_mm, head_angle_deg")
        spec["countersink_mode"] = COUNTERSINK_MODES[frozenset(supplied)]
    elif supplied != REQUIRED_HEAD[spec["hole_type"]]:
        raise CADOperationError("INVALID_ARGUMENT", f"{spec['hole_type']} requires exactly these head fields: {sorted(REQUIRED_HEAD[spec['hole_type']])}")
    if "head_angle_deg" in head and not head["head_angle_deg"] < 180:
        raise CADOperationError("INVALID_ARGUMENT", "head_angle_deg must be below 180")
    if "head_diameter_mm" in head and head["head_diameter_mm"] <= spec["diameter_mm"]:
        raise CADOperationError("INVALID_ARGUMENT", "Head diameter must exceed the bore diameter")
    if "head_depth_mm" in head and spec["limit"] == "blind" and head["head_depth_mm"] >= spec["depth_mm"]:
        raise CADOperationError("INVALID_ARGUMENT", "Head depth must be less than the blind bore depth")
    if spec["bottom"] == "v":
        if spec["limit"] != "blind":
            raise CADOperationError("INVALID_ARGUMENT", "A V bottom only applies to a blind hole")
        spec["bottom_angle_deg"] = _number(args.get("bottom_angle_deg", 118), "bottom_angle_deg")
        if not spec["bottom_angle_deg"] < 180:
            raise CADOperationError("INVALID_ARGUMENT", "bottom_angle_deg must be below 180")
    elif "bottom_angle_deg" in args:
        raise CADOperationError("INVALID_ARGUMENT", "bottom_angle_deg requires bottom=v")
    spec.update(head)
    return spec


def apply(hole, spec: dict) -> None:
    """Configure a just-created Hole. Type precedes its head parameters."""
    hole.Type = HOLE_TYPES[spec["hole_type"]]
    if "countersink_mode" in spec:
        # Without this, CATIA keeps Depth&Angle and silently ignores a diameter.
        hole.CounterSunkMode = spec["countersink_mode"]
    for key, attribute, unit in (("head_diameter_mm", "HeadDiameter", "mm"),
                                 ("head_depth_mm", "HeadDepth", "mm"),
                                 ("head_angle_deg", "HeadAngle", "deg")):
        if key in spec:
            getattr(hole, attribute).ValuateFromString(f"{spec[key]:.15g}{unit}")
    hole.BottomType = BOTTOMS[spec["bottom"]]
    if spec["bottom"] == "v":
        hole.BottomAngle.ValuateFromString(f"{spec['bottom_angle_deg']:.15g}deg")
    hole.BottomLimit.LimitMode = LIMITS[spec["limit"]]
    hole.Diameter.ValuateFromString(f"{spec['diameter_mm']:.15g}mm")
    if spec["reverse_direction"]:
        hole.Reverse()


def readback(hole, spec: dict) -> dict:
    """Read native values back; mismatches are failures, not warnings."""
    data = {"type": int(hole.Type), "bottom_type": int(hole.BottomType),
            "limit_mode": int(hole.BottomLimit.LimitMode), "diameter": str(hole.Diameter.ValueAsString())}
    for key, attribute in (("head_diameter_mm", "HeadDiameter"), ("head_depth_mm", "HeadDepth"),
                           ("head_angle_deg", "HeadAngle")):
        if key in spec:
            data[key.removesuffix("_mm").removesuffix("_deg")] = str(getattr(hole, attribute).ValueAsString())
    if data["type"] != HOLE_TYPES[spec["hole_type"]] or data["limit_mode"] != LIMITS[spec["limit"]] \
            or data["bottom_type"] != BOTTOMS[spec["bottom"]]:
        raise CADOperationError("POSTCONDITION_FAILED", f"Hole option readback differs: {data}")
    if not math.isclose(float(hole.Diameter.Value), spec["diameter_mm"], abs_tol=1e-6):
        raise CADOperationError("POSTCONDITION_FAILED", "Hole was created, but its diameter readback differs")
    return data


def extend_group_schema(definition: dict, modes) -> dict:
    """Make the shared options optional on the given modes of a group() tool."""
    definition["inputSchema"]["properties"].update(OPTION_PROPERTIES)
    for variant in definition["inputSchema"]["oneOf"]:
        if variant["properties"]["mode"]["const"] in modes:
            variant["propertyNames"]["enum"] = sorted(set(variant["propertyNames"]["enum"]) | set(OPTION_PROPERTIES))
    return definition
