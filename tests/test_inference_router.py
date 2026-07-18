"""Tests for the Dynamic Inference Router and Hardware Telemetry Daemon."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from axiom.engine.router import InferenceRouter
from axiom.engine.telemetry import HardwareTelemetryDaemon
from axiom.llm.ollama_client import OllamaConfig


class MockOllamaClient:
    def __init__(self):
        self.config = OllamaConfig(model="neural-chat")

    def chat(self, messages, **kwargs):
        return f"Chatted with {self.config.model}"

    def chat_with_tools(self, messages, tool_schemas, **kwargs):
        return f"Chatted with {self.config.model} using tools"


@pytest.fixture
def mock_telemetry():
    daemon = Mock(spec=HardwareTelemetryDaemon)
    daemon.latest_state = {
        "ram_available_percent": 50.0,
        "ollama_vram_bytes": 0,
        "warning": False
    }
    return daemon


@pytest.fixture
def router(mock_telemetry):
    client = MockOllamaClient()
    r = InferenceRouter(client, mock_telemetry)
    return r


def test_classify_tier1(router):
    # Short prompt, no tools -> Tier 1
    messages = [{"role": "user", "content": "Hello"}]
    assert router._classify_task(messages) == "tier1"


def test_classify_tier2(router):
    # Medium prompt, or tools present -> Tier 2
    messages = [{"role": "user", "content": "Hello " * 50}]
    tool_schemas = [{"name": "my_tool"}]
    assert router._classify_task(messages, tool_schemas) == "tier2"


def test_classify_tier3_by_keyword(router):
    # Contains architecture keyword -> Tier 3
    messages = [{"role": "user", "content": "Help me refactor the architecture."}]
    assert router._classify_task(messages) == "tier3"


def test_classify_tier3_by_length(router):
    # Very long prompt -> Tier 3
    messages = [{"role": "user", "content": "long " * 1000}]
    assert router._classify_task(messages) == "tier3"


def test_route_request_normal(router):
    # Tier 2 normal execution
    messages = [{"role": "user", "content": "Medium request." * 50}]
    target = router._route_request(messages, tool_schemas=[{}])
    assert target == router.model_tiers["tier2"]


def test_route_request_emergency_downgrade(router, mock_telemetry):
    # Tier 3 requested, but memory is low
    mock_telemetry.latest_state["warning"] = True
    mock_telemetry.latest_state["ram_available_percent"] = 10.0

    messages = [{"role": "user", "content": "Refactor the architecture of this complex app."}]
    
    # Normally this would be tier 3, but should downgrade to tier 2
    target = router._route_request(messages)
    assert target == router.model_tiers["tier2"]


def test_router_chat_restores_original_model(router):
    messages = [{"role": "user", "content": "Hello"}]
    original_model = router.llm_client.config.model
    
    # Should use tier 1 internally
    result = router.chat(messages)
    
    assert "phi3:mini" in result
    assert router.llm_client.config.model == original_model


def test_router_chat_with_tools_restores_original_model(router):
    messages = [{"role": "user", "content": "Refactor architecture"}]
    original_model = router.llm_client.config.model
    
    result = router.chat_with_tools(messages, [{}])
    
    assert "mixtral:8x7b" in result
    assert router.llm_client.config.model == original_model


@pytest.mark.asyncio
async def test_telemetry_daemon_loop():
    # Test that the daemon properly updates state and emits warning
    bus = Mock()
    daemon = HardwareTelemetryDaemon(bus)
    daemon._poll_interval_seconds = 0.01  # speed up test
    
    with patch("psutil.virtual_memory") as mock_vmem, \
         patch.object(daemon, "_get_ollama_vram_usage", new_callable=AsyncMock) as mock_vram:
        
        # Simulate low memory
        mock_mem = Mock()
        mock_mem.available = 10
        mock_mem.total = 100
        mock_vmem.return_value = mock_mem
        mock_vram.return_value = 1024
        
        # Start the loop manually for one iteration
        daemon._running = True
        task = asyncio.create_task(daemon._monitor_loop())
        await asyncio.sleep(0.05)
        daemon.stop()
        await task
        
        assert daemon.latest_state["warning"] is True
        assert daemon.latest_state["ram_available_percent"] == 10.0
        assert daemon.latest_state["ollama_vram_bytes"] == 1024
        
        # Verify event was published
        bus.publish.assert_called()
        event = bus.publish.call_args[0][0]
        assert event.event_type == "hardware.resource_warning"
        assert event.data["warning"] is True
