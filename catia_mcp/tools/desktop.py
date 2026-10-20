"""Human-approved, foreground-only CATIA desktop fallback. No shell execution."""
import base64
import io
import json
import os
import time
import uuid
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
        hwnd = self.gui.GetForegroundWindow()
        if not hwnd or self.gui.IsIconic(hwnd):
            raise CADOperationError("UI_TARGET_UNAVAILABLE", "Bring the intended CATIA window/dialog to the foreground")
        _, pid = self.process.GetWindowThreadProcessId(hwnd)
        handle = self.api.OpenProcess(0x1000, False, pid)
        try:
            # QueryFullProcessImageName needs only limited query rights.
            from ctypes import wintypes
            query = self.ctypes.windll.kernel32.QueryFullProcessImageNameW
            query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                              self.ctypes.POINTER(wintypes.DWORD)]
            query.restype = wintypes.BOOL
            size = wintypes.DWORD(32768)
            path = self.ctypes.create_unicode_buffer(size.value)
            if not query(int(handle), 0, path, self.ctypes.byref(size)):
                raise CADOperationError("UI_TARGET_UNAVAILABLE", "Cannot identify foreground process")
            if os.path.basename(path.value).lower() != "cnext.exe":
                raise CADOperationError("UI_TARGET_MISMATCH", "Foreground window is not CATIA CNEXT.exe")
        finally:
            handle.Close()
        return Window(hwnd, pid, self.gui.GetWindowText(hwnd), self.gui.GetWindowRect(hwnd))

    def capture(self, window):
        from PIL import ImageGrab
        # Window capture avoids including unrelated overlapping application pixels.
        image = ImageGrab.grab(window=window.hwnd)
        width, height = window.rect[2] - window.rect[0], window.rect[3] - window.rect[1]
        if image.size != (width, height) or width <= 0 or height <= 0:
            raise CADOperationError("UI_CAPTURE_MISMATCH", "Capture/window pixel sizes differ; do not guess coordinates")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue(), width, height

    def verify_document_window(self, window, document_name):
        """Conservative UI binding: one visible CNEXT process and matching document title."""
        candidates = set()
        matching = []
        def visit(hwnd, _):
            if not self.gui.IsWindowVisible(hwnd):
                return
            _, pid = self.process.GetWindowThreadProcessId(hwnd)
            # CNEXT's principal windows have CATIA in their title.
            title = self.gui.GetWindowText(hwnd)
            if "CATIA" in title.upper():
                candidates.add(pid)
                if pid == window.pid and document_name.casefold() in title.casefold():
                    matching.append(hwnd)
        self.gui.EnumWindows(visit, None)
        if candidates != {window.pid} or not matching:
            raise CADOperationError("UI_DOCUMENT_UNVERIFIED",
                                    "Cannot bind UI to one CATIA process and the active document title. "
                                    "Show the document in CATIA; do not guess or switch documents.")

    def approve(self, message):
        # Native dialog, default No; the model has no approval field or tool.
        return self.gui.MessageBox(
            0, message, "CATIA AI — confirm ONE UI action",
            0x4 | 0x100 | 0x30 | 0x40000 | 0x10000,
        ) == 6

    def focus_approved(self, window):
        # Human approval explicitly includes restoring this previously captured window.
        self.gui.SetForegroundWindow(window.hwnd)
        if self.window() != window:
            raise CADOperationError("UI_TARGET_CHANGED", "CATIA window changed during approval; capture again")

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

        # Held modifiers can turn a click/key into a different command.
        if any(self.api.GetAsyncKeyState(key) & 0x8000 for key in (16, 17, 18, 91, 92, 1, 2)):
            raise CADOperationError("UI_INPUT_BUSY", "Release keyboard modifiers and mouse buttons first")
        if self.window() != window:
            raise CADOperationError("UI_TARGET_CHANGED", "Foreground CATIA changed before input")
        events = []
        if action["kind"] == "click":
            x, y = window.rect[0] + action["x"], window.rect[1] + action["y"]
            child = self.gui.WindowFromPoint((x, y))
            if self.process.GetWindowThreadProcessId(child)[1] != window.pid:
                raise CADOperationError("UI_TARGET_CHANGED", "Click point is covered by another process")
            self.api.SetCursorPos((x, y))
            if self.window() != window:
                raise CADOperationError("UI_TARGET_CHANGED", "Focus changed before click")
            events = [Input(type=0, mouse=Mouse(flags=flag)) for flag in (2, 4)]
        elif action["kind"] == "key":
            vk = {"enter": 13, "escape": 27, "tab": 9, "backspace": 8,
                  "left": 37, "up": 38, "right": 39, "down": 40}[action["key"]]
            events = [Input(type=1, keyboard=Keyboard(vk=vk, flags=flag)) for flag in (0, 2)]
        else:
            # Unicode input; no clipboard, shell, hotkeys, or arbitrary scripts.
            for character in action["text"]:
                events.extend(Input(type=1, keyboard=Keyboard(scan=ord(character), flags=flag))
                              for flag in (4, 6))
        batch = (Input * len(events))(*events)
        send = c.windll.user32.SendInput
        send.argtypes = [w.UINT, c.POINTER(Input), c.c_int]
        send.restype = w.UINT
        if send(len(events), batch, c.sizeof(Input)) != len(events):
            raise CADOperationError("UI_INPUT_PARTIAL", "Input delivery incomplete; inspect, never replay. Check Windows privilege restrictions with IT.")


class DesktopTools:
    strict_writes = True

    def __init__(self, connection, state, backend_factory=WindowsDesktop, clock=time.monotonic):
        self.conn, self.state = connection, state
        self.backend_factory, self.clock = backend_factory, clock
        self.snapshot = None
        self.cancel_event = None

    def get_tool_definitions(self):
        return [
            {"name": "catia_ui_snapshot", "readOnlyHint": True,
             "description": "Capture foreground CATIA window including dialogs as an MCP image. Windows only. First bring CATIA forward. Returns a one-use, 90-second snapshot_id for human-approved UI input. Not geometric verification.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "catia_ui_action",
             "description": "Fallback only AFTER inspection and explicit chat consent. One left click, navigation key, or numeric text insertion. Requires fresh snapshot and native Windows human confirmation (default No). Never auto-retry. No arbitrary keyboard shortcuts/scripts. Reinspect model and capture again after each action. Keep CATIA and intended document unchanged; do not touch keyboard/mouse during execution.",
             "inputSchema": {"type": "object", "properties": {
                 "snapshot_id": {"type": "string", "minLength": 1},
                 "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                 "action": {"oneOf": [
                     {"type": "object", "properties": {"kind": {"const": "click"},
                          "x": {"type": "integer", "minimum": 0}, "y": {"type": "integer", "minimum": 0}},
                      "required": ["kind", "x", "y"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"const": "key"},
                          "key": {"enum": ["enter", "escape", "tab", "backspace", "left", "right", "up", "down"]}},
                      "required": ["kind", "key"], "additionalProperties": False},
                     {"type": "object", "properties": {"kind": {"const": "numeric_text"},
                          "text": {"type": "string", "minLength": 1, "maxLength": 64,
                                   "pattern": "^[0-9+., eE°-]+$"}},
                      "required": ["kind", "text"], "additionalProperties": False},
                 ]},
             }, "required": ["snapshot_id", "reason", "action"]}},
        ]

    def execute(self, name, args):
        if self.state.reconciliation_required:
            raise CADOperationError("SESSION_STATE_UNKNOWN", "Reconcile model state before desktop fallback")
        backend = self.backend_factory()
        document = self.state.document_id()
        if name == "catia_ui_snapshot":
            window = backend.window()
            backend.verify_document_window(window, self.conn.active_document.Name)
            image, width, height = backend.capture(window)
            if backend.window() != window:
                raise CADOperationError("UI_TARGET_CHANGED", "Window changed while capturing")
            token = uuid.uuid4().hex
            self.snapshot = (token, window, document, self.clock(), self.state.revisions[document])
            return {"ok": True, "snapshot_id": token, "window_title": window.title,
                    "width": width, "height": height, "coordinate_origin": "image top-left",
                    "document_id": document, "_desktop_png": base64.b64encode(image).decode("ascii")}
        saved, self.snapshot = self.snapshot, None
        if (not saved or saved[0] != args["snapshot_id"] or saved[2] != document
                or self.clock() - saved[3] > 90 or saved[4] != self.state.revisions[document]):
            raise CADOperationError("UI_STALE_SNAPSHOT", "Capture a fresh CATIA UI snapshot")
        window = saved[1]
        action = args["action"]
        if action["kind"] == "click" and not (action["x"] < window.rect[2] - window.rect[0] and action["y"] < window.rect[3] - window.rect[1]):
            raise CADOperationError("INVALID_ARGUMENT", "Click is outside captured CATIA window")
        message = (
            f"Document: {self.conn.active_document.Name}\nWindow: {window.title}\n\n"
            f"Proposed action (model-supplied): {args['reason']}\n"
            f"EXACT INPUT: {json.dumps(action, ensure_ascii=False)}\n\n"
            "Allow restoring THIS CATIA window and sending this ONE input?\n"
            "Check the target yourself. No = cancel. Approval expires in 60 seconds.\n"
            "Do not switch documents or touch mouse/keyboard while input runs."
        )
        started = self.clock()
        if not backend.approve(message):
            raise CADOperationError("UI_DENIED", "Human declined UI input; nothing sent")
        if self.clock() - started > 60:
            raise CADOperationError("UI_APPROVAL_EXPIRED", "Approval expired; nothing sent")
        if self.state.document_id() != document:
            raise CADOperationError("DOCUMENT_MISMATCH", "Active document changed during confirmation")
        backend.focus_approved(window)
        backend.verify_document_window(window, self.conn.active_document.Name)
        if self.clock() - started > 60:
            raise CADOperationError("UI_APPROVAL_EXPIRED", "Target verification exceeded approval lifetime; nothing sent")
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise CADOperationError("UI_CANCELLED", "Request cancelled or timed out; nothing sent")
        self.state.mutation_started = True
        backend.send(window, action)
        return {"ok": True, "input_sent": True, "geometry_verified": False,
                "message": "One approved input sent. Read model state and capture again; do not replay.",
                "requires_reconciliation": True}
