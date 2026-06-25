"""Ollama-compatible LLM client for local model inference - stdlib only."""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""
    base_url: str = "http://localhost:11434"
    model: str = "neural-chat"
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    timeout: int = 300


class OllamaError(Exception):
    """Exception raised for Ollama-related errors."""
    pass


class OllamaClient:
    """Client for Ollama local LLM inference - uses stdlib urllib only."""
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        """Initialize Ollama client.
        
        Args:
            config: OllamaConfig instance with connection settings
        """
        self.config = config or OllamaConfig()
    
    def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        """Make HTTP request to Ollama server.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/api/generate")
            body: Request body as dict (will be JSON encoded)
            
        Returns:
            Response as dictionary
            
        Raises:
            OllamaError: On any HTTP or connection error
        """
        url = self.config.base_url.rstrip("/") + path
        data = json.dumps(body).encode() if body else None
        
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                response_data = resp.read().decode()
                return json.loads(response_data)
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            logger.error(error_msg)
            raise OllamaError(error_msg)
        except urllib.error.URLError as e:
            error_msg = f"Connection failed: {e.reason}"
            logger.error(error_msg)
            raise OllamaError(error_msg)
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            raise OllamaError(error_msg)
    
    def is_available(self) -> bool:
        """Check if Ollama service is available.
        
        Returns:
            True if Ollama is reachable, False otherwise.
            NEVER raises exceptions.
        """
        try:
            self._request("GET", "/api/tags")
            return True
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """List available models in Ollama.
        
        Returns:
            List of model names.
            Returns empty list on any error.
            NEVER raises exceptions.
        """
        try:
            response = self._request("GET", "/api/tags")
            models = response.get("models", [])
            return [model.get("name", "") for model in models if isinstance(model, dict) and model.get("name")]
        except Exception as e:
            logger.debug(f"Error listing models: {e}")
            return []
    
    def generate(self, prompt: str, model: Optional[str] = None, 
                stream: bool = False) -> str:
        """Generate text using Ollama.
        
        Args:
            prompt: Input prompt for generation
            model: Model name (uses config default if not provided)
            stream: Whether to stream response (only False supported in stdlib)
            
        Returns:
            Generated text response
            
        Raises:
            OllamaError: On server error or connection failure
        """
        model = model or self.config.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # Streaming not supported with stdlib
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
        }
        
        try:
            response = self._request("POST", "/api/generate", payload)
            return response.get("response", "")
        except OllamaError:
            raise
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ""
    
    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        """Chat with Ollama using message format.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name (uses config default if not provided)
            
        Returns:
            Chat response text
            
        Raises:
            OllamaError: On server error or connection failure
        """
        model = model or self.config.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
        }
        
        try:
            response = self._request("POST", "/api/chat", payload)
            message = response.get("message", {})
            return message.get("content", "")
        except OllamaError:
            raise
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return ""
    
    def chat_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
                        model: Optional[str] = None) -> Dict[str, Any]:
        """Chat with Ollama using tool/function calling.

        Args:
            messages: List of message dicts (role + content, may include tool results)
            tools: List of tool schemas in OpenAI-compatible format
            model: Model override

        Returns:
            Full assistant message dict — may contain 'tool_calls' list
        """
        model = model or self.config.model

        payload = {
            "model": model,
            "messages": messages,
            "tools": tools if tools else None,
            "stream": False,
        }
        # Remove None keys
        payload = {k: v for k, v in payload.items() if v is not None}

        try:
            response = self._request("POST", "/api/chat", payload)
            return response.get("message", {"role": "assistant", "content": ""})
        except OllamaError:
            raise
        except Exception as e:
            logger.error(f"Error in chat_with_tools: {e}")
            return {"role": "assistant", "content": f"Error: {str(e)}"}

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate embeddings using Ollama.
        
        Args:
            text: Text to embed
            model: Model name (uses config default if not provided)
            
        Returns:
            Embedding vector as list of floats
        """
        model = model or self.config.model
        
        payload = {
            "model": model,
            "prompt": text,
        }
        
        try:
            response = self._request("POST", "/api/embeddings", payload)
            return response.get("embedding", [])
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    def set_model(self, model: str) -> None:
        """Switch to a different model."""
        self.config.model = model
    
    def close(self) -> None:
        """Close the session."""
        self._session.close()


class PromptBuilder:
    """Builder for constructing chat message sequences."""
    
    def __init__(self):
        """Initialize empty prompt builder."""
        self._messages = []
        self._system = None
    
    def system(self, text: str) -> "PromptBuilder":
        """Set system message.
        
        Args:
            text: System instruction text
            
        Returns:
            Self for method chaining
        """
        self._system = text
        return self
    
    def user(self, text: str) -> "PromptBuilder":
        """Add user message.
        
        Args:
            text: User message content
            
        Returns:
            Self for method chaining
        """
        self._messages.append({"role": "user", "content": text})
        return self
    
    def assistant(self, text: str) -> "PromptBuilder":
        """Add assistant message.
        
        Args:
            text: Assistant message content
            
        Returns:
            Self for method chaining
        """
        self._messages.append({"role": "assistant", "content": text})
        return self
    
    def build(self) -> List[Dict[str, str]]:
        """Build message list for OllamaClient.chat().
        
        If system is set, prepends {"role": "system", "content": self._system}.
        Then appends all messages in order.
        
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        result = []
        if self._system:
            result.append({"role": "system", "content": self._system})
        result.extend(self._messages)
        return result
    
    def build_raw(self) -> str:
        """Build concatenated string representation of all messages.
        
        Format:
            If system: "System: {text}\n"
            For each message: "{Role}: {content}\n"
        
        Returns:
            Stripped string containing all messages
        """
        lines = []
        if self._system:
            lines.append(f"System: {self._system}")
        for msg in self._messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines).strip()
    
    def reset(self) -> "PromptBuilder":
        """Clear all messages and system instruction.
        
        Returns:
            Self for method chaining
        """
        self._messages = []
        self._system = None
        return self
