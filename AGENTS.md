# CATIA operating rules for Codex

## CAD team workflow

For CATIA modeling requests, the main chat coordinates the project agents in
`.codex/agents`. This workflow is for CAD operations, not ordinary repository
maintenance. Run `setup_codex.ps1` on Windows first so the roles have complete
machine-local MCP transports. Do not add enabled-only MCP stubs to config.toml.

1. Delegate drawing interpretation to `cad_drawing_reader` when a drawing is
   supplied and current model inspection to `cad_model_inspector`. These two
   tasks may run together because only the inspector calls CATIA.
2. Give both reports to `cad_planner`, then send its plan to
   `cad_safety_reviewer`. Resolve missing dimensions with the user. Existing
   user authorization for the stated target and dimensions remains valid.
3. Start exactly one `cad_executor` with the accepted plan and target document.
   It alone may modify CATIA. No other agent may call CATIA while it is working.
   Never start a second executor or delegate a modeling action recursively.
4. After the executor finishes, delegate acceptance to `cad_verifier` with the
   original drawing, accepted plan, and operation evidence. It independently
   reads the model and reports PASS, FAIL, or UNVERIFIABLE per postcondition.
5. A failed check may return to the same executor for at most two scoped repair
   attempts. Do not broaden dimensions, target, or save permissions. Then stop
   and report remaining discrepancies if acceptance is still not established.

The main chat must not bypass the team by running Python COM scripts or altering
role access. The server enforces the inspection tool allowlist; the one-writer
schedule is an orchestration rule, not a lock against other CATIA clients.

## Model operations

- Connect with `catia_connect`, then read `catia_get_model_state` and
  `catia_get_selection` before acting. Confirm
  the active document is the one the user means. Never alter another open document.
- For a new part, call `catia_new_part`, then verify the active document is a
  CATPart before modeling. Issue CATIA tool calls serially.
- After each change, run `catia_update_part`, re-read model state/selection and
  measurable dimensions, then capture `catia_screenshot` and inspect it. An
  image alone does not prove a dimension or material effect.
- Finish and close an edited sketch before accepting it as a completed modeling
  step. Never pass a half-built sketch to the independent verifier.
- `catia_update_selected_feature` acts on the current selected COM feature/sketch,
  not a saved identifier. Read the selection again immediately before calling it.
- Selection names, positions, and topology descriptions are transient, not exact
  face/edge IDs. `catia_list_edges` explicitly reports unsupported exact
  addressing. Do not promise selected-face/edge Fillet, Chamfer, Hole, or Sketch.
- Ask for missing or unreadable dimensions in an attached drawing; never invent
  them. The drawing image is supplied in the Codex chat, not to the MCP server.
- Do not save, close, overwrite, or export a user document without an explicit
  request. Saving requires an explicit output path; overwriting requires opt-in.
- Treat a failed tool call as failure, not as a successful modeling step. CATIA
  COM behavior still needs live Windows verification.
- The Claude skills under `.claude/skills` are engineering references, not
  automatically loaded Codex instructions.
