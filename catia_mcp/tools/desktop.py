"""Read-only Windows desktop inspection; input is disabled by constraint policy."""
import base64
import io
import os
from dataclasses import dataclass

from catia_mcp.runtime import CADOperationError
from catia_mcp.constraint_policy import check_constraint_command


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
             "description": "Read-only capture of the entire Windows desktop, all monitors and applications, as an MCP image. No CATIA connection/document required. May expose sensitive visible content. UI input is disabled by constraint policy.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "catia_ui_action",
             "description": "DISABLED: generic UI input could bypass the Fix/AutoConstraint ban. Always returns OPERATION_DISABLED without sending input. The server logs the missing_tool name and reason locally for analysis; prefer catia_report_missing_tool instead of attempting input. catia_ui_snapshot remains available for inspection.",
             "inputSchema": {"type": "object", "properties": {
                 "missing_tool": {"type": "string", "minLength": 1, "maxLength": 160,
                                  "description": "Intended CATIA operation unavailable through typed tools; recorded even though UI input is blocked"},
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
        check_constraint_command(name, args)
        backend = self.backend_factory()
        window = backend.window()
        if name == "catia_ui_snapshot":
            image, width, height = backend.capture(window)
            return {"ok": True, "window_title": window.title,
                    "width": width, "height": height, "coordinate_origin": "image top-left",
                    "screen_origin": list(window.rect[:2]),
                    "_desktop_png": base64.b64encode(image).decode("ascii")}
        raise CADOperationError("UNSUPPORTED_OPERATION", "Only desktop snapshots are enabled")
