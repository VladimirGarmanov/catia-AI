"""Shared CAA pattern contracts; native parameter checks are not BRep validation."""
from __future__ import annotations

import math

from catia_mcp.runtime import CADOperationError, same_object


LINEAR_SUPPORT = {"line", "line2d", "edge", "plane", "face"}
CENTER_SUPPORT = {"point", "point2d", "vertex"}
NONNEGATIVE_SPACING = {"type": "number", "minimum": 0,
                       "description": "mm; zero is allowed only for a one-instance direction"}


def require_body_seed(body, seed):
    if not any(same_object(seed, body.Shapes.Item(i)) for i in range(1, body.Shapes.Count + 1)):
        raise CADOperationError("INVALID_ARGUMENT", "Pattern seed must belong to the explicitly targeted Body")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CADOperationError("INVALID_ARGUMENT", f"{label} must be finite")
    return value


def validate_pattern(mode, args):
    """Validate before changing InWorkObject or constructing any feature."""
    keys = ("first", "second") if mode == "rectangular_pattern" else ("radial", "angular")
    total = 1
    for key in keys:
        count, position = args[f"{key}_count"], args[f"{key}_seed_position"]
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 1000:
            raise CADOperationError("INVALID_ARGUMENT", f"{key}_count must be an integer in [1,1000], including the source")
        if isinstance(position, bool) or not isinstance(position, int) or not 1 <= position <= count:
            raise CADOperationError("INVALID_ARGUMENT", f"{key} seed position must be in [1,count]")
        spacing_key = f"{key}_spacing_" + ("deg" if key == "angular" else "mm")
        spacing = _number(args[spacing_key], spacing_key)
        crown = key == "angular" and args.get("complete_crown", False)
        if spacing < 0 or (count > 1 and spacing == 0 and not crown):
            raise CADOperationError("INVALID_ARGUMENT", f"{spacing_key} must be positive for multiple instances; use orientation flags to reverse")
        total *= count
    if not 2 <= total <= 10000:
        raise CADOperationError("INVALID_ARGUMENT", "Pattern must contain 2..10000 instances including the source")
    _number(args["rotation_deg"], "rotation_deg")
    if mode == "circular_pattern" and not args.get("complete_crown", False):
        if args["angular_spacing_deg"] * (args["angular_count"] - 1) >= 360:
            raise CADOperationError("INVALID_ARGUMENT", "Angular span must be less than 360 degrees; a closed ring uses 360/count spacing")


def configure_pattern(obj, mode, args):
    """Do not inherit a user's last unequal-spacing/complete-crown setting."""
    if mode == "rectangular_pattern":
        obj.FirstRectangularPatternParameters = 0  # catInstancesandSpacing
        obj.SecondRectangularPatternParameters = 0
        rows = (("First", "first"), ("Second", "second"))
        for native, key in rows:
            repartition = getattr(obj, native + "DirectionRepartition")
            repartition.InstancesCount.Value = args[key + "_count"]
            if args[key + "_count"] > 1:
                repartition.Spacing.ValuateFromString(f"{args[key + '_spacing_mm']:.15g}mm")
    else:
        obj.CircularPatternParameters = int(args.get("complete_crown", False))
        obj.RadialRepartition.InstancesCount.Value = args["radial_count"]
        obj.AngularRepartition.InstancesCount.Value = args["angular_count"]
        if args["radial_count"] > 1:
            obj.RadialRepartition.Spacing.ValuateFromString(f"{args['radial_spacing_mm']:.15g}mm")
        if args["angular_count"] > 1 and not args.get("complete_crown", False):
            obj.AngularRepartition.AngularSpacing.ValuateFromString(f"{args['angular_spacing_deg']:.15g}deg")


def read_pattern(obj, mode, args):
    """Read actual values after Update; never report requested counts as evidence.

    CAA RealParam.Value uses mm for Length and decimal degrees for Angle.
    CircPattern.RadialAlignment has wording inconsistent with the constructor;
    report it raw, without claiming that it verifies keep_parallel geometry.
    """
    actual = {}

    def check(key, value, wanted):
        actual[key] = value
        if isinstance(wanted, bool):
            matches = isinstance(value, bool) and value == wanted
        else:
            matches = (not isinstance(value, bool) and isinstance(value, (int, float))
                       and math.isfinite(value) and math.isclose(value, wanted, rel_tol=1e-9, abs_tol=1e-7))
        if not matches:
            raise CADOperationError("POSTCONDITION_FAILED", f"Created pattern {key}: requested {wanted}, read {value}; inspect before retrying")

    try:
        if mode == "rectangular_pattern":
            for native, key in (("First", "first"), ("Second", "second")):
                repartition = getattr(obj, native + "DirectionRepartition")
                check(key + "_count", repartition.InstancesCount.Value, args[key + "_count"])
                check(key + "_mode", getattr(obj, native + "RectangularPatternParameters"), 0)
                check(key + "_seed_position", getattr(obj, native + "DirectionRow").Value, args[key + "_seed_position"])
                check(key + "_forward", getattr(obj, native + "Orientation"), args[key + "_forward"])
                if args[key + "_count"] > 1:
                    check(key + "_spacing_mm", repartition.Spacing.Value, args[key + "_spacing_mm"])
        else:
            check("circular_mode", obj.CircularPatternParameters, int(args.get("complete_crown", False)))
            for native, key in (("Radial", "radial"), ("Angular", "angular")):
                repartition = getattr(obj, native + "Repartition")
                check(key + "_count", repartition.InstancesCount.Value, args[key + "_count"])
                check(key + "_seed_position", getattr(obj, native + "DirectionRow").Value, args[key + "_seed_position"])
            if args["radial_count"] > 1:
                check("radial_spacing_mm", obj.RadialRepartition.Spacing.Value, args["radial_spacing_mm"])
            if args["angular_count"] > 1:
                spacing = 360 / args["angular_count"] if args.get("complete_crown", False) else args["angular_spacing_deg"]
                check("angular_spacing_deg", obj.AngularRepartition.AngularSpacing.Value, spacing)
            check("axis_forward", obj.RotationOrientation, args["axis_forward"])
            actual["native_radial_alignment"] = bool(obj.RadialAlignment)
        check("rotation_deg", obj.RotationAngle.Value, args["rotation_deg"])
    except CADOperationError:
        raise
    except Exception as exc:
        raise CADOperationError("POSTCONDITION_UNAVAILABLE", f"Pattern exists but native parameter readback failed: {exc}; inspect before retrying") from exc
    actual["total_instances_including_source"] = (actual.get("first_count", actual.get("radial_count"))
                                                 * actual.get("second_count", actual.get("angular_count")))
    return {"parameters": actual, "parameter_readback_verified": True,
            "geometry_verified": False,
            "verification_limits": "Counts describe the native repartition, not measured BRep copies; direction geometry, overlap and orientation need Windows inspection"}


def read_user_pattern(obj, anchor, positions, instances):
    try:
        if not same_object(obj.AnchorPoint, anchor):
            raise CADOperationError("POSTCONDITION_FAILED", "User pattern anchor differs after Update; inspect before retrying")
    except CADOperationError:
        raise
    except Exception as exc:
        raise CADOperationError("POSTCONDITION_UNAVAILABLE", f"User pattern anchor readback failed: {exc}") from exc
    # CAA declares this as AnyObject, not a guaranteed enumerable collection.
    positions_verified = False
    try:
        located = obj.FeatureToLocatePositions
        if same_object(located, positions):
            positions_verified = True
        else:
            count = located.Count
            if isinstance(count, int):
                positions_verified = any(same_object(located.Item(i), positions) for i in range(1, count + 1))
                if not positions_verified:
                    raise CADOperationError("POSTCONDITION_FAILED", "User pattern positioning sketch missing after Update")
    except CADOperationError:
        raise
    except Exception:
        pass
    return {"anchor_verified": True, "positions_verified": positions_verified,
            "requested_instances": instances, "actual_instances": None, "geometry_verified": False,
            "verification_limits": "UserPattern exposes no documented InstancesCount; actual copies/placement require Windows inspection"}
