import pytest
from unittest.mock import patch, MagicMock
from axiom.llm.universal_client import UniversalLLMClient
import litellm

@patch("axiom.llm.universal_client.litellm.completion")
def test_chat_success(mock_completion):
    mock_msg = MagicMock()
    mock_msg.message.content = "Hello there"
    mock_response = MagicMock()
    mock_response.choices = [mock_msg]
    mock_completion.return_value = mock_response

    client = UniversalLLMClient(default_model="ollama/qwen3:8b")
    res = client.chat([{"role": "user", "content": "hi"}])
    assert res == "Hello there"
    mock_completion.assert_called_with(model="ollama/qwen3:8b", messages=[{"role": "user", "content": "hi"}], api_base="http://localhost:11434")

@patch("axiom.llm.universal_client.litellm.completion")
def test_chat_fallback(mock_completion):
    mock_msg = MagicMock()
    mock_msg.message.content = "Fallback success"
    mock_response = MagicMock()
    mock_response.choices = [mock_msg]
    
    # First call fails with RateLimitError, second call succeeds
    mock_completion.side_effect = [
        litellm.exceptions.RateLimitError(message="Rate limited", llm_provider="openai", model="gpt-4o"),
        mock_response
    ]

    client = UniversalLLMClient(fallback_model="ollama/qwen3:8b")
    res = client.chat([{"role": "user", "content": "hi"}], model="openai/gpt-4o")
    
    assert res == "Fallback success"
    assert mock_completion.call_count == 2
    mock_completion.assert_called_with(model="ollama/qwen3:8b", messages=[{"role": "user", "content": "hi"}], api_base="http://localhost:11434")

@patch("urllib.request.urlopen")
def test_list_models(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"models": [{"name": "qwen3:8b"}, {"name": "llama3:latest"}]}'
    
    # Enter context manager
    mock_urlopen.return_value.__enter__.return_value = mock_response

    client = UniversalLLMClient(default_model="ollama/qwen3:8b", fallback_model="ollama/qwen3:8b")
    models = client.list_models()
    
    assert "ollama/qwen3:8b" in models
    assert "ollama/llama3:latest" in models
