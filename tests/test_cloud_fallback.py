"""Tests for the Hybrid Cloud Fallback Adapter."""

import pytest
import os
from unittest.mock import Mock, patch

from axiom.engine.router import InferenceRouter
from axiom.engine.cloud_adapter import CloudAdapter
from axiom.config import AxiomConfig, set_config


@pytest.fixture
def mock_telemetry():
    telemetry = Mock()
    # Simulate a critical OOM situation
    telemetry.latest_state = {
        "warning": True,
        "ram_available_percent": 10.5
    }
    return telemetry


@pytest.fixture
def mock_llm_client():
    client = Mock()
    client.config.model = "default"
    client.chat.return_value = "local response"
    return client


def test_cloud_adapter_detection():
    # Test OpenAI detection
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key", "ANTHROPIC_API_KEY": ""}):
        adapter = CloudAdapter()
        assert adapter.is_configured
        assert adapter.provider == "openai"
        
    # Test Anthropic detection
    with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "test_key"}):
        adapter = CloudAdapter()
        assert adapter.is_configured
        assert adapter.provider == "anthropic"


@patch('builtins.print')
def test_router_downgrades_to_tier2_when_fallback_disabled(mock_print, mock_llm_client, mock_telemetry):
    # Set fallback to False
    set_config(AxiomConfig(allow_cloud_fallback=False))
    
    # Mock capabilities to avoid TypeError
    mock_llm_client.capabilities = {"models": ["llama3.1:latest", "qwen3-coder:latest", "qwen3:0.6b"]}
    
    router = InferenceRouter(llm_client=mock_llm_client, telemetry_daemon=mock_telemetry)
    
    # Send a Code message (complex, long context)
    messages = [{"role": "user", "content": "refactor this architecture framework"}]
    
    # Route it
    target = router._route_request(messages)
    
    # It should downgrade from code to orchestration
    assert target == router.model_tiers["orchestration"]
    
    # Assert chat works
    response = router.chat(messages)
    assert response == "local response"
    assert mock_llm_client.chat.called


@patch('builtins.print')
def test_router_bursts_to_cloud_when_fallback_enabled(mock_print, mock_llm_client, mock_telemetry):
    # Set fallback to True
    set_config(AxiomConfig(allow_cloud_fallback=True))
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
        router = InferenceRouter(llm_client=mock_llm_client, telemetry_daemon=mock_telemetry)
        
        # We ensure it's configured
        assert router.cloud_adapter.is_configured
        
        # Send a Tier 3 message
        messages = [{"role": "user", "content": "refactor this architecture framework"}]
        
        # Route it
        target = router._route_request(messages)
        
        # It should burst to cloud
        assert target == "cloud"
        
        # The print statement should have been called
        mock_print.assert_any_call("\n[!] Local VRAM exhausted (<15%). Bursting Code task to Cloud Fallback...\n")
        
        # Assert chat routes to cloud mock
        with patch.object(router.cloud_adapter, '_call_mock_for_tests', return_value="cloud response") as mock_cloud:
            response = router.chat(messages)
            assert response == "cloud response"
            assert mock_cloud.called
            
            # Local client should NOT have been called
            mock_llm_client.chat.assert_not_called()
