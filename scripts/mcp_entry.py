"""Start the MCP code from this project, including with isolated embedded Python.

The bundled runtime also contains a pip-installed copy. UPDATE.cmd changes this
project, so importing that older copy would silently undo the user's update.
"""
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    if not (root / "catia_mcp" / "server.py").is_file():
        raise RuntimeError("CATIA MCP source is missing from this project; repair the installation")
    sys.path.insert(0, str(root))
    from catia_mcp.server import main as start_server
    start_server()


if __name__ == "__main__":
    main()
