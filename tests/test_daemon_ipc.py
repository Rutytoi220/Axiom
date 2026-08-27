import json
import asyncio
import pytest
from unittest.mock import MagicMock

class MockWebSocket:
    def __init__(self):
        self.messages = []
        
    async def send(self, data):
        self.messages.append(data)
        
    async def __aiter__(self):
        yield json.dumps({"action": "reload_plugins"})
        
    @property
    def closed(self):
        return False

@pytest.mark.asyncio
async def test_daemon_reload_plugins():
    cli_mock = MagicMock()
    
    from axiom.server.daemon import DaemonServer
    daemon = DaemonServer(cli_mock)
    
    ws = MockWebSocket()
    await daemon.handle_client(ws)
    
    cli_mock.orchestrator.reload_plugins.assert_called_once()
    assert len(ws.messages) > 0
    response = json.loads(ws.messages[0])
    assert response["action"] == "reload_plugins"
    assert response["success"] is True
