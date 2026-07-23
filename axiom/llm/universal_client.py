import logging
import json
from typing import Dict, Any, List, Optional
import litellm

logger = logging.getLogger(__name__)

# Suppress overly verbose LiteLLM logs
litellm.suppress_debug_info = True

class UniversalLLMClient:
    """Unified Inference Engine using LiteLLM to route across local and cloud providers."""

    def __init__(self, default_model: str = "ollama/qwen3:8b", fallback_model: str = "ollama/qwen3:8b"):
        self.default_model = default_model
        self.fallback_model = fallback_model
        
        # Keep config object for backward compatibility with OllamaConfig accesses
        class DummyConfig:
            def __init__(self, model):
                self.model = model
        self.config = DummyConfig(default_model)

    def _execute_completion(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Any:
        try:
            return litellm.completion(model=model, messages=messages, **kwargs)
        except (litellm.exceptions.RateLimitError, litellm.exceptions.APIConnectionError) as e:
            if model != self.fallback_model:
                logger.warning(f"Provider error for {model}: {e}. Falling back to {self.fallback_model}")
                if self.fallback_model.startswith("ollama/"):
                    kwargs["api_base"] = "http://localhost:11434"
                return litellm.completion(model=self.fallback_model, messages=messages, **kwargs)
            raise e

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Execute a standard chat completion."""
        # Clean up kwargs that might not be supported by litellm
        timeout = kwargs.pop("timeout", None)
        if timeout:
            kwargs["timeout"] = timeout
            
        # Prioritize dynamically passed model or fallback to config
        model = kwargs.pop("model", self.config.model)
        
        # Ensure litellm knows local Ollama routes if using ollama
        if model.startswith("ollama/"):
            kwargs["api_base"] = "http://localhost:11434"
            
        try:
            response = self._execute_completion(model, messages, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"UniversalLLMClient chat error: {e}")
            return f"Error: {e}"

    def chat_with_tools(self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Execute a tool-enabled chat completion."""
        timeout = kwargs.pop("timeout", None)
        if timeout:
            kwargs["timeout"] = timeout
            
        model = kwargs.pop("model", self.config.model)
        if model.startswith("ollama/"):
            kwargs["api_base"] = "http://localhost:11434"

        # LiteLLM native tools syntax requires list of {"type": "function", "function": schema}
        litellm_tools = []
        for schema in tool_schemas:
            # Check if schema is already wrapped
            if "type" in schema and "function" in schema:
                litellm_tools.append(schema)
            else:
                litellm_tools.append({"type": "function", "function": schema})

        if litellm_tools:
            kwargs["tools"] = litellm_tools

        try:
            response = self._execute_completion(model, messages, **kwargs)
            msg = response.choices[0].message

            parsed_tool_calls = []
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    func = getattr(tc, "function", tc)
                    name = getattr(func, "name", "")
                    arguments_raw = getattr(func, "arguments", "")
                    
                    try:
                        arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                    except Exception:
                        arguments = arguments_raw

                    parsed_tool_calls.append({
                        "name": name,
                        "arguments": arguments
                    })
            
            # Fallback for models that might use legacy function_call
            elif hasattr(msg, "function_call") and msg.function_call:
                func = msg.function_call
                name = getattr(func, "name", "")
                arguments_raw = getattr(func, "arguments", "")
                try:
                    arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
                except Exception:
                    arguments = arguments_raw

                parsed_tool_calls.append({
                    "name": name,
                    "arguments": arguments
                })

            return {
                "content": msg.content or "",
                "tool_calls": parsed_tool_calls
            }

        except Exception as e:
            logger.error(f"UniversalLLMClient chat_with_tools error: {e}")
            return {"content": f"Error: {e}", "tool_calls": []}

    def is_available(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        """List available models from local Ollama and config."""
        models = []
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read().decode())
                for m in data.get("models", []):
                    name = m.get("name")
                    if name:
                        models.append(f"ollama/{name}")
        except Exception as e:
            logger.debug(f"Failed to fetch Ollama models: {e}")
        
        # Add configured models if they are not from Ollama or if Ollama is down
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
