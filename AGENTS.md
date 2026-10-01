# CATIA operating rules for Codex

## Single-agent workflow (default)

Work as ONE agent. Do not spawn subagents for drawing interpretation, planning,
execution, readiness checks or verification. The user explicitly chose this mode
after custom executor sessions repeatedly inherited only inspection tools.
Legacy files in .codex/agents and MULTI_AGENT.md do not mandate delegation.

In a source checkout, the user runs INSTALL.cmd, then START_CATIA_AI.cmd or
START_WITH_DRAWING.cmd. In the distributed full Windows installer, Python,
Codex and dependencies are bundled; use the installed CATIA AI shortcut instead.
Both launch paths enable the full catia-v5 MCP directly for the main session and
disable subagents/inspection transport through command-line overrides. They do
not rewrite .codex/config.toml or user settings. Do not change access yourself,
run installers during modeling, bypass Windows policy or use direct COM scripts.

At startup check your own available tools (catia_new_part, catia_pad,
catia_get_model_state, catia_get_selection, catia_screenshot). Do not call them
for a tool-availability-only request. Report a missing tool or actual startup
error once and stop. Do not loop through installation or agent readiness checks.

For an authorized modeling request:

1. Read the attached drawing visually. PDF pages may arrive as ordered PNGs.
   List visible dimensions, units, geometry, ambiguities and unreadable areas.
   Ask for missing dimensions; do not infer invisible geometry as fact. A photo
   of an object without scale is not a dimensioned drawing. Ask for a close-up
   if reduced-resolution rendering hides a dimension.
2. Connect and read model state and selection. Confirm the intended document or
   explicit new-part request. A missing active document is normal before a new
   part; other connection/read errors must be resolved first.
3. Describe a short feature plan and measurable postconditions. Resolve missing
   dimensions and ambiguous targets before writing. If the user already gave a
   complete modeling instruction, execute it; do not stop after only a plan or
   demand repeated authorization for that same scope.
4. Execute one feature at a time yourself through MCP, serially. Update, reread
   dimensions/state, capture and inspect a screenshot after each change. Stop
   on an error or failed postcondition; report the last successful operation.
5. Compare the finished model against the drawing and agreed dimensions. Report
   verified and unverified items separately. This is self-verification, not an
   independent review. At most two scoped repair attempts; never broaden scope.

## Model operations

- Use catia_connect, then catia_get_model_state and catia_get_selection before
  acting. Never alter another open document. Do not switch documents blindly.
- For a new part call catia_new_part once, then record the actual new document
  identity and verify CATPart type. Bind later operations to it.
- After each mutation run catia_update_part and verify the active document and
  measurable dimensions. Take screenshots at meaningful feature checkpoints;
  a successful screenshot alone does not prove geometry.
- Finish and close an edited sketch before accepting it as complete.
- catia_update_selected_feature acts on the CURRENT selected COM feature/sketch.
  Reread selection immediately before use; names are not saved object IDs.
- Selection names, positions and topology descriptions are transient, not stable
  face/edge IDs. catia_list_edges still cannot enumerate stable topology IDs.
  Fillet, Chamfer, Shell and Thickness now attempt to consume the currently
  selected exact edge/face through a live COM Reference. This path is experimental
  until a Windows CATIA test proves the intended geometry was modified; reread
  selection immediately before the call and stop if CATIA rejects it. Hole uses
  a positioning sketch, not an arbitrary selected face. Never invent an edge ID.
- Do not save, close, overwrite or export without explicit instruction. Saving
  requires an explicit path; overwriting additionally requires opt-in.
- The user must not switch active documents or run another CATIA automation
  client during modeling. Single-agent scheduling is not a COM interprocess lock.
- Treat failed tools as failures. Offline tests do not validate Windows geometry.
- Drawings are read by Codex, not by a paid AI API in the Python MCP server.
  The Claude skills in .claude/skills are engineering references, not automatic
  Codex instructions.
