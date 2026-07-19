import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from axiom.sdk.client import AxiomClient
from axiom.sdk.models import TelemetryPayload


@pytest.fixture
def mock_token_file(tmp_path):
    token_path = tmp_path / "daemon.token"
    token_path.write_text("test-token-123")
    return token_path


@pytest.fixture
def mock_socket_file(tmp_path):
    socket_path = tmp_path / "axiom.sock"
    socket_path.touch()
    return socket_path


@pytest.mark.asyncio
async def test_axiom_client_connects_and_authenticates(mock_socket_file, mock_token_file):
    client = AxiomClient(socket_path=mock_socket_file, token_path=mock_token_file)
    
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    
    with patch("asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)) as mock_open:
        await client.connect()
        mock_open.assert_called_once_with(str(mock_socket_file))
        assert client._auth_token == "test-token-123"
        
        await client.disconnect()


@pytest.mark.asyncio
async def test_axiom_client_get_status(mock_socket_file, mock_token_file):
    client = AxiomClient(socket_path=mock_socket_file, token_path=mock_token_file)
    
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    
    # We need to simulate the background read loop responding to our request
    async def mock_readline():
        # Yield once, then hang to simulate open connection
        await asyncio.sleep(0.01)
        
        # We need to extract the ID from the pending request
        if not client._pending_requests:
            await asyncio.sleep(1)
            return b""
            
        req_id = list(client._pending_requests.keys())[0]
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "ram_percent": 45.0,
                "vram_percent": 12.5,
                "tier": "tier1"
            }
        }
        # Clear it so we don't infinite loop with same id
        client._pending_requests.pop(req_id).set_result(response)
        
        # After returning one line, block
        await asyncio.sleep(1)
        return b""
        
    mock_reader.readline.side_effect = mock_readline
    
    with patch("asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)):
        # connect is called implicitly by get_status
        status = await client.get_status()
        
        assert isinstance(status, TelemetryPayload)
        assert status.ram_percent == 45.0
        assert status.vram_percent == 12.5
        assert status.tier == "tier1"
        
        # Verify the auth token was injected into the request
        mock_writer.write.assert_called_once()
        written_bytes = mock_writer.write.call_args[0][0]
        written_json = json.loads(written_bytes.decode().strip())
        assert written_json["method"] == "system.status"
        assert written_json["params"]["token"] == "test-token-123"
        
        await client.disconnect()


@pytest.mark.asyncio
async def test_axiom_client_subscribe(mock_socket_file, mock_token_file):
    client = AxiomClient(socket_path=mock_socket_file, token_path=mock_token_file)
    
    mock_reader = AsyncMock(spec=asyncio.StreamReader)
    mock_writer = AsyncMock(spec=asyncio.StreamWriter)
    
    async def mock_readline():
        # 1. First respond to the subscribe request
        await asyncio.sleep(0.01)
        if client._pending_requests:
            req_id = list(client._pending_requests.keys())[0]
            resp = {"jsonrpc": "2.0", "id": req_id, "result": "ok"}
            client._pending_requests.pop(req_id).set_result(resp)
            
        # 2. Emit a fake event
        await asyncio.sleep(0.01)
        event_payload = {
            "jsonrpc": "2.0",
            "method": "event.bus.published",
            "params": {
                "topic": "swarm.proposal",
                "proposal_id": "prop_123"
            }
        }
        return json.dumps(event_payload).encode() + b"\n"
        
    mock_reader.readline.side_effect = mock_readline
    
    with patch("asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)):
        # Start subscription
        async_gen = client.subscribe("swarm.proposal")
        
        # Get first event
        event = await asyncio.wait_for(async_gen.__anext__(), timeout=1.0)
        
        assert event["topic"] == "swarm.proposal"
        assert event["proposal_id"] == "prop_123"
        
        await client.disconnect()
