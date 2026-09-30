"""Windows user-local setup/start/diagnostics; never changes execution policies.

Python is the bootstrap prerequisite. Existing portable Node installations are
reused; a missing Node executable can be selected with a file dialog. Codex is
installed via npm only when absent. No administrator rights or Git are used.
"""

from __future__ import annotations

import argparse
import json
import ntpath
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS_PROMPT = (
    "Read AGENTS.md. Work as ONE agent; do not spawn or delegate to subagents. "
    "This startup check is not authorization to model. "
    "Do not run setup, modify configuration, change Windows policies, or use direct COM scripts. "
    "Check YOUR OWN available tools for catia_new_part, catia_pad, catia_get_model_state, "
    "catia_get_selection and catia_screenshot without calling them. Report PASS/FAIL. "
    "If absent, report the exact MCP startup error and stop; do not repeat installation. "
    "If present, wait for the user task. Read attached drawings visually, ask for missing "
    "dimensions and units, then execute authorized modeling yourself through MCP, serially. "
    "After each feature update and measure; screenshot at meaningful feature checkpoints, "
    "not after every primitive operation. Never save or overwrite "
    "without an explicit path and instruction."
)


class SetupError(RuntimeError):
    """An actionable installation error; no policy workaround is attempted."""


def windows_command(argv: list[str], comspec: str) -> list[str] | str:
    """Use .cmd explicitly, with all arguments quoted and shell expansion rejected.

    cmd.exe has different quoting from a native executable. Reject uncommon
    shell-active path characters rather than silently expanding or executing them.
    Spaces and Unicode paths are supported; .ps1 is never an accepted launcher.
    """
    suffix = Path(argv[0]).suffix.lower()
    if suffix == ".ps1":
        raise SetupError("PowerShell launchers are not supported; select codex.cmd or codex.exe")
    if suffix not in {".cmd", ".bat"}:
        return argv
    if any(any(char in arg for char in '\"%!^&|<>\r\n') for arg in argv):
        raise SetupError("A command path contains shell-active characters. Use a plain folder path.")
    # Pass cmd's command line verbatim: list2cmdline on the nested command
    # would add C-runtime backslash escapes that cmd.exe does not understand.
    body = " ".join(f'"{arg}"' for arg in argv)
    command = subprocess.list2cmdline([comspec]) + ' /d /s /c "' + body + '"'
    if len(command) > 8000:
        raise SetupError("Windows command is too long. Use a shorter project path or fewer PDF pages.")
    return command


def child_environment(node: Path | None, codex: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    parents = [str(path.parent) for path in (node, codex) if path is not None]
    env["PATH"] = os.pathsep.join(parents + [env.get("PATH", "")])
    env["PYTHONUTF8"] = "1"
    return env


class Runner:
    def __init__(self, root: Path, log: Path):
        self.root = root
        self.log = log
        self.env = child_environment(None, None)

    def say(self, message: str) -> None:
        print(message, flush=True)
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")

    def run(self, argv: list[str], *, cwd: Path | None = None,
            check: bool = True, private: bool = False, timeout: int = 300):
        self.say("Running: " + subprocess.list2cmdline(argv))
        command = windows_command(argv, self.env.get("COMSPEC", "cmd.exe"))
        result = subprocess.run(command, cwd=cwd or self.root, env=self.env,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, check=False)
        # MCP JSON may contain user-configured secrets. Never copy it to logs.
        if not private:
            if result.stdout.strip():
                self.say(result.stdout.strip())
            if result.stderr.strip():
                self.say(result.stderr.strip())
        if check and result.returncode:
            raise SetupError(f"Command failed (exit {result.returncode}): {Path(argv[0]).name}. "
                             "Stop here; do not disable security controls. See the log.")
        return result


def read_state(root: Path) -> dict:
    path = root / ".local" / "windows-runtime.json"
    if not path.exists():
        return {}
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise TypeError("Expected an object")
        for key in ("node", "codex"):
            if result.get(key) is not None and not isinstance(result[key], str):
                raise TypeError(f"Expected a path string for {key}")
        return result
    except (ValueError, TypeError, OSError) as exc:
        raise SetupError(f"Cannot read {path}: {exc}") from exc


def first_file(candidates) -> Path | None:
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def discover_node(root: Path, state: dict, user: Path) -> Path | None:
    candidates = [state.get("node"), shutil.which("node.exe"),
                  root / ".local" / "node" / "node.exe"]
    # Bounded lookup for the official ZIP, including Explorer's double nesting.
    downloads = user / "Downloads"
    for folder in sorted(downloads.glob("node-v*-win-*"), reverse=True):
        candidates.append(folder / "node.exe")
        candidates.extend(sorted(folder.glob("node-v*-win-*/node.exe"), reverse=True))
    return first_file(candidates)


def discover_codex(root: Path, state: dict) -> Path | None:
    return first_file([
        root.parent / "runtime" / "codex" / "codex.exe",
        root / ".local" / "codex" / "codex.cmd", state.get("codex"),
        shutil.which("codex.exe"), shutil.which("codex.cmd"),
        Path(os.environ.get("LOCALAPPDATA", str(root / ".local"))) / "codex-cli" / "codex.cmd",
        Path(os.environ.get("APPDATA", str(root / ".local"))) / "npm" / "codex.cmd",
    ])


def project_python(root: Path) -> Path:
    """Return this checkout's venv Python or the full install's bundled runtime."""
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    bundled_python = root.parent / "runtime" / "python" / "python.exe"
    return first_file((venv_python, bundled_python)) or venv_python.resolve()


def pick_node() -> Path:
    print("Node.js was not found. Select node.exe from your extracted official Node LTS ZIP.")
    print("Download, if allowed by your institution: https://nodejs.org/en/download")
    try:
        import tkinter
        from tkinter import filedialog
        window = tkinter.Tk()
        window.withdraw()
        try:
            selected = filedialog.askopenfilename(
                title="Select node.exe from the extracted Node.js folder",
                filetypes=[("Node.js", "node.exe")])
        finally:
            window.destroy()
    except Exception as exc:
        raise SetupError("File picker unavailable. Put Node's extracted contents in "
                         ".local/node and rerun INSTALL.cmd.") from exc
    path = Path(selected)
    if not selected or path.name.lower() != "node.exe" or not path.is_file():
        raise SetupError("No node.exe selected. Nothing was downloaded or security-unblocked.")
    return path.resolve()


def normalize_entry(entry: dict) -> dict:
    enabled = entry.get("enabled", True)
    config = entry.get("config", entry)
    enabled = enabled and config.get("enabled", True)
    transport = config.get("transport", config)
    transport = transport.get("stdio", transport)
    return {"command": transport.get("command"), "args": transport.get("args", []),
            "enabled": bool(enabled and transport.get("enabled", True)),
            "config": config}


def check_entry(entry: dict, python: Path, inspection: bool = False) -> None:
    expected = ["-m", "catia_mcp"] + (["--inspection-only"] if inspection else [])
    actual = normalize_entry(entry)
    same_path = ntpath.normcase(ntpath.normpath(str(actual["command"]))) == ntpath.normcase(
        ntpath.normpath(str(python)))
    if not same_path or actual["args"] != expected:
        raise SetupError("Effective CATIA MCP command/arguments differ from this project. "
                         "No persistent configuration was overwritten.")
    if not actual["enabled"]:
        raise SetupError("The effective full CATIA entry is disabled. Review managed settings.")


def session_overrides(root: Path) -> list[str]:
    """Full MCP for this invocation only; never rewrite user/project config.

    TOML literal strings preserve Windows backslashes and avoid nested double
    quotes in npm's cmd launcher. Reject unsupported paths rather than execute
    an incorrectly quoted command. Complete tables also work on a clean install.
    """
    python = str(project_python(root))
    if any(char in python for char in "'\r\n"):
        raise SetupError("Project path cannot contain apostrophes or newlines for CLI setup.")
    settings = ["agents.enabled=false"]
    for name, inspection in (("catia-v5", False), ("catia-v5-inspect", True)):
        args = "['-m','catia_mcp','--inspection-only']" if inspection else "['-m','catia_mcp']"
        enabled = "false" if inspection else "true"
        settings.append(
            f"mcp_servers.{name}={{command='{python}',args={args},"
            f"enabled={enabled},required={enabled},startup_timeout_sec=60}}")
    return [item for setting in settings for item in ("-c", setting)]


def read_entries(runner: Runner, codex: Path) -> dict:
    result = runner.run([str(codex), *session_overrides(runner.root),
                         "mcp", "list", "--json"], private=True)
    try:
        entries = json.loads(result.stdout)
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise ValueError("Expected a list of MCP entries")
        return {entry["name"]: entry for entry in entries}
    except (ValueError, KeyError) as exc:
        raise SetupError("Cannot parse Codex MCP listing; no configuration was changed.") from exc


def validate_session(entries: dict, python: Path) -> None:
    if "catia-v5" not in entries:
        raise SetupError("Full catia-v5 MCP missing from effective Codex configuration")
    check_entry(entries["catia-v5"], python)
    if ("catia-v5-inspect" in entries
            and normalize_entry(entries["catia-v5-inspect"])["enabled"]):
        raise SetupError("Inspection transport is still enabled in this single-agent session")


def get_runtime(runner: Runner, *, install: bool) -> tuple[Path | None, Path]:
    state = read_state(runner.root)
    node = discover_node(runner.root, state, Path.home())
    codex = discover_codex(runner.root, state)
    if node is None and (codex is None or codex.suffix.lower() != ".exe"):
        if not install:
            raise SetupError("Node.js was moved or not found. Run INSTALL.cmd to select it again.")
        node = pick_node()
    runner.env = child_environment(node, codex)
    if node:
        version = runner.run([str(node), "--version"]).stdout.strip()
        match = re.fullmatch(r"v(\d+)\.\d+\.\d+", version)
        if not match or int(match[1]) < 22:
            raise SetupError("Use an approved Node.js LTS version 22 or newer.")
    if codex is None:
        if not install:
            raise SetupError("Codex was not found. Run INSTALL.cmd.")
        npm = node.parent / "npm.cmd"
        if not npm.is_file():
            raise SetupError("npm.cmd missing beside node.exe. Extract the complete Node ZIP.")
        destination = runner.root / ".local" / "codex"
        runner.say("Installing official @openai/codex into this project's .local/codex.")
        runner.run([str(npm), "install", "-g", "@openai/codex@latest",
                    "--prefix", str(destination)], timeout=900)
        codex = destination / "codex.cmd"
        if not codex.is_file():
            raise SetupError("npm completed but codex.cmd is missing")
    runner.env = child_environment(node, codex)
    runner.run([str(codex), "--version"])
    return node, codex


def install_project(runner: Runner) -> None:
    python = runner.root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        runner.run([sys.executable, "-m", "venv", str(runner.root / ".venv")])
    runner.run([str(python), "-c", "import sys; assert sys.version_info >= (3, 10)"])
    runner.run([str(python), "-m", "pip", "install", "-e",
                str(runner.root) + "[drawings]"], timeout=900)
    runner.run([str(python), str(runner.root / "test_server.py")])
    node, codex = get_runtime(runner, install=True)
    state = {"node": str(node) if node else None, "codex": str(codex)}
    (runner.root / ".local" / "windows-runtime.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8")
    runner.run([str(python), str(runner.root / "scripts" / "windows_launcher.py"), "diagnose"])
    runner.say("Setup complete. Open CATIA, then START_CATIA_AI.cmd. "
               "Single-agent mode: full MCP is scoped to the launcher session. "
               "Live modeling still requires verification.")


def diagnose(runner: Runner, codex: Path) -> None:
    python = project_python(runner.root)
    validate_session(read_entries(runner, codex), python)
    runner.say("Single-agent configuration OK: full catia-v5 enabled; inspection disabled. "
               "No role files or persistent Codex settings were changed.")
    runner.run([str(python), str(runner.root / "scripts" / "check_mcp_transport.py")], timeout=90)
    runner.say("This checks configuration and real stdio discovery only. "
               "CATIA COM and interactive Codex tool access were NOT tested. "
               "No CATIA tool was called. Logs contain local paths; review before sharing.")


def start(runner: Runner, codex: Path, drawing: Path | None = None) -> int:
    diagnose(runner, codex)
    help_text = runner.run([str(codex), "--help"], private=True).stdout
    argv = [str(codex), *session_overrides(runner.root)]
    # A fresh process avoids reusing a daemon/session with pre-setup config.
    # This is a diagnostic precaution, not a claimed fix for role inheritance.
    if "--no-daemon" in help_text:
        argv.append("--no-daemon")
    prompt = READINESS_PROMPT
    if drawing is not None:
        from scripts.drawing_inputs import prepare_drawing
        images = prepare_drawing(drawing, runner.root / ".local" / "drawings")
        for path in images:
            if "," in str(path):
                raise SetupError("Drawing image paths cannot contain commas; move the project.")
            argv.extend(["--image", str(path)])
        prompt += (f" Attached are {len(images)} drawing page image(s) in page order. "
                   "After the tool check, describe the visible geometry, dimensions and "
                   "uncertainties; ask whether to create a NEW part. Do not model yet.")
        runner.say(f"Prepared {len(images)} drawing image(s); original file unchanged.")
    argv.extend(["-C", str(runner.root), prompt])
    runner.say("Starting ONE Codex agent with full CATIA tools. Sign in if asked; "
               "do not share login codes. No modeling is authorized by this launcher.")
    return subprocess.call(windows_command(argv, runner.env.get("COMSPEC", "cmd.exe")),
                           cwd=runner.root, env=runner.env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "diagnose"])
    parser.add_argument("--drawing", type=Path, help="Attach a PNG, JPEG or PDF")
    parser.add_argument("--choose-drawing", action="store_true", help="Open a drawing file picker")
    args = parser.parse_args(argv)
    if os.name != "nt":
        print("Windows-only. No installation or configuration was changed.")
        return 1
    if sys.version_info < (3, 10):  # noqa: UP036 - bootstrap may use an older Python
        print("Python 3.10+ is required.")
        return 1
    sys.path.insert(0, str(ROOT))
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    log = local / {"install": "setup.log", "start": "start.log",
                   "diagnose": "diagnostics.log"}[args.action]
    log.write_text("CATIA AI - " + args.action + "\n", encoding="utf-8")
    runner = Runner(ROOT, log)
    try:
        if args.action == "install":
            install_project(runner)
        else:
            if not project_python(ROOT).is_file():
                raise SetupError("Python runtime is missing. Run INSTALL.cmd or the CATIA AI installer.")
            _, codex = get_runtime(runner, install=False)
            if args.action == "start":
                drawing = args.drawing
                if args.choose_drawing:
                    from scripts.drawing_inputs import choose_drawing
                    drawing = choose_drawing()
                    if drawing is None:
                        runner.say("Drawing selection cancelled. Codex was not started.")
                        return 0
                return start(runner, codex, drawing)
            diagnose(runner, codex)
        return 0
    except (SetupError, OSError, ValueError, subprocess.SubprocessError) as exc:
        runner.say(f"STOP: {exc}")
        runner.say("No policy bypass attempted. If Windows blocks this program, contact IT.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
