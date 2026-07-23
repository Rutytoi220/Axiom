import pytest
import asyncio
import json
import threading
from unittest.mock import AsyncMock, Mock, patch

from axiom.tools.mcp_sse_client import MCPSSEClient
from axiom.tools.mcp_hub import MCPHub

@pytest.mark.asyncio
async def test_mcp_sse_client_handshake():
    mock_client = Mock()
    
    mock_response = AsyncMock()
    mock_response.status_code = 200
    
    async def mock_aiter_lines():
        yield "event: endpoint"
        yield "data: http://test.local/post"
        yield ""
        yield "event: message"
        yield 'data: {"jsonrpc":"2.0","id":1,"result":{}}'
        yield ""
        # Keep alive
        while True:
            await asyncio.sleep(1)
            
    mock_response.aiter_lines = mock_aiter_lines
    
    class AsyncContextManager:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, *args):
            pass
            
    mock_client.stream.return_value = AsyncContextManager()
    
    on_message = Mock()
    on_disconnect = Mock()
    
    client = MCPSSEClient("http://test.local/sse", "remote_test", on_message, on_disconnect)
    client._client = mock_client
    
    # Run connect in background task so we don't block
    task = asyncio.create_task(client.connect())
    
    # Wait until endpoint is discovered
    for _ in range(20):
        if client.post_url:
            break
        await asyncio.sleep(0.1)
        
    assert client.post_url == "http://test.local/post"
    
    # Wait for the message to be processed
    await asyncio.sleep(0.1)
    on_message.assert_called_with({"jsonrpc": "2.0", "id": 1, "result": {}})
    
    client.stop()
    await task

@pytest.mark.asyncio
async def test_mcp_sse_client_send_request():
    mock_client = AsyncMock()
    
    on_message = Mock()
    client = MCPSSEClient("http://test.local/sse", "test", on_message)
    client._client = mock_client
    client.post_url = "http://test.local/post"
    
    mock_post_resp = Mock()
    mock_post_resp.content = b'{"jsonrpc":"2.0","id":2,"result":{"success":true}}'
    mock_post_resp.json.return_value = {"jsonrpc": "2.0", "id": 2, "result": {"success": True}}
    mock_client.post.return_value = mock_post_resp
    
    req = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
    await client.send_request(req)
    
    mock_client.post.assert_called_with("http://test.local/post", json=req)
    on_message.assert_called_with({"jsonrpc": "2.0", "id": 2, "result": {"success": True}})

def test_mcp_hub_sse_integration():
    registry = Mock()
    hub = MCPHub(registry)
    
    with patch("axiom.tools.mcp_hub.MCPSSEClient") as MockSSEClient:
        mock_sse_instance = AsyncMock()
        # Mock connect so it doesn't block
        mock_sse_instance.connect.return_value = None
        
        # When send_request is called, we immediately fulfill the future in the hub by calling on_message
        async def mock_send_request(req):
            if req["method"] == "initialize":
                resp = {"jsonrpc": "2.0", "id": req["id"], "result": {}}
                hub._handle_sse_message("test_server", resp)
            elif req["method"] == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "remote_db_query",
                                "description": "query DB",
                                "inputSchema": {
                                    "properties": {"sql": {"type": "string"}},
                                    "required": ["sql"]
                                }
                            }
                        ]
                    }
                }
                hub._handle_sse_message("test_server", resp)
                
        mock_sse_instance.send_request.side_effect = mock_send_request
        MockSSEClient.return_value = mock_sse_instance
        
        with patch("axiom.tools.mcp_hub.Path.home") as mock_home:
            import tempfile
            from pathlib import Path
            td = tempfile.TemporaryDirectory()
            mock_home.return_value = Path(td.name)
            # Add server
            hub.add_server("test_server", "http://test.local/sse", [])
            # Check if tool was registered
            assert len(hub.active_tools) == 1
                
        # The hub adds the server and connects, which is somewhat asynchronous but we waited up to 10s.
        # Check if tool was registered
        assert len(hub.active_tools) == 1
        assert hub.active_tools[0] == "test_server_remote_db_query"
        
        status = hub.get_status()
        assert len(status["connected_servers"]) == 1
        assert status["connected_servers"][0]["name"] == "test_server"
        assert status["connected_servers"][0]["type"] == "SSE"

        # Check tool execution
        tool = registry.register_tool.call_args[0][1]
        
        # Now mock the execution response
        async def mock_execute_request(req):
            resp = {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {"content": [{"type": "text", "text": "Query success"}]}
            }
            hub._handle_sse_message("test_server", resp)
            
        mock_sse_instance.send_request.side_effect = mock_execute_request
        
        result = tool.execute(sql="SELECT *")
        assert result["success"] is True
        assert result["output"] == "Query success"
            
        td.cleanup()

    # Cleanup thread
    hub.stop()
