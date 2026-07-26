import pytest
import json
import asyncio
from axiom.tools.mcp_hub import MCPHub
from unittest.mock import Mock
import subprocess

@pytest.fixture
def registry():
    return Mock()

@pytest.fixture
def mcp_hub(registry, tmp_path, monkeypatch):
    import pathlib
    def mock_home(): return tmp_path
    monkeypatch.setattr(pathlib.Path, "home", mock_home)
    (tmp_path / ".axiom").mkdir()
    hub = MCPHub(registry)
    return hub

def test_mcp_hub_stop(mcp_hub, monkeypatch):
    client = Mock()
    mcp_hub._sse_clients = {"test": client}
    mcp_hub.stop()

def test_mcp_hub_load_servers(mcp_hub):
    config = {'mcpServers': {'test': {'command': 'test', 'args': []}}}
    mcp_hub.config_path.write_text(json.dumps(config))
    mcp_hub.load_servers()

def test_mcp_hub_add_server(mcp_hub):
    mcp_hub.config_path.write_text("{}")
    res = mcp_hub.add_server("sse", "http://test", [])
    assert res
    
    mcp_hub.config_path.write_text("{bad")
    res = mcp_hub.add_server("err", "err", [])
    assert not res

def test_mcp_hub_get_status(mcp_hub):
    mcp_hub.servers = {}
    class MockProcess(subprocess.Popen):
        def __init__(self): pass
        def poll(self): return None
    class MockSSE:
        _running = True
    mcp_hub.servers['stdio'] = MockProcess()
    mcp_hub.servers['sse'] = MockSSE()
    status = mcp_hub.get_status()
    assert len(status['connected_servers']) == 2

def test_mcp_hub_futures(mcp_hub):
    fut = mcp_hub._register_future(1)
    mcp_hub._pending_requests[1] = fut
    mcp_hub._handle_sse_message("test", {'id': 1, 'result': 'ok'})
    assert fut.result() == {'id': 1, 'result': 'ok'}
    
    mcp_hub._handle_sse_message("test", {'method': 'notif'})

@pytest.mark.asyncio
async def test_mcp_hub_sse_connect(mcp_hub, monkeypatch):
    import concurrent.futures
    class MockClient:
        def __init__(self, *args): pass
        async def connect(self): pass
        async def send_request(self, req): pass
        def stop(self): pass
        
    monkeypatch.setattr("axiom.tools.mcp_hub.MCPSSEClient", MockClient)
    
    def mock_reg_fut(req_id):
        fut = concurrent.futures.Future()
        if req_id == mcp_hub._request_id_counter:
            fut.set_result({'result': {'tools': [{'name': 'test_tool', 'description': 'desc'}]}})
        else:
            fut.set_result(True)
        return fut
    mcp_hub._register_future = mock_reg_fut
    
    mcp_hub.connect_sse("test_sse", "http://test")
    
    class MockReg:
        def add_tool(self, tool): self.tool = tool
    mcp_hub.registry = MockReg()
    client = MockClient()
    mcp_hub._register_mcp_tool_sse("test_sse", {'name': 't2'}, client)
    t2 = mcp_hub.registry.tool
    
    assert 't2' in t2.tool_id
    t2.get_info()
    
    def mock_reg_fut2(req_id):
        fut = concurrent.futures.Future()
        fut.set_result({'result': {'content': [{'type': 'text', 'text': 'ok'}]}})
        return fut
    mcp_hub._register_future = mock_reg_fut2
    res = t2.execute()
    assert res.get('success')

    def mock_reg_fut3(req_id):
        fut = concurrent.futures.Future()
        fut.set_result({'error': 'bad'})
        return fut
    mcp_hub._register_future = mock_reg_fut3
    res = t2.execute()
    assert not res.get('success')

    def mock_reg_fut4(req_id):
        fut = concurrent.futures.Future()
        return fut
    mcp_hub._register_future = mock_reg_fut4
    def mock_result(timeout=None): raise concurrent.futures.TimeoutError()
    fut4 = mcp_hub._register_future(99)
    fut4.result = mock_result
    mcp_hub._register_future = lambda r: fut4
    res = t2.execute()
    assert not res.get('success')

def test_mcp_hub_stdio_execute_error(mcp_hub):
    class MockProcess:
        class MockStdin:
            def write(self, *args): pass
            def flush(self): pass
        class MockStdout:
            def readline(self):
                return '{"error": "failed"}'
        stdin = MockStdin()
        stdout = MockStdout()
        
    class MockReg:
        def register_tool(self, id, tool): self.tool = tool
    mcp_hub.registry = MockReg()
    
    mcp_hub._register_mcp_tool("test_stdio", {'name': 't1'}, MockProcess())
    t1 = mcp_hub.registry.tool
    res = t1.execute()
    assert not res.get('success')
