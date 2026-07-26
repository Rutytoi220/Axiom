import logging
import json
from typing import Dict, Any, List, Optional
import litellm
logger = logging.getLogger(__name__)
litellm.suppress_debug_info = True

class UniversalLLMClient:
    """Unified Inference Engine using LiteLLM to route across local and cloud providers."""

    def __init__(self, default_model: str='ollama/qwen3:8b', fallback_model: str='ollama/qwen3:8b'):
        """Auto-generated docstring.

Args:
    default_model: Argument.
    fallback_model: Argument.

Returns:
    Return value.
"""
        self.default_model = default_model
        self.fallback_model = fallback_model

        class DummyConfig:
            """Auto-generated docstring.

"""

            def __init__(self, model):
                """Auto-generated docstring.

Args:
    model: Argument.

Returns:
    Return value.
"""
                self.model = model
        self.config = DummyConfig(default_model)

    def _execute_completion(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """Auto-generated docstring.

Args:
    model: Argument.
    messages: Argument.

Returns:
    Return value.
"""
        try:
            return litellm.completion(model=model, messages=messages, **kwargs)
        except (litellm.exceptions.RateLimitError, litellm.exceptions.APIConnectionError) as e:
            if model != self.fallback_model:
                logger.warning(f'Provider error for {model}: {e}. Falling back to {self.fallback_model}')
                if self.fallback_model.startswith('ollama/'):
                    kwargs['api_base'] = 'http://localhost:11434'
                return litellm.completion(model=self.fallback_model, messages=messages, **kwargs)
            raise e

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Execute a standard chat completion."""
        timeout = kwargs.pop('timeout', None)
        if timeout:
            kwargs['timeout'] = timeout
        model = kwargs.pop('model', self.config.model)
        if model.startswith('ollama/'):
            kwargs['api_base'] = 'http://localhost:11434'
        try:
            response = self._execute_completion(model, messages, **kwargs)
            return response.choices[0].message.content or ''
        except Exception as e:
            logger.error(f'UniversalLLMClient chat error: {e}')
            raise e

    def chat_with_tools(self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Execute a tool-enabled chat completion."""
        timeout = kwargs.pop('timeout', None)
        if timeout:
            kwargs['timeout'] = timeout
        model = kwargs.pop('model', self.config.model)
        if model.startswith('ollama/'):
            kwargs['api_base'] = 'http://localhost:11434'
        litellm_tools = []
        for schema in tool_schemas:
            if 'type' in schema and 'function' in schema:
                litellm_tools.append(schema)
            else:
                litellm_tools.append({'type': 'function', 'function': schema})
        if litellm_tools:
            kwargs['tools'] = litellm_tools
        try:
            response = self._execute_completion(model, messages, **kwargs)
            msg = response.choices[0].message
            parsed_tool_calls = []
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    func = getattr(tc, 'function', tc)
                    name = getattr(func, 'name', '')
                    arguments_raw = getattr(func, 'arguments', '')
                    try:
                        arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                    except Exception:
                        arguments = arguments_raw
                    parsed_tool_calls.append({'name': name, 'arguments': arguments})
            elif hasattr(msg, 'function_call') and msg.function_call:
                func = msg.function_call
                name = getattr(func, 'name', '')
                arguments_raw = getattr(func, 'arguments', '')
                try:
                    arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                except Exception:
                    arguments = arguments_raw
                parsed_tool_calls.append({'name': name, 'arguments': arguments})
            return {'content': msg.content or '', 'tool_calls': parsed_tool_calls}
        except Exception as e:
            logger.error(f'UniversalLLMClient chat_with_tools error: {e}')
            raise e

    def is_available(self) -> bool:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return True

    def list_models(self) -> List[str]:
        """List available models from local Ollama and config."""
        models = []
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request('http://localhost:11434/api/tags', method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                for m in data.get('models', []):
                    name = m.get('name')
                    if name:
                        models.append(f'ollama/{name}')
        except Exception as e:
            logger.debug(f'Failed to fetch Ollama models: {e}')
        if self.default_model not in models:
            models.append(self.default_model)
        if self.fallback_model not in models and self.fallback_model != self.default_model:
            models.append(self.fallback_model)
        return models

    def _detect_capabilities(self):
        """Stub for backward compatibility with OllamaClient."""
        pass

    def close(self):
        """Stub for backward compatibility with OllamaClient."""
        pass

    def embed(self, text: str, model: str = "ollama/nomic-embed-text") -> List[float]:
        """Compute embeddings for a string."""
        try:
            api_base = 'http://localhost:11434' if model.startswith('ollama/') else None
            response = litellm.embedding(model=model, input=[text], api_base=api_base)
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(f'Embedding failed: {e}')
            return []
