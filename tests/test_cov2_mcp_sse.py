import pytest
import asyncio
from axiom.tools.mcp_sse_client import MCPSSEClient

@pytest.fixture
def sse_client():
    def on_msg(msg): pass
    def on_disc(): pass
    return MCPSSEClient("http://test", "test_name", on_msg, on_disc)

@pytest.mark.asyncio
async def test_mcp_sse_client_init(sse_client):
    assert sse_client.url == "http://test"

@pytest.mark.asyncio
async def test_mcp_sse_dispatch_event(sse_client):
    # test endpoint event
    sse_client._dispatch_event('endpoint', 'http://post_url')
    assert sse_client.post_url == 'http://post_url'

    sse_client._dispatch_event('endpoint', '/relative_url')
    assert sse_client.post_url == 'http://test/relative_url'

    # test message event
    messages = []
    sse_client.on_message = lambda x: messages.append(x)
    sse_client._dispatch_event('message', '{"key": "value"}')
    assert messages[0] == {"key": "value"}

    # test bad JSON
    sse_client._dispatch_event('message', '{bad')
    # Should just log error

@pytest.mark.asyncio
async def test_mcp_sse_send_request(sse_client, monkeypatch):
    import httpx
    
    class MockResponse:
        def __init__(self, json_data, status=200):
            self.json_data = json_data
            self.status_code = status
            self.content = b"content"
        def raise_for_status(self):
            if self.status_code >= 400: raise Exception("Error")
        def json(self):
            if self.json_data == "raise":
                import json
                raise json.JSONDecodeError("msg", "doc", 0)
            return self.json_data

    class MockAsyncClient:
        async def post(self, url, json=None):
            if url == "fail": raise Exception("Failed")
            return MockResponse({"resp": "ok"})
            
    sse_client._client = MockAsyncClient()
    
    with pytest.raises(ConnectionError):
        await sse_client.send_request({})

    sse_client.post_url = "http://post_url"
    
    messages = []
    sse_client.on_message = lambda x: messages.append(x)
    await sse_client.send_request({})
    assert messages[0] == {"resp": "ok"}
    
    # Exception handling
    sse_client.post_url = "fail"
    with pytest.raises(Exception):
        await sse_client.send_request({})

@pytest.mark.asyncio
async def test_mcp_sse_listen_loop(sse_client, monkeypatch):
    import httpx
    class MockAiter:
        async def __aiter__(self):
            yield "event: endpoint"
            yield "data: http://post_url"
            yield ""
            yield "event: message"
            yield 'data: {"test": "test"}'
            yield ""
            yield "data: just data"
            yield ""

    class MockStream:
        def __init__(self, *args, **kwargs):
            self.status_code = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        def aiter_lines(self): return MockAiter()

    class MockClient:
        def stream(self, *args, **kwargs):
            return MockStream()

    sse_client._client = MockClient()
    sse_client._running = True
    
    # Run a single iteration of the loop
    async def listen_wrapper():
        task = asyncio.create_task(sse_client._listen_loop())
        await asyncio.sleep(0.1)
        sse_client._running = False
        await asyncio.sleep(0.1)
        
    await listen_wrapper()

@pytest.mark.asyncio
async def test_mcp_sse_cleanup(sse_client):
    await sse_client.cleanup()
    assert not sse_client._running
