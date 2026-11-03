"""Offline means no real CATIA connection, even on a licensed Windows machine."""
import pytest

import catia_mcp.connection as connection


@pytest.fixture(autouse=True)
def disable_live_com(monkeypatch, tmp_path):
    monkeypatch.setattr(connection, "HAS_COM", False)
    monkeypatch.setenv("CATIA_AI_DATA_DIR", str(tmp_path / "offline-tool-gaps"))
    # A contract test can explicitly replace both pywin32 and this flag with
    # doubles. Merely having CATIA/pywin32 installed never enables COM here.
