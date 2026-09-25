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
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READINESS_PROMPT = (
    "Read AGENTS.md. This is a readiness check, not authorization to model. "
    "Do not run setup, modify configuration, change Windows policies, or use direct COM scripts. "
    "Spawn the configured cad_executor role with agent_type=cad_executor, not a default agent "
    "merely named executor. It must report its actual MCP tool access, specifically "
    "catia_new_part and catia_pad, without calling them or changing CATIA. "
    "Report the actual spawn arguments and PASS/FAIL for executor tool availability. "
    "Reading TOML or parent inspection tools is not evidence of executor access. "
    "If unavailable, stop and report the startup error or limitation; do not retry endlessly."
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
    return subprocess.list2cmdline([comspec]) + ' /d /s /c "' + body + '"'


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
        root / ".local" / "codex" / "codex.cmd", state.get("codex"),
        shutil.which("codex.exe"), shutil.which("codex.cmd"),
        Path(os.environ.get("LOCALAPPDATA", str(root / ".local"))) / "codex-cli" / "codex.cmd",
        Path(os.environ.get("APPDATA", str(root / ".local"))) / "npm" / "codex.cmd",
    ])


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


def check_entry(entry: dict, python: Path, inspection: bool = True) -> None:
    expected = ["-m", "catia_mcp"] + (["--inspection-only"] if inspection else [])
    actual = normalize_entry(entry)
    same_path = ntpath.normcase(ntpath.normpath(str(actual["command"]))) == ntpath.normcase(
        ntpath.normpath(str(python)))
    if not same_path or actual["args"] != expected:
        raise SetupError("An existing CATIA MCP entry points elsewhere. It was not overwritten. "
                         "Have its owner review it before installing another project copy.")
    if not actual["enabled"]:
        raise SetupError("The CATIA inspection entry is disabled. Review your Codex settings; "
                         "setup will not silently re-enable it.")


def read_entries(runner: Runner, codex: Path, cwd: Path) -> dict:
    result = runner.run([str(codex), "mcp", "list", "--json"], cwd=cwd, private=True)
    try:
        entries = json.loads(result.stdout)
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise ValueError("Expected a list of MCP entries")
        return {entry["name"]: entry for entry in entries}
    except (ValueError, KeyError) as exc:
        raise SetupError("Cannot parse Codex MCP listing; no configuration was changed.") from exc


def preflight_entries(entries: dict, python: Path) -> None:
    if "catia-v5-inspect" in entries:
        check_entry(entries["catia-v5-inspect"], python)
    if "catia-v5" in entries and normalize_entry(entries["catia-v5"])["enabled"]:
        raise SetupError("A global full-access catia-v5 entry already exists. Setup will not "
                         "delete it or expose it to the coordinator. Review it first.")


def configure_mcp(runner: Runner, codex: Path, python: Path) -> None:
    # Read outside the project to avoid mistaking a project override for user config.
    with tempfile.TemporaryDirectory(prefix="catia-config-check-") as directory:
        cwd = Path(directory)
        entries = read_entries(runner, codex, cwd)
        preflight_entries(entries, python)
        runner.run([str(python), str(runner.root / "scripts" / "configure_codex_agents.py")])
        if "catia-v5-inspect" not in entries:
            runner.run([str(codex), "mcp", "add", "catia-v5-inspect", "--",
                        str(python), "-m", "catia_mcp", "--inspection-only"], cwd=cwd)
        verified = read_entries(runner, codex, cwd)
        if "catia-v5-inspect" not in verified:
            raise SetupError("Codex did not retain the inspection registration")
        check_entry(verified["catia-v5-inspect"], python)


def validate_roles(root: Path, python: Path) -> list[str]:
    # Delayed import: dependencies are installed before the first setup call.
    try:
        from scripts.configure_codex_agents import ROLE_ACCESS, tomllib
    except ImportError as exc:
        raise SetupError("TOML support missing. Run INSTALL.cmd first.") from exc
    names = []
    for role, flags in ROLE_ACCESS.items():
        path = root / ".codex" / "agents" / f"{role}.toml"
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
            if data.get("name") != role:
                raise ValueError("Wrong role name")
            for key in ("description", "developer_instructions"):
                if not isinstance(data.get(key), str) or not data[key].strip():
                    raise ValueError(f"Missing {key}")
            servers = data["mcp_servers"]
            for name, enabled, args in (
                ("catia-v5", flags[0], ["-m", "catia_mcp"]),
                ("catia-v5-inspect", flags[1], ["-m", "catia_mcp", "--inspection-only"]),
            ):
                server = servers[name]
                if (server.get("enabled") is not enabled or server.get("args") != args
                        or Path(server.get("command", "")).resolve() != python.resolve()):
                    raise ValueError(f"Wrong transport or access flags: {name}")
            names.append(role)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SetupError(f"Invalid role file {path.name}: {exc}. Run INSTALL.cmd; "
                             "do not copy instructions into a generic agent as a substitute.") from exc
    return names


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
    runner.run([str(python), "-m", "pip", "install", "-e", str(runner.root)], timeout=900)
    runner.run([str(python), str(runner.root / "test_server.py")])
    node, codex = get_runtime(runner, install=True)
    configure_mcp(runner, codex, python)
    # Validate with the venv interpreter, even when bootstrap Python has no tomli.
    state = {"node": str(node) if node else None, "codex": str(codex)}
    (runner.root / ".local" / "windows-runtime.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8")
    runner.run([str(python), str(runner.root / "scripts" / "windows_launcher.py"), "diagnose"])
    runner.say("Setup complete. Open CATIA, then START_CATIA_AI.cmd. "
               "Codex role access and live modeling still require the readiness check.")


def diagnose(runner: Runner, codex: Path) -> None:
    python = runner.root / ".venv" / "Scripts" / "python.exe"
    roles = validate_roles(runner.root, python)
    runner.say("TOML and absolute transports OK: " + ", ".join(roles))
    with tempfile.TemporaryDirectory(prefix="catia-diagnose-") as directory:
        entries = read_entries(runner, codex, Path(directory))
        preflight_entries(entries, python)
        if "catia-v5-inspect" not in entries:
            raise SetupError("Inspection server is not registered. Run INSTALL.cmd.")
    runner.run([str(python), str(runner.root / "scripts" / "check_mcp_transport.py")], timeout=90)
    runner.say("This checks configuration and real stdio discovery only. "
               "CATIA COM and the spawned Codex executor were NOT tested. "
               "No CATIA tool was called. Logs contain local paths; review before sharing.")


def start(runner: Runner, codex: Path) -> int:
    diagnose(runner, codex)
    help_text = runner.run([str(codex), "--help"], private=True).stdout
    argv = [str(codex)]
    # A fresh process avoids reusing a daemon/session with pre-setup config.
    # This is a diagnostic precaution, not a claimed fix for role inheritance.
    if "--no-daemon" in help_text:
        argv.append("--no-daemon")
    argv.extend(["-C", str(runner.root), READINESS_PROMPT])
    runner.say("Starting a fresh Codex readiness session. Sign in if asked; "
               "do not share login codes. No modeling is authorized by this launcher.")
    return subprocess.call(windows_command(argv, runner.env.get("COMSPEC", "cmd.exe")),
                           cwd=runner.root, env=runner.env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "diagnose"])
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
            _, codex = get_runtime(runner, install=False)
            if args.action == "start":
                return start(runner, codex)
            diagnose(runner, codex)
        return 0
    except (SetupError, OSError, ValueError, subprocess.SubprocessError) as exc:
        runner.say(f"STOP: {exc}")
        runner.say("No policy bypass attempted. If Windows blocks this program, contact IT.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
