"""Pytest configuration and shared fixtures for AXIOM."""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

def pytest_configure(config):
    """Pytest configuration hook."""
    pass

@pytest.fixture(autouse=True)
def mock_home_directory(monkeypatch):
    """Ensure tests never write to actual ~/.local or ~/.config by mocking Path.home()"""
    with tempfile.TemporaryDirectory() as temp_home:
        # We must mock it where it's used, but setting HOME env var often helps too
        monkeypatch.setenv("HOME", temp_home)
        monkeypatch.setenv("USERPROFILE", temp_home) # Windows
        monkeypatch.setenv("XDG_CONFIG_HOME", os.path.join(temp_home, ".config"))
        monkeypatch.setenv("XDG_DATA_HOME", os.path.join(temp_home, ".local", "share"))
        
        with patch("pathlib.Path.home", return_value=Path(temp_home)):
            yield temp_home

@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    return orchestrator

@pytest.fixture
def mock_gui_bridge():
    bridge = MagicMock()
    return bridge
