"""Tests for Headless Daemon Mode & JSON-RPC IPC Server."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import websockets

from axiom.core.ipc_server import AxiomDaemon
from axiom.core.events import EventBus, Event

@pytest.fixture
def mock_cli(tmp_path):
    cli = MagicMock()
    
    class MockEngine:
        def __init__(self):
            self.event_bus = EventBus()
        def is_running(self):
            return True
            
        class MockRegistry:
            def list_agents(self):
                return {"a1": 1}
            def list_tools(self):
                return {"t1": 1, "t2": 2}
        registry = MockRegistry()
            
    cli.engine = MockEngine()
    
    class MockOllama:
        def is_available(self):
            return True
    cli.ollama = MockOllama()
    
    class MockOrchestrator:
        def run(self, text):
            class Response:
                success = True
                output = f"Processed: {text}"
            return Response()
            
    cli.orchestrator = MockOrchestrator()
    
    return cli

@pytest.fixture
def override_axiom_dir(tmp_path, monkeypatch):
    import axiom.core.ipc_server
    class PatchedPath:
        @classmethod
        def home(cls):
            return tmp_path
    monkeypatch.setattr(axiom.core.ipc_server, 'Path', PatchedPath)
    return tmp_path

@pytest.mark.asyncio
async def test_websocket_authentication_and_prompt(mock_cli, override_axiom_dir):
    daemon = AxiomDaemon(mock_cli)
    # Patch port to avoid conflicts
    import websockets
    original_serve = websockets.serve
    
    # Start on random port
    import socket
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    
    async def patched_serve(handler, host, p, **kwargs):
        return await original_serve(handler, host, port, **kwargs)
        
    import axiom.core.ipc_server
    axiom.core.ipc_server.websockets.serve = patched_serve
    
    await daemon.start()
    token = daemon.token
    assert token is not None
    
    try:
        # Test WS connection
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Try without auth
            req = {"jsonrpc": "2.0", "method": "axiom.prompt", "params": {"text": "hello"}, "id": 1}
            await ws.send(json.dumps(req))
            resp = json.loads(await ws.recv())
            assert "error" in resp
            assert resp["error"]["code"] == -32001
            
            # Auth
            req_auth = {"jsonrpc": "2.0", "method": "axiom.authenticate", "params": {"token": token}, "id": 2}
            await ws.send(json.dumps(req_auth))
            resp_auth = json.loads(await ws.recv())
            assert resp_auth["result"] == "Authenticated"
            
            # Try prompt again
            req_prompt = {"jsonrpc": "2.0", "method": "axiom.prompt", "params": {"text": "hello"}, "id": 3}
            await ws.send(json.dumps(req_prompt))
            resp_prompt = json.loads(await ws.recv())
            assert resp_prompt["result"] == "Processed: hello"
            
            # Status
            req_status = {"jsonrpc": "2.0", "method": "axiom.status", "id": 4}
            await ws.send(json.dumps(req_status))
            resp_status = json.loads(await ws.recv())
            assert resp_status["result"]["engine_running"] is True
            assert resp_status["result"]["agents"] == 1
    finally:
        await daemon.stop()
        axiom.core.ipc_server.websockets.serve = original_serve

@pytest.mark.asyncio
async def test_websocket_subscribe_events(mock_cli, override_axiom_dir):
    daemon = AxiomDaemon(mock_cli)
    
    # Start on random port
    import socket
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    
    import websockets
    original_serve = websockets.serve
    async def patched_serve(handler, host, p, **kwargs):
        return await original_serve(handler, host, port, **kwargs)
        
    import axiom.core.ipc_server
    axiom.core.ipc_server.websockets.serve = patched_serve
    
    await daemon.start()
    token = daemon.token
    
    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Auth
            req_auth = {"jsonrpc": "2.0", "method": "axiom.authenticate", "params": {"token": token}, "id": 1}
            await ws.send(json.dumps(req_auth))
            await ws.recv() # Consume auth response
            
            # Subscribe
            req_sub = {"jsonrpc": "2.0", "method": "axiom.subscribe", "params": {"event_type": "*"}, "id": 2}
            await ws.send(json.dumps(req_sub))
            resp_sub = json.loads(await ws.recv())
            assert resp_sub["result"] == "Subscribed"
            
            # Publish event
            mock_cli.engine.event_bus.publish(Event("test.event", "test", data={"msg": "hello"}))
            
            # Wait for event notification
            notif = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
            assert notif["method"] == "axiom.event"
            assert notif["params"]["event_type"] == "test.event"
            assert notif["params"]["payload"] == {"msg": "hello"}
            
    finally:
        await daemon.stop()
        axiom.core.ipc_server.websockets.serve = original_serve
