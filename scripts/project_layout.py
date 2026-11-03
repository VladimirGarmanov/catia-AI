"""Remove known retired entry points, never arbitrary files missing from a ZIP."""
from pathlib import Path


RETIRED_PATHS = (
    "START_CATIA_AI.cmd", "START_CLAUDE_AI.cmd", "START_WITH_DRAWING.cmd",
    "START_CLAUDE_WITH_DRAWING.cmd", "START_SMART_DRAWING.cmd",
    "START_TEAM_AI.cmd", "START_CLAUDE_TEAM.cmd", "INSTALL_CLAUDE.cmd",
    "DIAGNOSE_CLAUDE.cmd", "setup_codex.ps1",
    "WINDOWS_CODEX.md", "WINDOWS_CLAUDE.md", "scripts/configure_codex_agents.py",
)


def retired_files(root: Path):
    """Inspect the exact allowlist; refuse links/junctions and directory replacements."""
    resolved_root = root.resolve()
    for relative in RETIRED_PATHS:
        target = root / relative
        for candidate in (target, *target.parents):
            if candidate == root:
                break
            if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
                raise OSError(f"Refusing to clean linked project path: {relative}")
        if not target.resolve().is_relative_to(resolved_root):
            raise OSError(f"Retired path is outside project: {relative}")
        if target.exists():
            if not target.is_file():
                raise OSError(f"Expected a retired file, found a directory: {relative}")
            yield target, Path(relative)


def cleanup_retired(root: Path) -> list[str]:
    # Validate the complete list before removing anything. No archive directory
    # is created; these are superseded application entry points, not user data.
    paths = list(retired_files(root))
    removed = []
    for target, relative in paths:
        target.unlink()
        removed.append(relative.as_posix())
    return removed
