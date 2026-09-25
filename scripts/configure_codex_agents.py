"""Materialize complete, machine-local MCP transports in the Windows role files.

Never edits .codex/config.toml. Portable role files deliberately omit transport
stubs: Codex rejects enabled-only MCP definitions without a command or URL.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


ROLE_ACCESS = {
    "cad_drawing_reader": (False, False),
    "cad_model_inspector": (False, True),
    "cad_planner": (False, False),
    "cad_safety_reviewer": (False, True),
    "cad_executor": (True, False),
    "cad_verifier": (False, True),
}
START_MARKER = "# BEGIN GENERATED CATIA MCP TRANSPORTS"
END_MARKER = "# END GENERATED CATIA MCP TRANSPORTS"


def render_agent_config(source: str, role: str, python_path: Path) -> str:
    """Preserve role instructions and replace only our generated transport block."""
    if START_MARKER in source:
        prefix, tail = source.split(START_MARKER, 1)
        if END_MARKER not in tail:
            raise ValueError(f"Incomplete generated transport block for {role}")
        _, suffix = tail.split(END_MARKER, 1)
        source = prefix + suffix
    if "[mcp_servers." in source:
        raise ValueError(f"Manual MCP configuration in {role}; refusing to overwrite it")
    parsed = tomllib.loads(source)
    if parsed.get("name") != role:
        raise ValueError(f"Agent name does not match {role}")
    for key in ("description", "developer_instructions"):
        if not isinstance(parsed.get(key), str) or not parsed[key].strip():
            raise ValueError(f"Missing {key} in {role}")
    writer, inspector = ROLE_ACCESS[role]
    command = json.dumps(str(python_path), ensure_ascii=False)
    block = f'''{START_MARKER}
[mcp_servers.catia-v5]
command = {command}
args = ["-m", "catia_mcp"]
enabled = {str(writer).lower()}
required = {str(writer).lower()}
startup_timeout_sec = 30

[mcp_servers.catia-v5-inspect]
command = {command}
args = ["-m", "catia_mcp", "--inspection-only"]
enabled = {str(inspector).lower()}
required = {str(inspector).lower()}
startup_timeout_sec = 30
{END_MARKER}
'''
    rendered = source.rstrip() + "\n\n" + block
    tomllib.loads(rendered)
    return rendered


def configure_agents(project_root: Path, python_path: Path) -> list[str]:
    project_root = project_root.resolve()
    python_path = python_path.resolve()
    expected_python = project_root / ".venv" / "Scripts" / "python.exe"
    if python_path != expected_python.resolve() or not python_path.is_file():
        raise ValueError("Run this script with the project's Windows .venv Python")
    agent_dir = project_root / ".codex" / "agents"
    # Validate every source before writing any role file.
    changes = {}
    for role in ROLE_ACCESS:
        path = agent_dir / f"{role}.toml"
        changes[path] = render_agent_config(path.read_text(encoding="utf-8-sig"), role, python_path)
    for path, content in changes.items():
        if path.read_text(encoding="utf-8") == content:
            continue
        backup_dir = project_root / ".local" / "role-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / path.name
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        path.write_text(content, encoding="utf-8")
    return list(ROLE_ACCESS)


def main() -> int:
    if os.name != "nt":
        print("Agent MCP setup is Windows-only; no configuration was changed.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    roles = configure_agents(root, Path(sys.executable))
    print(f"Configured {len(roles)} CATIA roles; .codex/config.toml was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
