import pytest
from unittest.mock import patch, MagicMock
from axiom.engine.router import SmartRouter, IntentCategory, RouterDecision
from axiom.llm.universal_client import UniversalLLMClient

@patch("axiom.engine.router.litellm.completion")
def test_smart_router_code_classification(mock_completion):
    mock_msg = MagicMock()
    mock_msg.message.content = '{"category": "CODE"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_msg]
    mock_completion.return_value = mock_response
    
    llm = UniversalLLMClient()
    router = SmartRouter(llm_client=llm)
    
    intent = router._classify_task([{"role": "user", "content": "Write a python script"}])
    assert intent == IntentCategory.CODE
    
    # Verify routing selects correct model
    target = router._route_request([{"role": "user", "content": "Write a python script"}])
    assert target == "ollama/qwen3-coder:latest"

@patch("axiom.engine.router.litellm.completion")
def test_smart_router_chat_classification(mock_completion):
    mock_msg = MagicMock()
    mock_msg.message.content = '{"category": "CHAT"}'
    mock_response = MagicMock()
    mock_response.choices = [mock_msg]
    mock_completion.return_value = mock_response
    
    llm = UniversalLLMClient()
    router = SmartRouter(llm_client=llm)
    
    intent = router._classify_task([{"role": "user", "content": "Hello!"}])
    assert intent == IntentCategory.CHAT
    
    target = router._route_request([{"role": "user", "content": "Hello!"}])
    assert target == "ollama/llama3.1:latest"

def test_smart_router_vision_fallback():
    llm = UniversalLLMClient()
    router = SmartRouter(llm_client=llm)
    
    # Should short-circuit to vision when image payload is present
    intent = router._classify_task([
        {"role": "user", "content": [
            {"type": "text", "text": "What is this?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]}
    ])
    assert intent == IntentCategory.VISION

@patch("axiom.engine.router.litellm.completion")
def test_smart_router_error_fallback(mock_completion):
    # Simulate a crash in litellm
    mock_completion.side_effect = Exception("API Down")
    
    llm = UniversalLLMClient()
    router = SmartRouter(llm_client=llm)
    
    intent = router._classify_task([{"role": "user", "content": "do something"}])
    assert intent == IntentCategory.SYSTEM
