# CAA V5 Automation migration — 2026-10-15

## What actually changed

The source baseline is recoverable at Git commit `ef79325`. No user CAD files,
Codex configuration or launcher were deleted. The old server already used raw
pywin32 COM; pycatia was a documentation source, not the connection library.
The COM transport is preserved while editing/session behavior is replaced.
This is a migration in progress, **not a completed rewrite of every CATIA API**.

`scripts/sync_v5_reference.py` indexes the supplied
[CAA V5 Automation mirror](https://catiadesign.org/_doc/V5Automation/).
It does not execute page scripts or use computer control. All unique TOC entries
are indexed; `--pages` downloads all HTML pages referenced by that TOC, with four
workers and resumable local caching. Failures are listed in `download_errors.json`.
This does not claim to crawl every file on the hosting website. The host is not a
Dassault domain; the documentation snapshot may be older than installed CATIA.

Cache: `.local/v5-reference` (ignored by Git, not included in GitHub ZIP).
The saved source hashes record the fetched content, not live API compatibility.

```powershell
.\.venv\Scripts\python.exe scripts\sync_v5_reference.py --pages
```

On macOS use `.venv/bin/python scripts/sync_v5_reference.py --pages`.
`--match SketcherInterfaces` limits downloaded pages, not the full TOC index.
TLS verification remains enabled. No paid AI API or pycatia dependency added.

## Existing sketch workflow

1. Connect; read model state and selection, confirming the active document.
2. `catia_sketch_context` returns actual sketch handles and selected/in-work flags.
3. `catia_sketch_begin_edit`: `mode=open` opens a closed existing sketch through
   `Sketch.OpenEdition`. For a user-open sketch use `mode=adopt_user_open` and
   `user_confirmed_open=true`; this obtains `Sketch.Factory2D` without reopening.
   Choose source=handle, selection (whole Sketch), or in_work. No sketch is created.
4. Existing geometry and constraint tools now work on that bound sketch.
   `catia_sketch_constraints` reads constraint handles/types/modes/statuses.
   `catia_sketch_edit_constraint` sets supported dimensions in explicit mm/deg,
   changes driving/reference mode, or activates/deactivates a constraint.
5. At completion use `catia_close_sketch`, update the Part and verify dimensions.

The documented Sketch interface does **not** expose an IsEditing getter.
The adoption path requires the user's statement plus a matching InWorkObject;
neither proves the UI state independently. Switching active document (including
one with the same filename) or the adopted in-work target stops subsequent edits.
Some containers beyond Body and recursively visited HybridBodies are not yet
supported by sketch discovery. Manual UI closure with unchanged InWorkObject may
only be detected by CATIA rejecting a subsequent operation. Do not edit concurrently.

Source: [Sketch Automation](https://catiadesign.org/_doc/V5Automation/generated/interfaces/SketcherInterfaces/interface_Sketch_21197.htm).

## Tests and remaining work

Sketch constraints now include length, midpoint, equidistance and ellipse radii;
exact line start/end selectors and absolute origin/axis selectors avoid guessing
which vertex an index means. Two-element distance can be horizontal or vertical.
Rectangle and circle accept `anchor_origin=true` for origin-anchored dimensioned
profiles, without blanket Fix constraints. Existing constraints can be explicitly
removed by their exact bound-sketch handle.

`catia_sketch_diagnose` decodes native per-constraint status and inactive state.
It deliberately returns `iso_constrained=null`, `remaining_dof=null`: satisfied
constraints do not establish solver rank, redundancy or full geometric definition.
Verify final iso-constrained status using CATIA Sketch Analysis on Windows.
The previously published claim of all tools is not a claim of all CATIA GUI modes.

Removed obsolete `setup.sh` (Claude installer) and `MULTI_AGENT.md`; no archive
copies were created. Their previous versions remain recoverable through Git.
Active COM modules and the catalogue still used at runtime are retained, not
silently removed along with currently supported modeling operations.

Local download completed on 2026-10-15: 1,490 referenced HTML pages,
10,438 distinct index links, zero failed page downloads. The ignored local cache
is not included in a Git checkout or GitHub ZIP.

132 tools register; original names preserved. Offline mocks exercise adoption
without OpenEdition, explicit opening, same-name/different-document rejection,
target changes and refusal without user confirmation. They do not validate COM.

Required Windows checks: adopt an already UI-open sketch, draw a line, constrain
it, change its dimension, close/update, then verify intended sketch/geometry and
that other documents remain unchanged. Also test manual UI closure and wrong
selection. Drafting currently keeps its previous typed handlers; a full review
against the downloaded CAA pages and live CATDrawing is still outstanding.

Do not treat the 10,438 index links as 10,438 executable tools. Missing native
operations, license-dependent interfaces and unsupported feature types remain
work to implement and validate, not automatic generic COM dispatch permissions.
