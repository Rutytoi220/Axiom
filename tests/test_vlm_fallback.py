import pytest
from unittest.mock import MagicMock
from axiom.agents.orchestrator_agent import OrchestratorAgent

def test_vlm_empty_response_fallback():
    # Mock LLM Client that returns empty response initially, then succeeds
    mock_llm = MagicMock()
    
    class MockConfig:
        def __init__(self):
            self.model = 'ollama/qwen3-vl:2b'
            
    mock_llm.config = MockConfig()
    
    # Configure mock to return empty on first call, successful on second
    # We're mocking chat() and chat_with_tools() depending on what _call_llm uses
    # _call_llm iterates up to LLM_RETRIES. In our case, the loop will retry with qwen3:8b
    mock_llm.chat_with_tools.side_effect = [
        {"role": "assistant", "content": "", "tool_calls": []}, # Empty first time
        {"role": "assistant", "content": "Success!", "tool_calls": []} # Success second time
    ]
    
    mock_llm.chat.side_effect = [
        "",
        "Success!"
    ]

    agent = OrchestratorAgent(llm=mock_llm)
    
    # Make a direct call to _call_llm to test the retry logic
    messages = [{"role": "user", "content": "hello"}]
    
    # Test without tools
    result = agent._call_llm(messages=messages, tool_schemas=[])
    
    assert result['content'] == 'Success!'
    assert mock_llm.config.model == 'ollama/qwen3:8b'
    assert mock_llm.chat.call_count == 2
    
    # Reset
    mock_llm.chat_with_tools.side_effect = [
        {"role": "assistant", "content": "", "tool_calls": []}, # Empty first time
        {"role": "assistant", "content": "Success with tools!", "tool_calls": [{"name": "foo"}]} # Success second time
    ]
    mock_llm.config.model = 'ollama/qwen3-vl:2b'
    
    # Test with tools
    result = agent._call_llm(messages=messages, tool_schemas=[{"type": "function", "function": {"name": "foo"}}])
    
    assert result['content'] == 'Success with tools!'
    assert result['tool_calls'] == [{"name": "foo"}]
    assert mock_llm.config.model == 'ollama/qwen3:8b'
    assert mock_llm.chat_with_tools.call_count == 2
