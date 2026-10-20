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
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ImageContent, TextContent, Tool, ToolAnnotations

from catia_mcp.connection import CATIAConnection
from catia_mcp.fallback import fallback_advice
from catia_mcp.runtime import SessionState, CADOperationError, error_details
from catia_mcp.tools.assembly import AssemblyTools
from catia_mcp.tools.context import ContextTools
from catia_mcp.tools.document import DocumentTools
from catia_mcp.tools.export import ExportTools, ScreenshotCapture
from catia_mcp.tools.gsd import GSDTools
from catia_mcp.tools.measurement import MeasurementTools
from catia_mcp.tools.part_design import PartDesignTools
from catia_mcp.tools.sketcher import SketcherTools
from catia_mcp.tools.capabilities import CapabilityTools

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
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="catia-com")
        self._inflight = None
        self._timed_out = False
        self._call_lock = asyncio.Lock()
        self.session = SessionState(self.connection)
        self.connection.session = self.session

        # Initialize tool modules with shared connection
        self.document_tools = DocumentTools(self.connection)
        self.context_tools = ContextTools(self.connection)
        self.sketcher_tools = SketcherTools(self.connection)
        self.part_design_tools = PartDesignTools(self.connection)
        self.gsd_tools = GSDTools(self.connection)
        self.assembly_tools = AssemblyTools(self.connection)
        self.measurement_tools = MeasurementTools(self.connection)
        self.export_tools = ExportTools(self.connection)
        from catia_mcp.tools.engineering import EngineeringTools
        self.engineering_tools = EngineeringTools(self.connection, self.session, self.sketcher_tools)
        self.capability_tools = CapabilityTools()
        from catia_mcp.tools.advanced_geometry import AdvancedGeometryTools
        from catia_mcp.tools.domains import DomainTools
        from catia_mcp.tools.drafting import DraftingTools
        self.advanced_tools = AdvancedGeometryTools(self.engineering_tools)
        self.domain_tools = DomainTools(self.engineering_tools)
        self.drafting_tools = DraftingTools(self.engineering_tools)
        from catia_mcp.tools.analysis_tools import AnalysisTools
        from catia_mcp.tools.sketch_operations import SketchOperationTools
        self.analysis_tools = AnalysisTools(self.engineering_tools)
        self.sketch_operation_tools = SketchOperationTools(self.engineering_tools)
        from catia_mcp.tools.sketch_session import SketchSessionTools
        from catia_mcp.tools.v5_reference import V5ReferenceTools
        self.sketch_session_tools = SketchSessionTools(self.engineering_tools)
        self.v5_reference_tools = V5ReferenceTools()
        from catia_mcp.tools.shape_factory import ShapeFactoryTools, VolumeFactoryTools
        self.shape_factory_tools = ShapeFactoryTools(self.engineering_tools)
        self.volume_factory_tools = VolumeFactoryTools(self.engineering_tools)
        from catia_mcp.tools.desktop import DesktopTools
        self.desktop_tools = DesktopTools(self.connection, self.session)

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
            self.engineering_tools,
            self.capability_tools,
            self.advanced_tools,
            self.domain_tools,
            self.drafting_tools,
            self.analysis_tools,
            self.sketch_operation_tools,
            self.sketch_session_tools,
            self.v5_reference_tools,
            self.shape_factory_tools,
            self.volume_factory_tools,
            self.desktop_tools,
        ]

        # Build tool name -> module routing table
        self._all_tool_router: dict[str, Any] = {}
        self._schemas = {}
        for module in self._tool_modules:
            for tool_def in module.get_tool_definitions():
                if tool_def["name"] in self._all_tool_router:
                    raise RuntimeError(f"Duplicate tool: {tool_def['name']}")
                self._all_tool_router[tool_def["name"]] = module
                schema = deepcopy(tool_def["inputSchema"])
                schema.setdefault("properties", {}).update({
                    "document_id": {"type": "string", "minLength": 1},
                    "request_id": {"type": "string", "minLength": 1},
                    "expected_revision": {"type": "integer", "minimum": 0},
                })
                schema["additionalProperties"] = False
                if (module is self.engineering_tools or getattr(module, "strict_writes", False)) and not tool_def.get("readOnlyHint") and tool_def["name"] != "catia_new_drawing":
                    schema["required"] = list(dict.fromkeys(schema.get("required", []) +
                        ["document_id", "request_id", "expected_revision"]))
                self._schemas[tool_def["name"]] = schema
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
        self.capability_tools.available_tools = set(self._tool_router)

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
                            inputSchema=self._schemas[tool_def["name"]],
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

                # Everything that can touch COM runs on ONE dedicated apartment.
                # Shielding cancellation prevents cancellation from implying rollback.
                result = await self._dispatch_worker(name, arguments)
                if isinstance(result, ScreenshotCapture):
                    logger.info("Screenshot captured: %s (%d bytes)",
                                result.file_path, len(result.image_bytes))
                    return [
                        TextContent(type="text", text=f"Screenshot saved to {result.file_path}"),
                        ImageContent(type="image", mimeType=result.mime_type,
                                     data=base64.b64encode(result.image_bytes).decode("ascii")),
                    ]
                if isinstance(result, dict):
                    desktop_png = result.pop("_desktop_png", None)
                    result = fallback_advice(result)
                    logger.info("Tool result: %s", str(result)[:200])
                    return CallToolResult(
                        content=[TextContent(type="text", text=json.dumps(
                            result, indent=2, ensure_ascii=False))] + (
                                [ImageContent(type="image", mimeType="image/png", data=desktop_png)]
                                if desktop_png else []),
                        structuredContent=result,
                        isError=not result.get("ok", True),
                    )
                logger.info("Tool result: %s", result[:200] if len(result) > 200 else result)
                return [TextContent(type="text", text=result)]

            except Exception as e:
                error_msg = f"Error in {name}: {e}"
                logger.exception(error_msg)
                failure = fallback_advice({"ok": False, "code": "TOOL_EXCEPTION",
                                           "message": error_msg})
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(failure, ensure_ascii=False))],
                    structuredContent=failure,
                    isError=True,
                )

    async def _dispatch_worker(self, name, arguments):
        async with self._call_lock:
            if self._timed_out and self._inflight is not None and not self._inflight.done():
                return {"ok": False, "code": "SESSION_STATE_UNKNOWN",
                        "message": "Previous COM call still running; no new operation queued"}
            timeout_event = threading.Event()
            future = asyncio.get_running_loop().run_in_executor(
                self.worker, self._execute_with_timeout_marker, name, arguments, timeout_event)
            self._inflight = future
            try:
                result = await asyncio.wait_for(asyncio.shield(future), timeout=120)
            except asyncio.TimeoutError:
                timeout_event.set()
                self._timed_out = True
                return {"ok": False, "code": "COM_TIMEOUT", "status": "partial_failure",
                        "message": "Completion unknown; worker NOT cancelled. Do not replay. Wait, then inspect model state."}
            except asyncio.CancelledError:
                timeout_event.set()
                self._timed_out = True
                raise
            self._timed_out = False
            return result

    def _execute_with_timeout_marker(self, name, arguments, timeout_event):
        # Executed on the COM thread, including the health transition.
        self.desktop_tools.cancel_event = timeout_event
        try:
            return self._execute_serial(name, arguments)
        finally:
            self.desktop_tools.cancel_event = None
            if name == "catia_ui_action" and self.session.mutation_started:
                # UI may enter/exit edition or delete an object without COM handles
                # reflecting it. Rebind/adopt the actual sketch after inspection.
                self.session.objects.clear()
                self.desktop_tools.snapshot = None
                self.sketcher_tools._active_factory = None
                self.sketcher_tools._active_sketch = None
                self.sketcher_tools._active_document_identity = None
                self.sketcher_tools._active_document = None
                self.sketcher_tools._adopted_ui_sketch = False
                self.session.reconciliation_required = True
            if timeout_event.is_set():
                self.session.reconciliation_required = True

    def _execute_serial(self, name, arguments):
        state = self.session
        read_names = INSPECTION_TOOL_NAMES | {
            "catia_sketch_get_geometry", "catia_get_inertia", "catia_measure",
            "catia_measure_distance", "catia_get_bounding_box", "catia_list_objects",
            "catia_measure_object", "catia_capability_status",
            "catia_sketch_diagnose", "catia_domain_objects", "catia_measure_exact",
            "catia_material_catalog", "catia_diagnose_geometry",
            "catia_capability_request",
            "catia_sketch_context", "catia_v5_reference_search", "catia_v5_reference_read",
            "catia_sketch_constraints",
            "catia_ui_snapshot",
        }
        write = name not in read_names
        creates_document = name in {"catia_new_part", "catia_new_product", "catia_open_document", "catia_new_drawing"}
        request_id = arguments.get("request_id")
        fingerprint = None
        key = None
        entered = False
        previous_in_work = None
        state.created, state.modified = [], []
        self.connection.operation_body = None
        state.updated = state.mutation_started = False
        if name in {"catia_ui_snapshot", "catia_ui_action"}:
            return self._execute_desktop(name, arguments)
        try:
            fingerprint = json.dumps([name, arguments], sort_keys=True, allow_nan=False)
            errors = list(Draft202012Validator(self._schemas[name]).iter_errors(arguments))
            if errors:
                raise CADOperationError("INVALID_ARGUMENT", errors[0].message)
            if request_id in state.requests:
                previous, result = state.requests[request_id]
                if previous != fingerprint:
                    raise CADOperationError("INVALID_ARGUMENT", "request_id reused with different arguments")
                replay = deepcopy(result)
                replay["replayed"] = True
                return replay
            if write and len(state.requests) >= 10000:
                raise CADOperationError("CAPABILITY_UNAVAILABLE", "Session journal full; inspect/save explicitly and restart MCP")
            if name not in {"catia_connect", "catia_disconnect", "catia_capability_status", "catia_capability_request", "catia_v5_reference_search", "catia_v5_reference_read"}:
                self.connection.ensure_connected()
                if arguments.get("document_id") and self.session.document_id() != arguments["document_id"]:
                    raise CADOperationError("DOCUMENT_MISMATCH", "Explicit document_id differs from the active document")
                if "expected_revision" in arguments:
                    current = state.document_id()
                    if state.revisions[current] != arguments["expected_revision"]:
                        raise CADOperationError("STALE_REFERENCE", "Expected revision differs; read model state")
            if write:
                if not creates_document:
                    key = state.assert_document(arguments.get("document_id"), arguments.get("expected_revision"))
                elif state.reconciliation_required:
                    raise CADOperationError("PARTIAL_MUTATION", "Inspect model state after the previous failure")
                if self.sketcher_tools._active_sketch is not None and (
                    name.startswith("catia_gsd_") or self._tool_router[name] is self.part_design_tools
                    or creates_document
                ):
                    raise CADOperationError("INVALID_ARGUMENT", "Close the edited sketch before this operation")
            entered = True
            if write and not creates_document:
                try:
                    previous_in_work = self.connection.get_active_part().InWorkObject
                except Exception:
                    pass  # Product/Drawing does not have Part.InWorkObject.
            if name == "catia_disconnect":
                if self.sketcher_tools._active_sketch is not None:
                    raise CADOperationError("INVALID_ARGUMENT", "Close the edited sketch before disconnecting")
                self._release_com_references()
            if name == "catia_get_model_state":
                # Discard earlier snapshots before collecting fresh selection handles.
                state.invalidate_topology()
            result = self._tool_router[name].execute(name, arguments)
            failed = isinstance(result, dict) and not result.get("ok", True)
            if write:
                if creates_document and not failed:
                    key = state.bind()["document_id"]
                if key:
                    state.finish_write(key)
                state.reconciliation_required = failed
                if name == "catia_ui_action":
                    # A click can change selection, edition or document. Nothing is
                    # geometrically verified just because Windows accepted input.
                    state.objects.clear()
                    state.reconciliation_required = True
                if not isinstance(result, dict):
                    result = {"ok": True, "message": result}
                result.update(status="partial_failure" if failed else "success",
                              session=state.context(), created_handles=state.created,
                              modified_handles=state.modified, updated=state.updated,
                              request_id=request_id,
                              verification="Live geometric verification is separate from tool completion")
                result.setdefault("warnings", [])
                if request_id is None:
                    result["warnings"].append("Legacy call without request_id: replay protection unavailable; never automatically repeat a write")
            elif name == "catia_get_model_state" and isinstance(result, dict) and result.get("ok"):
                result["session"] = state.bind()
            if name == "catia_disconnect":
                self.session = SessionState(self.connection)
                self.engineering_tools.state = self.session
                self.desktop_tools.state = self.session
                self.desktop_tools.snapshot = None
                self.connection.session = self.session
            if request_id and write:
                state.requests[request_id] = (fingerprint, deepcopy(result))
            return result
        except Exception as exc:
            uncertain = write and entered
            if uncertain:
                state.reconciliation_required = True
                if key:
                    state.finish_write(key)
            error = error_details(exc, name)
            recovery_warnings = []
            if uncertain and previous_in_work is not None:
                try:
                    if state.document_id() == key:
                        self.connection.get_active_part().InWorkObject = previous_in_work
                        recovery_warnings.append("Previous InWorkObject restored; geometry was NOT rolled back")
                except Exception as restore_error:
                    recovery_warnings.append(f"InWorkObject restoration failed: {restore_error}")
            result = {"ok": False, "status": "partial_failure" if uncertain else "failed",
                      "code": error["code"], "error": error, "request_id": request_id,
                      "created_handles": state.created, "modified_handles": state.modified,
                      "updated": state.updated, "session": state.context(),
                      "warnings": (["No rollback or automatic retry; inspect model before continuing"] if uncertain else []) + recovery_warnings}
            if isinstance(request_id, str) and fingerprint is not None and write and request_id not in state.requests:
                state.requests[request_id] = (fingerprint, deepcopy(result))
            return result

    def _execute_desktop(self, name, arguments):
        # Desktop fallback must remain available when COM/document reads fail.
        state = self.session
        request_id = arguments.get("request_id")
        fingerprint = json.dumps([name, arguments], sort_keys=True, allow_nan=False)
        try:
            Draft202012Validator(self._schemas[name]).validate(arguments)
            if request_id in state.requests:
                previous, result = state.requests[request_id]
                if previous != fingerprint:
                    raise CADOperationError("INVALID_ARGUMENT", "request_id reused with different arguments")
                return {**deepcopy(result), "replayed": True}
            result = self.desktop_tools.execute(name, arguments)
        except Exception as exc:
            error = error_details(exc, name)
            result = {"ok": False, "code": error["code"], "error": error,
                      "input_may_have_been_sent": state.mutation_started}
        if name == "catia_ui_action" and isinstance(request_id, str) and request_id not in state.requests:
            state.requests[request_id] = (fingerprint, deepcopy(result))
        return result

    def _release_com_references(self):
        """Release our apartment-owned proxies before CoUninitialize, on worker."""
        self.session.objects.clear()
        self.session.documents.clear()
        self.connection.operation_body = None
        self.sketcher_tools._active_factory = None
        self.sketcher_tools._active_sketch = None
        self.sketcher_tools._active_document_identity = None
        self.sketcher_tools._active_document = None
        self.sketcher_tools._adopted_ui_sketch = False
        self.gsd_tools._geoset_document = None

    def _shutdown_worker(self):
        self._release_com_references()
        self.connection.disconnect()

    async def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting CATIA V5 MCP Server...")
        logger.info("Registered %d tools across %d modules",
                     len(self._tool_router), len(self._tool_modules))

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(read_stream, write_stream,
                                      self.server.create_initialization_options())
        finally:
            await asyncio.get_running_loop().run_in_executor(self.worker, self._shutdown_worker)
            self.worker.shutdown(wait=True)


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
