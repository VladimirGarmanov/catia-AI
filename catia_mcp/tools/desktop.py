"""Windows whole-desktop input, enabled by explicit user request. No local approval dialog."""
import base64
import io
import os
from dataclasses import dataclass

from catia_mcp.runtime import CADOperationError


@dataclass(frozen=True)
class Window:
    hwnd: int
    pid: int
    title: str
    rect: tuple


class WindowsDesktop:
    def __init__(self):
        if os.name != "nt":
            raise CADOperationError("WINDOWS_ONLY", "Desktop fallback requires Windows with interactive CATIA")
        import ctypes
        import win32api
        import win32gui
        import win32process
        self.ctypes, self.api, self.gui, self.process = ctypes, win32api, win32gui, win32process
        # Match screenshot pixels to mouse coordinates on mixed-DPI monitors.
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))

    def window(self):
        x, y, width, height = [self.api.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
        return Window(0, 0, "Windows desktop (all monitors)", (x, y, x + width, y + height))

    def capture(self, window):
        from PIL import ImageGrab
        image = ImageGrab.grab(all_screens=True)
        width, height = window.rect[2] - window.rect[0], window.rect[3] - window.rect[1]
        if image.size != (width, height) or width <= 0 or height <= 0:
            raise CADOperationError("UI_CAPTURE_MISMATCH", "Capture/window pixel sizes differ; do not guess coordinates")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue(), width, height

    def send(self, window, action):
        import ctypes as c
        from ctypes import wintypes as w

        class Mouse(c.Structure):
            _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("data", w.DWORD),
                        ("flags", w.DWORD), ("time", w.DWORD), ("extra", c.c_size_t)]

        class Keyboard(c.Structure):
            _fields_ = [("vk", w.WORD), ("scan", w.WORD), ("flags", w.DWORD),
                        ("time", w.DWORD), ("extra", c.c_size_t)]

        class Payload(c.Union):
            _fields_ = [("mouse", Mouse), ("keyboard", Keyboard)]

        class Input(c.Structure):
            _anonymous_ = ("payload",)
            _fields_ = [("type", w.DWORD), ("payload", Payload)]

        events = []
        if action["kind"] == "click":
            x, y = window.rect[0] + action["x"], window.rect[1] + action["y"]
            self.api.SetCursorPos((x, y))
            flags = {"left": (2, 4), "right": (8, 16), "middle": (32, 64)}[action.get("button", "left")]
            events = [Input(type=0, mouse=Mouse(flags=flag))
                      for _ in range(action.get("clicks", 1)) for flag in flags]
        elif action["kind"] == "key":
            vk = KEYS[action["key"]]
            events = [Input(type=1, keyboard=Keyboard(vk=vk, flags=flag)) for flag in (0, 2)]
        elif action["kind"] == "hotkey":
            keys = [KEYS[key] for key in action["keys"]]
            events = ([Input(type=1, keyboard=Keyboard(vk=vk)) for vk in keys]
                      + [Input(type=1, keyboard=Keyboard(vk=vk, flags=2)) for vk in reversed(keys)])
        elif action["kind"] == "scroll":
            events = [Input(type=0, mouse=Mouse(data=action["steps"] * 120 & 0xffffffff, flags=0x800))]
        else:
            encoded = action["text"].encode("utf-16-le")
            for offset in range(0, len(encoded), 2):
                unit = int.from_bytes(encoded[offset:offset + 2], "little")
                events.extend(Input(type=1, keyboard=Keyboard(scan=unit, flags=flag))
                              for flag in (4, 6))
        batch = (Input * len(events))(*events)
        send = c.windll.user32.SendInput
        send.argtypes = [w.UINT, c.POINTER(Input), c.c_int]
        send.restype = w.UINT
        if send(len(events), batch, c.sizeof(Input)) != len(events):
            raise CADOperationError("UI_INPUT_PARTIAL", "Input delivery incomplete; inspect, never replay. Check Windows privilege restrictions with IT.")


KEYS = {"enter": 13, "escape": 27, "tab": 9, "backspace": 8,
        "left": 37, "up": 38, "right": 39, "down": 40, "delete": 46,
        "home": 36, "end": 35, "pageup": 33, "pagedown": 34,
        "ctrl": 17, "alt": 18, "shift": 16, "win": 91, "space": 32,
        **{chr(n).lower(): n for n in range(65, 91)},
        **{str(n): 48 + n for n in range(10)},
        **{f"f{n}": 111 + n for n in range(1, 13)}}


class DesktopTools:

    def __init__(self, connection, state, backend_factory=WindowsDesktop):
        self.conn, self.state = connection, state
        self.backend_factory = backend_factory
        self.snapshot = None
        self.cancel_event = None

    def get_tool_definitions(self):
        return [
            {"name": "catia_ui_snapshot", "readOnlyHint": True,
             "description": "Capture entire Windows desktop, all monitors and applications, as an MCP image. No CATIA connection/document required. Coordinates for UI actions are relative to this image top-left. May expose sensitive visible content. No local confirmation dialog.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "catia_ui_action",
             "description": "Windows whole-desktop input without local confirmation or CATIA window restrictions. Acts on current desktop/focus: click, key, hotkey, Unicode text, scroll. Inspect a screenshot first. Coordinates relative to whole-desktop image top-left. No automatic replay; verify result. OS permissions still apply. Use only for the user's authorized task.",
             "inputSchema": {"type": "object", "properties": {
                 "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                 "action": {"oneOf": [
                     {"type": "object", "properties": {"kind": {"const": "click"},
                          "x": {"type": "integer", "minimum": 0}, "y": {"type": "integer", "minimum": 0},
                          "button": {"enum": ["left", "right", "middle"]}, "clicks": {"enum": [1, 2]}},
                      "required": ["kind", "x", "y"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"const": "key"},
                          "key": {"enum": list(KEYS)}},
                      "required": ["kind", "key"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"enum": ["text", "numeric_text"]},
                          "text": {"type": "string", "minLength": 1, "maxLength": 4096}},
                      "required": ["kind", "text"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"const": "hotkey"},
                          "keys": {"type": "array", "items": {"enum": list(KEYS)}, "minItems": 1, "maxItems": 8, "uniqueItems": True}},
                      "required": ["kind", "keys"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"const": "scroll"},
                          "steps": {"type": "integer", "minimum": -100, "maximum": 100}},
                      "required": ["kind", "steps"], "additionalProperties": False},
                 ]},
             }, "required": ["reason", "action", "request_id"]}},
        ]

    def execute(self, name, args):
        backend = self.backend_factory()
        window = backend.window()
        if name == "catia_ui_snapshot":
            image, width, height = backend.capture(window)
            return {"ok": True, "window_title": window.title,
                    "width": width, "height": height, "coordinate_origin": "image top-left",
                    "screen_origin": list(window.rect[:2]),
                    "_desktop_png": base64.b64encode(image).decode("ascii")}
        action = args["action"]
        if action["kind"] == "click" and not (action["x"] < window.rect[2] - window.rect[0] and action["y"] < window.rect[3] - window.rect[1]):
            raise CADOperationError("INVALID_ARGUMENT", "Click coordinates are outside desktop pixels")
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise CADOperationError("UI_CANCELLED", "Request cancelled or timed out; nothing sent")
        self.state.mutation_started = True
        backend.send(window, action)
        return {"ok": True, "input_sent": True, "geometry_verified": False,
                "message": "Desktop input sent without local confirmation. Inspect UI and model; do not replay.",
                "requires_reconciliation": True}
