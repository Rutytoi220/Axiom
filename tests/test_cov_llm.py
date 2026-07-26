import pytest
from unittest.mock import patch, MagicMock
from axiom.llm.universal_client import UniversalLLMClient
from axiom.llm.ollama_client import OllamaClient, OllamaError, PromptBuilder
import litellm
import urllib.error
import urllib.request
import json

def test_universal_execute_completion_fallback():
    client = UniversalLLMClient(default_model="test1", fallback_model="test2")
    with patch("axiom.llm.universal_client.litellm.completion") as mock_comp:
        mock_comp.side_effect = [litellm.exceptions.RateLimitError("rate limit", llm_provider="test", model="test"), MagicMock()]
        client._execute_completion("test1", [{"role": "user", "content": "hi"}])
        assert mock_comp.call_count == 2
        
        mock_comp.side_effect = [litellm.exceptions.RateLimitError("rate limit", llm_provider="test", model="test"), litellm.exceptions.APIConnectionError("conn", llm_provider="test", model="test")]
        with pytest.raises(litellm.exceptions.APIConnectionError):
            client._execute_completion("test1", [{"role": "user", "content": "hi"}])

def test_universal_chat_error():
    client = UniversalLLMClient()
    with patch("axiom.llm.universal_client.litellm.completion", side_effect=Exception("some error")):
        with pytest.raises(Exception):
            client.chat([{"role": "user", "content": "hi"}], timeout=10)

def test_universal_chat_with_tools_error():
    client = UniversalLLMClient()
    with patch("axiom.llm.universal_client.litellm.completion", side_effect=Exception("some error")):
        with pytest.raises(Exception):
            client.chat_with_tools([{"role": "user", "content": "hi"}], [])

def test_universal_chat_with_tools_schemas_and_parsing():
    client = UniversalLLMClient()
    with patch("axiom.llm.universal_client.litellm.completion") as mock_comp:
        # tool schema conversion
        mock_msg = MagicMock()
        mock_msg.content = "content"
        # msg.tool_calls
        tc = MagicMock()
        tc.function.name = "tool1"
        tc.function.arguments = '{"a": 1}'
        mock_msg.tool_calls = [tc]
        
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=mock_msg)]
        mock_comp.return_value = mock_resp
        
        # passed schema missing 'type'
        res = client.chat_with_tools([{"role": "user"}], [{"name": "tool1"}], timeout=5)
        assert res["tool_calls"][0]["name"] == "tool1"
        
        # function_call fallback
        mock_msg.tool_calls = None
        fc = MagicMock()
        fc.name = "tool2"
        fc.arguments = {"b": 2} # raw dict
        mock_msg.function_call = fc
        res = client.chat_with_tools([{"role": "user"}], [{"type": "function", "function": {"name": "tool2"}}])
        assert res["tool_calls"][0]["name"] == "tool2"

def test_universal_embed():
    client = UniversalLLMClient()
    with patch("axiom.llm.universal_client.litellm.embedding") as mock_emb:
        mock_emb.return_value = MagicMock(data=[{"embedding": [1.0]}])
        assert client.embed("hi") == [1.0]
        
        mock_emb.side_effect = Exception("err")
        assert client.embed("hi") == []

def test_universal_list_models_error():
    client = UniversalLLMClient(default_model="d1", fallback_model="d2")
    with patch("urllib.request.urlopen", side_effect=Exception("err")):
        models = client.list_models()
        assert "d1" in models
        assert "d2" in models
        assert client.is_available() is True
        client._detect_capabilities()
        client.close()

def test_ollama_client_detect_capabilities():
    client = OllamaClient()
    with patch("axiom.llm.ollama_client.urllib.request.urlopen") as mock_urlopen:
        # models
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"models": [{"name": "neural-chat"}]}'
        
        mock_chat_resp = MagicMock()
        mock_chat_resp.read.return_value = b'{}'
        
        mock_urlopen.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_resp)),
            MagicMock(__enter__=MagicMock(return_value=mock_chat_resp))
        ]
        
        client._detect_capabilities()
        assert "neural-chat" in client.capabilities["models"]
        assert client.capabilities["chat"] is True

def test_ollama_client_normalize_model():
    client = OllamaClient()
    assert client.normalize_model("neural-chat") == "neural-chat"
    client.capabilities["models"] = ["neural-chat:latest"]
    assert client.normalize_model("neural-chat") == "neural-chat:latest"

def test_ollama_client_request_errors():
    client = OllamaClient()
    with patch("axiom.llm.ollama_client.urllib.request.urlopen", side_effect=urllib.error.URLError("conn error")):
        with pytest.raises(OllamaError):
            client._request("GET", "/api/tags")
    
    with patch("axiom.llm.ollama_client.urllib.request.urlopen", side_effect=Exception("err")):
        with pytest.raises(OllamaError):
            client._request("GET", "/api/tags")

@pytest.mark.asyncio
async def test_ollama_client_async_methods():
    client = OllamaClient()
    with patch("axiom.llm.ollama_client.OllamaClient.is_available", return_value=True):
        assert await client.is_available_async() is True
    with patch("axiom.llm.ollama_client.OllamaClient.list_models", return_value=[]):
        assert await client.list_models_async() == []
    with patch("axiom.llm.ollama_client.OllamaClient.generate", return_value="hi"):
        assert await client.generate_async("hi") == "hi"
    with patch("axiom.llm.ollama_client.OllamaClient.chat", return_value="hi"):
        assert await client.chat_async([]) == "hi"
    with patch("axiom.llm.ollama_client.OllamaClient.chat_with_tools", return_value={}):
        assert await client.chat_with_tools_async([], []) == {}
    with patch("axiom.llm.ollama_client.OllamaClient.embed", return_value=[1.0]):
        assert await client.embed_async("hi") == [1.0]

def test_ollama_client_chat_with_tools():
    client = OllamaClient()
    with patch("axiom.llm.ollama_client.OllamaClient._request") as mock_req:
        mock_req.return_value = {"message": {"role": "assistant", "content": "hello"}}
        res = client.chat_with_tools([{"role": "user", "content": "hi"}], [{"name": "tool1"}])
        assert res["content"] == "hello"
        
        mock_req.side_effect = Exception("err")
        res = client.chat_with_tools([], [])
        assert "Error: err" in res["content"]

def test_ollama_client_misc():
    client = OllamaClient()
    client.set_model("test")
    assert client.config.model == "test"
    client.close()

def test_prompt_builder():
    builder = PromptBuilder()
    builder.system("system_msg")
    builder.user("user_msg")
    builder.assistant("assistant_msg")
    assert builder.build_raw() == "System: system_msg\nUser: user_msg\nAssistant: assistant_msg"
    builder.build()
    builder.reset()
    assert builder.build_raw() == ""
