"""Test suite for axiom.llm.ollama_client (OllamaClient, OllamaConfig).

Mocks urllib.request.urlopen so these tests never require a live Ollama
server, while still exercising the client's real request/response handling,
error translation, and graceful-degradation contracts.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from axiom.llm.ollama_client import OllamaClient, OllamaConfig, OllamaError


def _mock_response(payload: dict):
    """Build a mock matching the `with urlopen(...) as resp:` usage."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = response
    context_manager.__exit__.return_value = False
    return context_manager


class TestOllamaConfig:
    def test_defaults(self):
        config = OllamaConfig()

        assert config.base_url == "http://localhost:11434"
        assert config.model == "neural-chat"
        assert config.temperature == 0.7

    def test_custom_values(self):
        config = OllamaConfig(base_url="http://example:1234", model="mistral", temperature=0.1)

        assert config.base_url == "http://example:1234"
        assert config.model == "mistral"
        assert config.temperature == 0.1


class TestIsAvailable:
    def test_returns_true_when_server_responds(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=_mock_response({"models": []})):
            assert client.is_available() is True

    def test_returns_false_on_connection_error_without_raising(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.is_available() is False


class TestListModels:
    def test_returns_model_names(self):
        client = OllamaClient()
        payload = {"models": [{"name": "llama3"}, {"name": "mistral"}]}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            assert client.list_models() == ["llama3", "mistral"]

    def test_skips_malformed_entries(self):
        client = OllamaClient()
        payload = {"models": [{"name": "llama3"}, {"no_name": True}, "not-a-dict"]}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            assert client.list_models() == ["llama3"]

    def test_returns_empty_list_on_error(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.list_models() == []


class TestGenerate:
    def test_returns_response_text(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=_mock_response({"response": "hello"})):
            assert client.generate("prompt") == "hello"

    def test_http_error_raises_ollama_error(self):
        client = OllamaClient()
        http_error = urllib.error.HTTPError("url", 500, "Internal Error", {}, None)
        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(OllamaError, match="HTTP 500"):
                client.generate("prompt")

    def test_connection_error_raises_ollama_error(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(OllamaError, match="Connection failed"):
                client.generate("prompt")


class TestChat:
    def test_returns_message_content(self):
        client = OllamaClient()
        payload = {"message": {"role": "assistant", "content": "hi there"}}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)):
            assert client.chat([{"role": "user", "content": "hi"}]) == "hi there"

    def test_http_error_raises_ollama_error(self):
        client = OllamaClient()
        http_error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(OllamaError):
                client.chat([{"role": "user", "content": "hi"}])


class TestChatWithTools:
    def test_returns_full_assistant_message(self):
        client = OllamaClient()
        payload = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "shell", "arguments": {}}}],
            }
        }
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)) as mocked:
            result = client.chat_with_tools([{"role": "user", "content": "run ls"}], tools=[{"type": "function"}])

        assert result["tool_calls"][0]["function"]["name"] == "shell"
        # Verify the request payload actually included the tools list.
        sent_request = mocked.call_args[0][0]
        sent_body = json.loads(sent_request.data.decode())
        assert sent_body["tools"] == [{"type": "function"}]

    def test_omits_tools_key_when_none(self):
        client = OllamaClient()
        payload = {"message": {"role": "assistant", "content": "ok"}}
        with patch("urllib.request.urlopen", return_value=_mock_response(payload)) as mocked:
            client.chat_with_tools([{"role": "user", "content": "hi"}], tools=[])

        sent_request = mocked.call_args[0][0]
        sent_body = json.loads(sent_request.data.decode())
        assert "tools" not in sent_body

    def test_connection_error_raises_ollama_error(self):
        """_request() translates all failures into OllamaError, and
        chat_with_tools re-raises it (consistent with chat()/generate())."""
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(OllamaError, match="Connection failed"):
                client.chat_with_tools([{"role": "user", "content": "hi"}], tools=[])


class TestEmbed:
    def test_returns_embedding_vector(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", return_value=_mock_response({"embedding": [0.1, 0.2]})):
            assert client.embed("some text") == [0.1, 0.2]

    def test_returns_empty_list_on_error(self):
        client = OllamaClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert client.embed("some text") == []


class TestSetModel:
    def test_set_model_updates_config(self):
        client = OllamaClient()

        client.set_model("mistral")

        assert client.config.model == "mistral"


class TestClose:
    def test_close_does_not_raise(self):
        """Regression test: close() previously referenced a nonexistent
        self._session attribute and always raised AttributeError."""
        client = OllamaClient()

        client.close()  # Must not raise.

    def test_close_is_safe_to_call_multiple_times(self):
        client = OllamaClient()

        client.close()
        client.close()
