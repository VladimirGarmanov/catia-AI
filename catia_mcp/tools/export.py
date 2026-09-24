"""Export tools for CATIA V5.

Export to STEP, IGES, STL, 3DXML, and other formats.
Also includes screenshot capture.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Any

from catia_mcp.connection import CATIAConnection

# CATIA export format identifiers
FORMAT_MAP = {
    "step": "stp",
    "stp": "stp",
    "iges": "igs",
    "igs": "igs",
    "stl": "stl",
    "3dxml": "3dxml",
    "wrl": "wrl",
    "vrml": "wrl",
    "pdf": "pdf",
    "cgr": "cgr",
}


@dataclass(frozen=True)
class ScreenshotCapture:
    file_path: str
    mime_type: str
    image_bytes: bytes


class ExportTools:
    """Tools for exporting CATIA V5 data to external formats."""

    def __init__(self, connection: CATIAConnection) -> None:
        self.conn = connection

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "catia_export",
                "description": (
                    "Export the active document to a file. "
                    "Supported formats: STEP (.stp), IGES (.igs), STL (.stl), "
                    "3DXML (.3dxml), VRML (.wrl), PDF (2D drawings)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": (
                                "Output file path. The format is determined by the extension. "
                                "Example: 'C:/export/my_part.stp'"
                            ),
                        },
                        "format": {
                            "type": "string",
                            "description": (
                                "Export format (optional if file extension is provided). "
                                "One of: step, iges, stl, 3dxml, vrml"
                            ),
                            "enum": ["step", "iges", "stl", "3dxml", "vrml"],
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_screenshot",
                "description": (
                    "Capture the current 3D view, save it, and return the image "
                    "as MCP image content. "
                    "Supports JPG, BMP, TIFF (CATIA V5 cannot capture PNG; a .png path "
                    "is saved as .jpg instead). Pixel size follows the CATIA viewer."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Output image path (e.g., 'C:/screenshots/part.png')",
                        },
                    },
                    "required": ["file_path"],
                },
            },
            {
                "name": "catia_set_view",
                "description": (
                    "Set the 3D view orientation. "
                    "Standard views: front, back, top, bottom, left, right, isometric."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "view": {
                            "type": "string",
                            "description": "View orientation",
                            "enum": [
                                "front", "back", "top", "bottom",
                                "left", "right", "isometric",
                            ],
                        },
                    },
                    "required": ["view"],
                },
            },
            {
                "name": "catia_fit_all",
                "description": "Fit all geometry in the current 3D view (zoom to fit).",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str | ScreenshotCapture:
        match tool_name:
            case "catia_export":
                return self._export(arguments["file_path"], arguments.get("format"))
            case "catia_screenshot":
                if "width" in arguments or "height" in arguments:
                    raise ValueError(
                        "catia_screenshot does not control pixel dimensions; "
                        "resize the CATIA viewer before capture"
                    )
                return self._screenshot(arguments["file_path"])
            case "catia_set_view":
                return self._set_view(arguments["view"])
            case "catia_fit_all":
                return self._fit_all()
            case _:
                raise ValueError(f"Unknown export tool: {tool_name}")

    def _export(self, file_path: str, fmt: str | None = None) -> str:
        self.conn.ensure_connected()
        doc = self.conn.active_document

        # Determine format from extension if not specified
        if fmt is None:
            ext = os.path.splitext(file_path)[1].lstrip(".").lower()
            fmt = ext

        fmt_key = fmt.lower()
        if fmt_key not in FORMAT_MAP:
            supported = ", ".join(sorted(set(FORMAT_MAP.keys())))
            raise ValueError(
                f"Unsupported export format: '{fmt}'. Supported: {supported}"
            )

        # Ensure output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # CATIA V5 export via SaveAs with format specification
        doc.ExportData(file_path, FORMAT_MAP[fmt_key])

        size_info = ""
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            if size_bytes > 1024 * 1024:
                size_info = f" ({size_bytes / (1024*1024):.1f} MB)"
            elif size_bytes > 1024:
                size_info = f" ({size_bytes / 1024:.1f} KB)"
            else:
                size_info = f" ({size_bytes} bytes)"

        return f"Exported to {file_path}{size_info} (format: {fmt_key.upper()})"

    def _screenshot(self, file_path: str) -> ScreenshotCapture:
        self.conn.ensure_connected()
        if not file_path or not file_path.strip():
            raise ValueError("An explicit file_path is required for a screenshot")
        file_path = os.path.abspath(file_path)

        # CatCaptureFormat: 2 = TIFF, 4 = BMP, 5 = JPEG (no PNG in CATIA V5)
        capture_formats = {".jpg": 5, ".jpeg": 5, ".bmp": 4, ".tif": 2, ".tiff": 2}
        mime_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".bmp": "image/bmp",
            ".tif": "image/tiff", ".tiff": "image/tiff",
        }
        ext = os.path.splitext(file_path)[1].lower()
        capture_format = capture_formats.get(ext)
        if capture_format is None:
            file_path = os.path.splitext(file_path)[0] + ".jpg"
            capture_format = 5

        output_dir = os.path.dirname(file_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        viewer = self.conn.active_window.ActiveViewer
        # A fresh capture path prevents an old image from being reported as new
        # if CATIA returns without writing a file. Preserve the prior destination
        # until a nonempty new capture has actually been read.
        with tempfile.TemporaryDirectory(prefix=".catia-capture-", dir=output_dir) as capture_dir:
            capture_path = os.path.join(capture_dir, os.path.basename(file_path))
            viewer.CaptureToFile(capture_format, capture_path)
            try:
                with open(capture_path, "rb") as image_file:
                    image_bytes = image_file.read()
            except OSError as exc:
                raise RuntimeError(f"CATIA did not produce a readable new screenshot: {exc}") from exc
            if not image_bytes:
                raise RuntimeError("CATIA produced an empty screenshot")
            os.replace(capture_path, file_path)
        return ScreenshotCapture(file_path, mime_types.get(ext, "image/jpeg"), image_bytes)

    def _set_view(self, view: str) -> str:
        self.conn.ensure_connected()
        viewer = self.conn.active_window.ActiveViewer
        viewpoint = viewer.Viewpoint3D

        # Standard view direction vectors and up vectors
        views = {
            "front":     {"sight": (0, 0, -1), "up": (0, 1, 0)},
            "back":      {"sight": (0, 0, 1),  "up": (0, 1, 0)},
            "top":       {"sight": (0, -1, 0), "up": (0, 0, -1)},
            "bottom":    {"sight": (0, 1, 0),  "up": (0, 0, 1)},
            "left":      {"sight": (1, 0, 0),  "up": (0, 1, 0)},
            "right":     {"sight": (-1, 0, 0), "up": (0, 1, 0)},
            "isometric": {"sight": (-1, -1, -1), "up": (0, 1, 0)},
        }

        if view not in views:
            raise ValueError(f"Unknown view: '{view}'")

        v = views[view]
        sight = v["sight"]
        up = v["up"]

        # Set viewpoint sight and up directions
        viewpoint.PutSightDirection(list(sight))
        viewpoint.PutUpDirection(list(up))

        # Fit all in view
        viewer.Reframe()

        return f"View set to: {view}"

    def _fit_all(self) -> str:
        self.conn.ensure_connected()
        viewer = self.conn.active_window.ActiveViewer
        viewer.Reframe()
        return "View fitted to all geometry"
