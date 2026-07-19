import pytest
import asyncio
from unittest.mock import patch, MagicMock
from pathlib import Path
from axiom.client.gateway import create_app
from axiom.core.ipc_server import AxiomDaemon

@pytest.fixture
def mock_daemon(tmp_path):
    class MockEngine:
        event_bus = MagicMock()
    class MockCLI:
        engine = MockEngine()
    
    with patch("axiom.core.ipc_server.Path.home") as mock_home:
        mock_home.return_value = tmp_path
        daemon = AxiomDaemon(MockCLI())
        yield daemon

@pytest.mark.asyncio
async def test_gateway_fallback_html_generation(mock_daemon):
    app = create_app(mock_daemon)
    
    # Check if the fallback index.html was created
    gui_dir = mock_daemon.axiom_dir / "gui"
    index_file = gui_dir / "index.html"
    
    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")
    assert "AXIOM GUI Sandbox" in content
    assert "backdrop-filter: blur" in content # Check for glassmorphism CSS
    assert "npm run build" in content

@pytest.mark.asyncio
async def test_daemon_browser_spawn(mock_daemon):
    # We only want to test the _spawn_browser coroutine
    with patch("webbrowser.open_new_tab") as mock_open:
        await mock_daemon._spawn_browser()
        
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        assert "http://127.0.0.1:49103/?token=" in called_url
        assert mock_daemon.token in called_url
