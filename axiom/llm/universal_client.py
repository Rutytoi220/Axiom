import logging
import json
from typing import Dict, Any, List, Optional
import litellm
from axiom.engine.inference_scheduler import get_scheduler
from axiom.llm.federation_client import HybridFederationClient

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
        self.federation = HybridFederationClient()

    def _execute_completion(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """Auto-generated docstring."""
        images = kwargs.pop('images', None)
        if images:
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    orig_content = msg.get('content', '')
                    new_content = []
                    if isinstance(orig_content, str):
                        new_content.append({'type': 'text', 'text': orig_content})
                    elif isinstance(orig_content, list):
                        new_content.extend(orig_content)
                        
                    for img in images:
                        b64_str = img if img.startswith('data:') else f"data:image/png;base64,{img}"
                        new_content.append({'type': 'image_url', 'image_url': {'url': b64_str}})
                        
                    msg['content'] = new_content
                    break

        priority = kwargs.pop('priority', 0)  # Default priority is 0 (Critical/Real-time)
        scheduler = get_scheduler()

        def _do_completion():
            try:
                return litellm.completion(model=model, messages=messages, **kwargs)
            except (litellm.exceptions.RateLimitError, litellm.exceptions.APIConnectionError) as e:
                if model != self.fallback_model:
                    logger.warning(f'Provider error for {model}: {e}. Falling back to {self.fallback_model}')
                    if self.fallback_model.startswith('ollama/'):
                        try:
                            from axiom.core.swarm_router import SwarmRouter
                            kwargs['api_base'] = SwarmRouter.instance().get_ollama_base_url()
                        except Exception:
                            kwargs['api_base'] = 'http://localhost:11434'
                    return litellm.completion(model=self.fallback_model, messages=messages, **kwargs)
                raise e

        def _streaming_generator():
            with scheduler.priority_lock(priority):
                response = _do_completion()
                for chunk in response:
                    yield chunk

        if kwargs.get('stream'):
            return _streaming_generator()
        else:
            with scheduler.priority_lock(priority):
                return _do_completion()

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Execute a standard chat completion."""
        timeout = kwargs.pop('timeout', None)
        if timeout:
            kwargs['timeout'] = timeout
        model = kwargs.pop('model', self.config.model)
        
        if '/' not in model and model != 'cloud':
            model = f"ollama/{model}"
            
        if model.startswith('claude-3-5') or model == 'cloud':
            if self.federation.is_configured:
                # We have to run it via the async wrapper
                import asyncio
                return asyncio.run(self.federation.chat_async(messages, **kwargs))
            else:
                logger.warning("Cloud model requested but federation is not configured. Falling back to local.")
                model = self.fallback_model
                if '/' not in model:
                    model = f"ollama/{model}"
                
        if model.startswith('ollama/'):
            try:
                from axiom.core.swarm_router import SwarmRouter
                kwargs['api_base'] = SwarmRouter.instance().get_ollama_base_url()
            except Exception:
                kwargs['api_base'] = 'http://localhost:11434'
            
        stream_callback = kwargs.pop('stream_callback', None)
        if stream_callback:
            kwargs['stream'] = True

        try:
            response = self._execute_completion(model, messages, **kwargs)
            if stream_callback:
                full_text = []
                for chunk in response:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", "") or ""
                    if content:
                        full_text.append(content)
                        stream_callback(content)
                return "".join(full_text)
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
        
        if '/' not in model and model != 'cloud':
            model = f"ollama/{model}"
            
        if model.startswith('ollama/'):
            try:
                from axiom.core.swarm_router import SwarmRouter
                kwargs['api_base'] = SwarmRouter.instance().get_ollama_base_url()
            except Exception:
                kwargs['api_base'] = 'http://localhost:11434'
        litellm_tools = []
        for schema in tool_schemas:
            if 'type' in schema and 'function' in schema:
                litellm_tools.append(schema)
            else:
                litellm_tools.append({'type': 'function', 'function': schema})
        stream_callback = kwargs.pop('stream_callback', None)
        if stream_callback:
            kwargs['stream'] = True
            
        if litellm_tools:
            kwargs['tools'] = litellm_tools
        try:
            response = self._execute_completion(model, messages, **kwargs)
            
            if stream_callback:
                full_text = []
                tool_calls_dict = {}
                for chunk in response:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", "") or ""
                    if content:
                        full_text.append(content)
                        stream_callback(content)
                    
                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = getattr(tc, 'index', 0)
                            if idx not in tool_calls_dict:
                                tool_calls_dict[idx] = {'name': '', 'arguments': ''}
                            
                            if hasattr(tc, 'function'):
                                if getattr(tc.function, 'name', None):
                                    tool_calls_dict[idx]['name'] += tc.function.name
                                if getattr(tc.function, 'arguments', None):
                                    tool_calls_dict[idx]['arguments'] += tc.function.arguments

                parsed_tool_calls = []
                for idx in sorted(tool_calls_dict.keys()):
                    t = tool_calls_dict[idx]
                    try:
                        args = json.loads(t['arguments']) if t['arguments'] else {}
                    except Exception:
                        args = t['arguments']
                    parsed_tool_calls.append({'name': t['name'], 'arguments': args})
                
                return {'content': "".join(full_text), 'tool_calls': parsed_tool_calls}

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

    def generate(self, prompt, **kwargs) -> dict:
        """Backward compatibility stub for legacy components."""
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = prompt
        return {"content": self.chat(messages, **kwargs)}

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
