import pytest
from fastapi.testclient import TestClient
from axiom.client.gateway import create_app
import json

class MockRegistry:
    def list_agents(self):
        return []
    def list_tools(self):
        return []
    def list_plugins(self):
        return []

class MockEventBus:
    def __init__(self):
        self.handlers = []
        
    def subscribe(self, event_pattern, handler):
        self.handlers.append(handler)
        
    def unsubscribe(self, event_pattern, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)
            
    def emit(self, event):
        for h in self.handlers:
            h(event)

class MockEngine:
    def __init__(self):
        self.event_bus = MockEventBus()
        self.registry = MockRegistry()
        self._running = True
        
    def is_running(self):
        return self._running

class MockDaemon:
    def __init__(self):
        self.token = "test-token-123"
        self.engine = MockEngine()

class DummyEvent:
    def __init__(self, name, payload):
        self.name = name
        self.payload = payload

@pytest.fixture
def test_client():
    daemon = MockDaemon()
    app = create_app(daemon)
    return TestClient(app), daemon

def test_get_index(test_client):
    client, _ = test_client
    response = client.get("/")
    assert response.status_code == 200
    assert "AXIOM GUI Sandbox" in response.text

def test_api_status_unauthorized(test_client):
    client, _ = test_client
    response = client.get("/api/status")
    assert response.status_code == 401

def test_api_status_authorized(test_client):
    client, daemon = test_client
    response = client.get("/api/status", headers={"Authorization": f"Bearer {daemon.token}"})
    assert response.status_code == 200
    data = response.json()
    assert "ram_percent" in data
    assert data["engine_running"] is True

def test_websocket_events(test_client):
    client, daemon = test_client
    with client.websocket_connect(f"/ws/events?token={daemon.token}") as websocket:
        # Inject an event
        daemon.engine.event_bus.emit(DummyEvent("swarm.proposal", {"proposal_id": 42}))
        
        # Receive the event
        data = websocket.receive_text()
        parsed = json.loads(data)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "axiom.event"
        assert parsed["params"]["event_type"] == "swarm.proposal"
        assert parsed["params"]["payload"]["proposal_id"] == 42
