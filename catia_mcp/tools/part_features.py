"""Dedicated Part Design Thread/Tap with ISO metric sizes and native readback.

CAA ShapeFactory.AddNewThreadWithRef(lateral face, limit face) creates a thread
SPECIFICATION (cosmetic, drawable), not helical teeth. CatThreadPolarity
{catThread, catTap}, CatThreadSide {catRightSide, catLeftSide}. Diameter, pitch and
depth are written explicitly from the ISO 261/262 coarse table or a fine "MdxP"
designation, then read back. The lateral face radius is measured by SPA and a
size that does not fit the face is reported (thread: face Ø ≈ D; tap: minor Ø..D).
"""
import re

from catia_mcp.runtime import CADOperationError
from catia_mcp.tools.engineering import HANDLE, POSITIVE, dimension
from catia_mcp.tools.operations import BOOL, OperationTools, group, optional_fields

# ISO 261/262 coarse pitches (mm).
COARSE = {1: .25, 1.2: .25, 1.6: .35, 2: .4, 2.5: .45, 3: .5, 3.5: .6, 4: .7, 5: .8, 6: 1, 7: 1, 8: 1.25,
          10: 1.5, 12: 1.75, 14: 2, 16: 2, 18: 2.5, 20: 2.5, 22: 2.5, 24: 3, 27: 3, 30: 3.5, 33: 3.5,
          36: 4, 39: 4, 42: 4.5, 45: 4.5, 48: 5, 52: 5, 56: 5.5, 60: 5.5, 64: 6}
DESIGNATION = re.compile(r"^M(\d+(?:\.\d+)?)(?:[xX](\d+(?:\.\d+)?))?$")


def metric(designation):
    match = DESIGNATION.match(designation.strip())
    if not match:
        raise CADOperationError("INVALID_ARGUMENT", "Designation must look like M10 (coarse) or M10x1.25 (fine)")
    diameter = float(match.group(1))
    if match.group(2):
        pitch = float(match.group(2))
        if not 0 < pitch < diameter / 2:
            raise CADOperationError("INVALID_ARGUMENT", "Fine pitch must be positive and well below the diameter")
        return diameter, pitch, "fine"
    key = int(diameter) if diameter.is_integer() else diameter
    if key not in COARSE:
        raise CADOperationError("INVALID_ARGUMENT", f"M{match.group(1)} has no ISO coarse pitch here; give MdxP explicitly")
    return diameter, COARSE[key], "coarse"


class PartFeatureTools(OperationTools):
    def get_tool_definitions(self):
        common = {"body_handle": HANDLE, "lateral_face_handle": HANDLE, "limit_face_handle": HANDLE,
                  "depth_mm": POSITIVE, "polarity": {"enum": ["thread", "tap"]}, "hand": {"enum": ["right", "left"]}}
        definition = group("catia_thread",
            "Part Design Thread/Tap on an exact cylindrical lateral face (shaft = thread, hole = tap) starting from an exact "
            "planar limit face, both fresh selection handles, in an explicit Body. metric: ISO designation M10 (coarse pitch "
            "from ISO 261) or M10x1.25 (fine). custom: diameter_mm and pitch_mm. Writes diameter, pitch, depth, polarity and "
            "hand, optional reverse, Updates, reads them back and measures the face diameter: a size that does not fit is "
            "WRONG_GEOMETRY_EFFECT with the feature left behind. It is a thread specification (shown in drawings), not "
            "modeled helical teeth. For threaded holes catia_hole/catia_feature_options hole_thread also exist.", {
                "metric": {"designation": {"type": "string", "minLength": 2, "maxLength": 16}},
                "custom": {"diameter_mm": POSITIVE, "pitch_mm": POSITIVE},
            }, common)
        return [optional_fields(definition, common={"reverse": BOOL})]

    def execute(self, name, a):
        if self.engineering.sketcher._active_sketch is not None:
            raise CADOperationError("INVALID_ARGUMENT", "Close sketch edition before 3D operations")
        if a["mode"] == "metric":
            diameter, pitch, series = metric(a["designation"])
        else:
            diameter, pitch, series = a["diameter_mm"], a["pitch_mm"], "custom"
            if pitch >= diameter / 2:
                raise CADOperationError("INVALID_ARGUMENT", "Pitch must be well below the diameter")
        lateral = self.ref(a["lateral_face_handle"], {"face"})
        limit = self.ref(a["limit_face_handle"], {"face"})
        if a["lateral_face_handle"] == a["limit_face_handle"]:
            raise CADOperationError("INVALID_ARGUMENT", "Lateral and limit faces must differ")
        face_diameter = self._face_diameter(lateral)  # measured before any write
        part = self.conn.get_active_part()
        self.engineering.body(a["body_handle"])
        try:
            obj = part.ShapeFactory.AddNewThreadWithRef(lateral, limit)
        except Exception as exc:
            raise CADOperationError("CAPABILITY_UNAVAILABLE", f"AddNewThreadWithRef failed: {exc}") from exc
        self.state.mark_created(obj, "feature")
        obj.SetExplicitPolarity({"thread": 0, "tap": 1}[a["polarity"]])
        obj.Side = {"right": 0, "left": 1}[a["hand"]]
        dimension(obj.Diameter, diameter, "mm")
        dimension(obj.Pitch, pitch, "mm")
        dimension(obj.Depth, a["depth_mm"], "mm")
        if a.get("reverse"):
            obj.ReverseDirection()
        result = self.engineering.finish(obj, "feature", {})
        native = {"diameter_mm": float(obj.Diameter.Value), "pitch_mm": float(obj.Pitch.Value),
                  "depth_mm": float(obj.Depth.Value), "side": int(obj.Side)}
        for key, expected in (("diameter_mm", diameter), ("pitch_mm", pitch), ("depth_mm", a["depth_mm"])):
            if abs(native[key] - expected) > 1e-6:
                raise CADOperationError("POSTCONDITION_FAILED",
                    f"Thread {result['handle']} {key} reads {native[key]}, expected {expected}; feature left behind")
        if native["side"] != {"right": 0, "left": 1}[a["hand"]]:
            raise CADOperationError("POSTCONDITION_FAILED", f"Thread {result['handle']} hand readback differs")
        fit = "unverified"
        if face_diameter is not None:
            if a["polarity"] == "thread":
                ok = abs(face_diameter - diameter) <= max(0.02 * diameter, 0.05)
            else:
                minor = diameter - 1.0825 * pitch
                ok = minor - 0.05 * diameter <= face_diameter <= diameter + 0.01
            if not ok:
                raise CADOperationError("WRONG_GEOMETRY_EFFECT",
                    f"{a['polarity']} M{diameter:g}x{pitch:g} does not fit the measured face Ø{face_diameter:.3f} mm; "
                    f"thread {result['handle']} was left behind, inspect it")
            fit = "passed"
        return {**result, "series": series, "requested": {"diameter_mm": diameter, "pitch_mm": pitch,
                "depth_mm": a["depth_mm"], "polarity": a["polarity"], "hand": a["hand"]},
                "native": native, "measured_face_diameter_mm": face_diameter, "fit_check": fit,
                "warning": "Thread specification, not helical geometry; verify direction/limit visually on Windows"}

    def _face_diameter(self, reference):
        try:
            measurable = self.conn.active_document.GetWorkbench("SPAWorkbench").GetMeasurable(reference)
            if int(measurable.GeometryName) != 4:  # CatMeasurableCylinder
                raise CADOperationError("WRONG_GEOMETRY_TYPE", "Thread lateral face must measure as a cylinder")
            value = 2 * float(measurable.Radius)
            # SPA lengths are mm in CATIA V5 (areas/volumes are SI); a sub-millimetre
            # reading for a real thread face would mean metres, so convert explicitly.
            return value * 1000 if 0 < value < 0.5 else value
        except CADOperationError:
            raise
        except Exception:
            return None
