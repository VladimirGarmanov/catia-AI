"""Probe real stdio discovery only: no CATIA tool is called, including connect."""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from catia_mcp.server import INSPECTION_TOOL_NAMES


async def inspect_transport(inspection_only: bool) -> set[str]:
    args = ["-m", "catia_mcp"]
    if inspection_only:
        args.append("--inspection-only")
    parameters = StdioServerParameters(command=sys.executable, args=args)
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        response = await session.list_tools()
        return {tool.name for tool in response.tools}


async def probe_transports() -> dict:
    # Sequential processes: never parallel CATIA clients.
    inspection = await inspect_transport(True)
    full = await inspect_transport(False)
    if inspection != INSPECTION_TOOL_NAMES:
        raise RuntimeError("Inspection MCP tool set does not match the allowlist")
    from importlib.resources import files
    baseline = json.loads(files("CATIA_AGENT_CODEX_PACKAGE").joinpath("CATIA_AGENT_EXISTING_TOOLS.json").read_text(encoding="utf-8"))
    missing = {entry["name"] for entry in baseline["tools"]} - full
    if missing:
        raise RuntimeError(f"Full MCP is missing baseline tools: {sorted(missing)}")
    desktop = {"catia_ui_snapshot", "catia_ui_action"}
    if not desktop <= full or desktop & inspection:
        raise RuntimeError("Desktop fallback must exist only in the full MCP transport")
    return {
        "inspection_tools": len(inspection), "full_tools": len(full),
        "stdio_discovery": "PASS", "catia_com": "NOT_TESTED",
        "codex_session_tool_access": "NOT_TESTED",
        "note": "No tools called. Interactive Codex access must be checked in its own session.",
    }


def main() -> None:
    print(json.dumps(asyncio.run(asyncio.wait_for(probe_transports(), timeout=60)), indent=2))


if __name__ == "__main__":
    main()
