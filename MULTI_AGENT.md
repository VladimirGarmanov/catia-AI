# Legacy multi-agent experiment — not the default

The supported launch workflow is now **single-agent**. Use INSTALL.cmd and
START_CATIA_AI.cmd, or START_WITH_DRAWING.cmd. See [WINDOWS_CODEX.md](WINDOWS_CODEX.md).

Windows evidence: both MCP processes discovered correctly (13 inspection / 81
full tools), but cad_executor received only the parent's 13 inspection tools.
Changing fork_turns from all to none did not change that result. The exact cause
inside Codex was not established; TOML validation was not proof of role access.

The six .codex/agents files and scripts/configure_codex_agents.py are retained as
legacy references, not as a required or verified operating mode. INSTALL no
longer edits these roles or registers the inspection server. START disables
subagents for its session and connects the full MCP to the main chat directly.

Do not follow old reader/planner/executor/verifier prompts in this mode. One
agent performs the whole authorized workflow and checks its own result. That is
not independent verification. Do not run another CAD automation session at the
same time.

.codex/config.toml is preserved, including its old team comments/settings.
Session-only CLI overrides take precedence; simply running codex without the
launcher does not select the new mode.
