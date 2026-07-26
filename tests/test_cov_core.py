import pytest
import asyncio
import os
import sys
import json
from unittest.mock import MagicMock, AsyncMock, patch

sys.modules["uvicorn"] = MagicMock()

from axiom.core.ipc_server import AxiomDaemon, JSONRPCError
from axiom.core.config_service import initialize_model_config

@pytest.fixture
def mock_cli():
    cli = MagicMock()
    cli.engine = MagicMock()
    cli.engine.is_running.return_value = True
    cli.ollama = MagicMock()
    cli.ollama.is_available.return_value = True
    cli.orchestrator = MagicMock()
    return cli

@pytest.mark.asyncio
async def test_ipc_server_start_stop(mock_cli, tmp_path, monkeypatch):
    monkeypatch.setattr("axiom.core.ipc_server.Path.home", lambda: tmp_path)
    
    daemon = AxiomDaemon(mock_cli)
    assert daemon.token is not None
    
    # Mock servers
    with patch("websockets.serve", new_callable=AsyncMock) as mock_ws:
        with patch("asyncio.start_unix_server", new_callable=AsyncMock) as mock_uds:
            with patch("axiom.core.ipc_server.uvicorn.Server.serve", new_callable=AsyncMock) as mock_http:
                with patch("webbrowser.open_new_tab") as mock_browser:
                    await daemon.start()
                    # Start again should return early
                    await daemon.start()
                    
                    await asyncio.sleep(0.6) # let browser spawn
                    mock_browser.assert_called()
                    
                    await daemon.stop()
                    
@pytest.mark.asyncio
async def test_ipc_server_events(mock_cli, tmp_path, monkeypatch):
    monkeypatch.setattr("axiom.core.ipc_server.Path.home", lambda: tmp_path)
    daemon = AxiomDaemon(mock_cli)
    daemon._is_running = True
    
    event = MagicMock()
    event.name = "test.event"
    event.payload = {"data": 123}
    
    ws_mock = AsyncMock()
    daemon.subscribers[ws_mock] = {"*", "test.event"}
    
    daemon._on_event(event)
    await asyncio.sleep(0.1) # allow dispatch to run
    
    # test _send_safely exception
    ws_mock.send.side_effect = Exception("error")
    await daemon._send_safely(ws_mock, "msg")

@pytest.mark.asyncio
async def test_ipc_server_ws_client(mock_cli, tmp_path, monkeypatch):
    monkeypatch.setattr("axiom.core.ipc_server.Path.home", lambda: tmp_path)
    daemon = AxiomDaemon(mock_cli)
    daemon.token = "valid_token"
    
    class MockWS:
        async def __aiter__(self):
            yield json.dumps({"jsonrpc": "2.0", "method": "axiom.authenticate", "params": {"token": "valid_token"}, "id": 1})
            yield json.dumps({"jsonrpc": "2.0", "method": "axiom.subscribe", "params": {"event_type": "test"}, "id": 2})
            yield json.dumps({"jsonrpc": "2.0", "method": "axiom.status", "id": 3})
            yield json.dumps({"jsonrpc": "2.0", "method": "axiom.prompt", "params": {"text": "hello"}, "id": 4})
            yield json.dumps({"jsonrpc": "2.0", "method": "axiom.stop", "id": 5})
            yield "invalid json"
        async def send(self, msg):
            pass
            
    ws_mock = MockWS()
    
    response = MagicMock()
    response.success = True
    response.output = "hi"
    mock_cli.orchestrator.run.return_value = response
    
    await daemon._handle_ws_client(ws_mock)

@pytest.mark.asyncio
async def test_ipc_server_uds_client(mock_cli, tmp_path, monkeypatch):
    monkeypatch.setattr("axiom.core.ipc_server.Path.home", lambda: tmp_path)
    daemon = AxiomDaemon(mock_cli)
    
    reader = AsyncMock()
    reader.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "method": "axiom.status", "id": 1}).encode("utf-8") + b"\n",
        b"\n",
        json.dumps({"jsonrpc": "2.0", "method": "axiom.stop", "id": 2}).encode("utf-8") + b"\n",
        b""
    ]
    
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    
    with patch.object(daemon, "stop", new_callable=AsyncMock):
        await daemon._handle_uds_client(reader, writer)
