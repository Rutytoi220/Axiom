import pytest
import asyncio
import json
import httpx
from axiom.tools.mcp_hub import MCPHub
from unittest.mock import MagicMock
import concurrent.futures
import pathlib

@pytest.mark.asyncio
async def test_mcp_hub_load_config_exception(tmp_path, monkeypatch):
    hub = MCPHub(registry=MagicMock())
    hub.config_path = tmp_path / "mcp.json"
    def mock_read_text(*args, **kwargs): raise Exception("fail")
    monkeypatch.setattr(pathlib.Path, "read_text", mock_read_text)
    hub.load_servers()

@pytest.mark.asyncio
async def test_mcp_hub_sse_exceptions(monkeypatch):
    registry = MagicMock()
    hub = MCPHub(registry=registry)
    
    class MockClient:
        def __init__(self, *args): pass
        async def connect(self): raise httpx.ConnectError("fail")
    monkeypatch.setattr("axiom.tools.mcp_hub.MCPSSEClient", MockClient)
    hub.connect_sse("test", "http://test")
    
    class MockClient2:
        def __init__(self, *args):
            self.on_disconnect = args[3]
        async def connect(self): raise Exception("fail")
    monkeypatch.setattr("axiom.tools.mcp_hub.MCPSSEClient", MockClient2)
    hub.connect_sse("test2", "http://test2")

    class MockClient3:
        def __init__(self, *args):
            self.on_disconnect = args[3]
        async def connect(self): pass
        async def send_request(self, *args): pass
    monkeypatch.setattr("axiom.tools.mcp_hub.MCPSSEClient", MockClient3)
    
    # We need to not hang on future, so we mock wrap_future and future
    def mock_wrap_future(*args): return asyncio.Future()
    # Or just let it timeout
    hub.connect_sse("test3", "http://test3")
    
    if "test3" in hub.servers:
        hub.servers["test3"].on_disconnect()
        assert "test3" not in hub.servers

@pytest.mark.asyncio
async def test_mcp_hub_sse_dynamic_tool_exceptions(monkeypatch):
    registry = MagicMock()
    del registry.register_tool
    registry.add_tool = MagicMock()
    hub = MCPHub(registry=registry)
    
    class MockClient:
        async def send_request(self, req):
            raise Exception("fail")
    
    hub._register_mcp_tool_sse("test", {"name": "test_tool", "description": "desc"}, MockClient())
    
    tool = registry.add_tool.call_args[0][0]
    res = tool.execute(arg=1) 
    assert not res['success']
    assert 'fail' in res['error']

    class MockClientTimeout:
        async def send_request(self, req): pass
    
    hub._register_mcp_tool_sse("test2", {"name": "test_tool2"}, MockClientTimeout())
    tool2 = registry.add_tool.call_args[0][0]
    
    def mock_result(*args, **kwargs): raise concurrent.futures.TimeoutError()
    monkeypatch.setattr(concurrent.futures.Future, "result", mock_result)
    res2 = tool2.execute(arg=1)
    assert not res2['success']
    assert 'Timeout' in res2['error']

def test_mcp_hub_stdio_exceptions(monkeypatch):
    registry = MagicMock()
    hub = MCPHub(registry=registry)
    
    def mock_popen(*args, **kwargs):
        raise Exception("popen fail")
    monkeypatch.setattr("subprocess.Popen", mock_popen)
    
    hub.connect_stdio("test", "testcmd", [])

    del registry.register_tool
    registry.add_tool = MagicMock()
    
    class MockProcess:
        class stdin:
            @staticmethod
            def write(*args): raise Exception("stdin fail")
            @staticmethod
            def flush(): pass
    
    hub._register_mcp_tool("test", {"name": "test_tool"}, MockProcess())
    tool = registry.add_tool.call_args[0][0]
    res = tool.execute(arg=1)
    assert not res['success']
    assert 'fail' in res['error']
