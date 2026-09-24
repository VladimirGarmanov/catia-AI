"""CATIA V5 MCP Server.

Main entry point. Exposes all CATIA V5 automation tools via the
Model Context Protocol (MCP) for local Codex and other MCP clients.

Usage:
    python -m catia_mcp.server
    # or
    catia-mcp  (if installed via pip)
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ImageContent, TextContent, Tool, ToolAnnotations

from catia_mcp.connection import CATIAConnection
from catia_mcp.tools.assembly import AssemblyTools
from catia_mcp.tools.context import ContextTools
from catia_mcp.tools.document import DocumentTools
from catia_mcp.tools.export import ExportTools, ScreenshotCapture
from catia_mcp.tools.gsd import GSDTools
from catia_mcp.tools.measurement import MeasurementTools
from catia_mcp.tools.part_design import PartDesignTools
from catia_mcp.tools.sketcher import SketcherTools

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "catia_mcp.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("catia_mcp")

# A separate inspection-only MCP process exposes only these tools. Keep this an
# explicit allowlist: new modeling tools must never become available by default.
INSPECTION_TOOL_NAMES = frozenset({
    "catia_connect",
    "catia_disconnect",
    "catia_list_documents",
    "catia_get_active_document_info",
    "catia_get_selection",
    "catia_get_model_state",
    "catia_list_features",
    "catia_list_edges",
    "catia_list_components",
    "catia_list_constraints",
    "catia_gsd_list_elements",
    "catia_get_parameters",
    "catia_screenshot",
})


class CATIAMCPServer:
    """MCP server that bridges clients to CATIA V5 via COM Automation."""

    def __init__(self, inspection_only: bool = False) -> None:
        self.inspection_only = inspection_only
        server_name = "catia-v5-inspect" if inspection_only else "catia-v5-mcp"
        self.server = Server(server_name)
        self.connection = CATIAConnection(allow_launch=not inspection_only)

        # Initialize tool modules with shared connection
        self.document_tools = DocumentTools(self.connection)
        self.context_tools = ContextTools(self.connection)
        self.sketcher_tools = SketcherTools(self.connection)
        self.part_design_tools = PartDesignTools(self.connection)
        self.gsd_tools = GSDTools(self.connection)
        self.assembly_tools = AssemblyTools(self.connection)
        self.measurement_tools = MeasurementTools(self.connection)
        self.export_tools = ExportTools(self.connection)

        # All tool modules
        self._tool_modules = [
            self.document_tools,
            self.context_tools,
            self.sketcher_tools,
            self.part_design_tools,
            self.gsd_tools,
            self.assembly_tools,
            self.measurement_tools,
            self.export_tools,
        ]

        # Build tool name -> module routing table
        self._all_tool_router: dict[str, Any] = {}
        for module in self._tool_modules:
            for tool_def in module.get_tool_definitions():
                self._all_tool_router[tool_def["name"]] = module
        if inspection_only:
            missing = INSPECTION_TOOL_NAMES - self._all_tool_router.keys()
            if missing:
                raise RuntimeError(f"Unknown inspection tools: {sorted(missing)}")
            self._tool_router = {
                name: module for name, module in self._all_tool_router.items()
                if name in INSPECTION_TOOL_NAMES
            }
        else:
            self._tool_router = self._all_tool_router.copy()

        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            tools = []
            for module in self._tool_modules:
                for tool_def in module.get_tool_definitions():
                    if tool_def["name"] not in self._tool_router:
                        continue
                    description = tool_def["description"]
                    if self.inspection_only and tool_def["name"] == "catia_connect":
                        description = "Attach to an already running CATIA V5 instance."
                    tools.append(
                        Tool(
                            name=tool_def["name"],
                            description=description,
                            inputSchema=tool_def["inputSchema"],
                            annotations=(
                                ToolAnnotations(readOnlyHint=True)
                                if tool_def.get("readOnlyHint") else None
                            ),
                        )
                    )
            logger.info("Listed %d tools", len(tools))
            return tools

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> list[TextContent | ImageContent] | CallToolResult:
            arguments = arguments or {}
            logger.info("Tool call: %s(%s)", name, arguments)

            try:
                if (
                    self.inspection_only and name in self._all_tool_router
                    and name not in self._tool_router
                ):
                    result = {
                        "ok": False,
                        "code": "INSPECTION_ONLY",
                        "message": f"{name} cannot run in the inspection-only MCP server",
                    }
                    return CallToolResult(
                        content=[TextContent(type="text", text=json.dumps(result))],
                        structuredContent=result,
                        isError=True,
                    )
                module = self._tool_router.get(name)
                if module is None:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: '{name}'. Use list_tools to see available tools.",
                        )],
                        isError=True,
                    )

                # Auto-connect for non-connect tools
                if name not in {
                    "catia_connect", "catia_disconnect",
                    "catia_get_selection", "catia_get_model_state",
                    "catia_update_selected_feature",
                    "catia_list_edges",
                } and not self.connection.is_connected:
                    connect_msg = self.connection.connect()
                    logger.info("Auto-connected: %s", connect_msg)

                result = module.execute(name, arguments)
                if isinstance(result, ScreenshotCapture):
                    logger.info("Screenshot captured: %s (%d bytes)",
                                result.file_path, len(result.image_bytes))
                    return [
                        TextContent(type="text", text=f"Screenshot saved to {result.file_path}"),
                        ImageContent(type="image", mimeType=result.mime_type,
                                     data=base64.b64encode(result.image_bytes).decode("ascii")),
                    ]
                if isinstance(result, dict):
                    logger.info("Tool result: %s", str(result)[:200])
                    return CallToolResult(
                        content=[TextContent(type="text", text=json.dumps(
                            result, indent=2, ensure_ascii=False))],
                        structuredContent=result,
                        isError=not result.get("ok", True),
                    )
                logger.info("Tool result: %s", result[:200] if len(result) > 200 else result)
                return [TextContent(type="text", text=result)]

            except Exception as e:
                error_msg = f"Error in {name}: {e}"
                logger.exception(error_msg)
                return CallToolResult(
                    content=[TextContent(type="text", text=error_msg)],
                    isError=True,
                )

    async def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting CATIA V5 MCP Server...")
        logger.info("Registered %d tools across %d modules",
                     len(self._tool_router), len(self._tool_modules))

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main() -> None:
    """Entry point for the CATIA V5 MCP Server."""
    parser = argparse.ArgumentParser(description="CATIA V5 MCP server")
    parser.add_argument(
        "--inspection-only", action="store_true",
        help="Expose only observational CATIA tools; do not launch CATIA",
    )
    arguments = parser.parse_args()
    server = CATIAMCPServer(inspection_only=arguments.inspection_only)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
