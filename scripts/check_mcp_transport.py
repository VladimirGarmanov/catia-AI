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
    if len(full) != 81 or not {"catia_new_part", "catia_pad"} <= full:
        raise RuntimeError("Full MCP does not expose the expected 81 tools")
    return {
        "inspection_tools": len(inspection), "full_tools": len(full),
        "stdio_discovery": "PASS", "catia_com": "NOT_TESTED",
        "codex_executor_tool_access": "NOT_TESTED",
        "note": "No tools called. This does not prove Codex loaded a custom role.",
    }


def main() -> None:
    print(json.dumps(asyncio.run(asyncio.wait_for(probe_transports(), timeout=60)), indent=2))


if __name__ == "__main__":
    main()
