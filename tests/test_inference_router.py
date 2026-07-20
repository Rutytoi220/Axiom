"""Tests for InferenceRouter heuristics."""

import pytest
from unittest.mock import Mock
from axiom.engine.router import InferenceRouter

@pytest.fixture
def mock_client():
    client = Mock()
    client.capabilities = {"models": ["qwen3:0.6b", "qwen3:8b", "llama3.1:latest", "qwen3-coder:latest"]}
    client.config = Mock()
    client.config.model = "default"
    return client

def test_classify_chat(mock_client):
    router = InferenceRouter(mock_client)
    
    messages = [{"role": "user", "content": "who are you"}]
    tool_schemas = [{"function": {"name": "write_to_file"}}]
    intent = router._classify_task(messages, tool_schemas)
    assert intent == "chat"

def test_classify_tools_query(mock_client):
    router = InferenceRouter(mock_client)
    
    messages = [{"role": "user", "content": "what tools do you have?"}]
    tool_schemas = [{"function": {"name": "write_to_file"}}]
    intent = router._classify_task(messages, tool_schemas)
    assert intent == "orchestration"

def test_classify_code(mock_client):
    router = InferenceRouter(mock_client)
    messages = [{"role": "user", "content": "write a python script"}]
    tool_schemas = [{"function": {"name": "write_to_file"}}]
    intent = router._classify_task(messages, tool_schemas)
    assert intent == "code"

def test_classify_orchestration(mock_client):
    router = InferenceRouter(mock_client)
    # Long text with no code keywords
    messages = [{"role": "user", "content": "hello " * 20}]
    intent = router._classify_task(messages, None)
    assert intent == "orchestration"

def test_classify_short_path_override(mock_client):
    router = InferenceRouter(mock_client)
    # Short text, but contains a path
    messages = [{"role": "user", "content": "what's in /home/user/doc.pdf"}]
    intent = router._classify_task(messages, None)
    assert intent == "orchestration"

def test_classify_short_tool_verb_override(mock_client):
    router = InferenceRouter(mock_client)
    # Short text, but contains tool verb
    messages = [{"role": "user", "content": "read test.pdf"}]
    intent = router._classify_task(messages, None)
    intent = router._classify_task(messages, None)
    assert intent == "orchestration"

def test_route_request_models(mock_client):
    router = InferenceRouter(mock_client)
    
    # Test chat model
    msg_chat = [{"role": "user", "content": "who are you"}]
    model = router._route_request(msg_chat)
    assert model == "qwen3:0.6b"
    
    # Test orchestration model
    msg_orch = [{"role": "user", "content": "read test.pdf"}]
    model = router._route_request(msg_orch)
    assert model == "qwen3:8b"
    
    # Test code model
    msg_code = [{"role": "user", "content": "write a python script"}]
    model = router._route_request(msg_code)
    assert model == "qwen3-coder:latest"

def test_classify_capability_query(mock_client):
    router = InferenceRouter(mock_client)
    messages = [{"role": "user", "content": "what can you do?"}]
    intent = router._classify_task(messages, None)
    assert intent == "orchestration"
