# CATIA AI

CATIA V5 MCP server for **Codex and Claude Code** on Windows. The AI client
reads drawings and calls typed Python tools; the server talks to CATIA through
pywin32/COM. No separate paid AI API is embedded in the server.

## Start on Windows

Download the project ZIP from [catia-AI](https://github.com/VladimirGarmanov/catia-AI),
extract it, and open **INSTALL.cmd**. Choose Codex, Claude Code, or both.
Then open CATIA and **START_AI.cmd**. Python, Node when needed, and the selected
client are installed locally; Git and administrator rights are not required.
Network and organization restrictions still apply.

| Entry point | Purpose |
| --- | --- |
| `INSTALL.cmd` | Install or repair dependencies and selected clients |
| `START_AI.cmd` | Choose client and work mode |
| `UPDATE.cmd` | Update project files from published GitHub main |
| `DIAGNOSE.cmd` | Check client configuration and MCP transport |

**One launch menu:** Chat, One drawing, Multiple files + planning team, or
Codex Astra-to-Luna drawing handoff. No separate launcher for each combination.
The full EXE installer opens the same menu through one CATIA AI shortcut.

Full instructions in Russian: **[WINDOWS.md](WINDOWS.md)**.
Ready-to-copy demonstrations: **[DEMO_PROMPTS.md](DEMO_PROMPTS.md)**.

## Working with CATIA

Read the drawing and active model/selection, resolve missing dimensions, then
execute one feature at a time through MCP. Update and measure the result.
Screenshots are useful at meaningful checkpoints, not after every primitive.
The agent does not infer invisible dimensions or overwrite CAD files without
an explicit path and instruction.

The current server registers **151 full tools**; the separate inspection mode
exposes 13. Tool count describes registration, not full native GUI coverage or
live Windows validation. Available groups include document/model context,
Sketcher, Part Design, GSD, assembly, drafting, measurement, and exports.
Read each tool's current schema rather than relying on an old copied tool list.

- [Multiple files and agents](TEAM_WORKFLOW.md): independent planning tasks,
  one coordinator making all CATIA calls serially; explicit document switching.
- [Sketch constraint checks](SKETCH_CONSTRAINT_STATUS.md): constraint health and
  update state; unknown whole-sketch DOF is never reported as fully constrained.
- [Assembly and drawing](ASSEMBLY_DRAWING.md), [patterns](PATTERNS.md),
  [renaming](NAMING.md): scoped operations and live-check requirements.
- [Implementation status](IMPLEMENTATION_STATUS.md): coverage and known limits.
- [Saving and the tool backlog](SAVE_AND_TOOL_GAPS.md): verified native saves
  and a local missing-tools journal; UI input remains disabled.
- [Agent operating rules](AGENTS.md): document identity, fresh references,
  failure handling and the ban on Fix/AutoConstraint. Desktop input is disabled;
  read-only snapshots remain available.

Run only one CAD-writing client at a time. Multiple MCP processes do not share
an interprocess CATIA lock. Parallel agents analyze supplied context; they do
not independently drive the same CATIA session.

Example request:

> Создай кронштейн по приложенному чертежу в новой детали; размеры, которых
> не видно, сначала уточни. Ничего не сохраняй без моего указания пути.

## Project layout

| Path | Responsibility |
| --- | --- |
| `scripts/windows_launcher.py` | Shared installation, launch menus and diagnostics |
| `scripts/install_node.py`, `scripts/update_project.py` | Local runtime download and source update |
| `scripts/drawing_inputs.py`, `scripts/drawing_handoff.py`, `scripts/cad_team.py` | Drawing preparation and planning context |
| `catia_mcp/server.py` | MCP schema registration and dispatch |
| `catia_mcp/runtime.py`, `catia_mcp/connection.py` | Serialized COM operations and session state |
| `catia_mcp/tools/` | Typed CATIA operations |
| `CATIA_AGENT_CODEX_PACKAGE/` | API reference data used by the server |
| `.codex/agents/` | Optional offline planning/review roles |
| `installer/`, `scripts/build_windows_bundle.py` | Full Windows installer build |
| `tests/` | Offline contract and mock checks |

Runtime and user task data live in `.venv` / `.local`. The launcher does not
rewrite `.codex/config.toml` or global client settings. Retired entry points are
removed by a bounded migration; no archive folder or second source tree is kept.

## Development on Mac or Windows

Python 3.10+ is required. From the project folder on macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,drawings]'
.venv/bin/python -m pytest -q
.venv/bin/python test_server.py
```

`pywin32` is installed only on Windows. Mac supports offline development,
reference lookup and mocked tests; it cannot validate CATIA COM geometry.
Never run live modeling probes against a user's working document.

The Windows bundle is built by `.github/workflows/windows-installer.yml` with
`scripts/build_windows_bundle.py` and Inno Setup. A successful installer build
or stdio discovery is not proof of live CATIA operation.

## License and origins

MIT — see [LICENSE](LICENSE). Based on
[daiemon12/catia-v5-mcp-server](https://github.com/daiemon12/catia-v5-mcp-server).
CATIA is a Dassault Systèmes product; Codex and Claude are separate clients.
