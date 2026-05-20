"""Ollama-compatible LLM client for local model inference."""

import requests
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


class OllamaClient:
    """Client for Ollama local LLM inference."""
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._session = requests.Session()
    
    def is_available(self) -> bool:
        """Check if Ollama service is available."""
        try:
            response = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """List available models in Ollama."""
        try:
            response = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.error(f"Error listing models: {e}")
        return []
    
    def generate(self, prompt: str, model: Optional[str] = None, 
                stream: bool = False) -> str:
        """Generate text using Ollama."""
        model = model or self.config.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
        }
        
        try:
            response = self._session.post(
                f"{self.config.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout,
                stream=stream
            )
            
            if response.status_code == 200:
                if stream:
                    return self._process_stream(response)
                else:
                    data = response.json()
                    return data.get("response", "")
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return ""
    
    def _process_stream(self, response) -> str:
        """Process streaming response."""
        result = ""
        try:
            for line in response.iter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    result += data.get("response", "")
        except Exception as e:
            logger.error(f"Error processing stream: {e}")
        return result
    
    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        """Chat with Ollama using message format."""
        model = model or self.config.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": self.config.temperature,
        }
        
        try:
            response = self._session.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                logger.error(f"Chat error: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return ""
    
    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate embeddings using Ollama."""
        model = model or self.config.model
        
        payload = {
            "model": model,
            "prompt": text,
        }
        
        try:
            response = self._session.post(
                f"{self.config.base_url}/api/embeddings",
                json=payload,
                timeout=self.config.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
            else:
                logger.error(f"Embed error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []
    
    def set_model(self, model: str) -> None:
        """Switch to a different model."""
        self.config.model = model
    
    def close(self) -> None:
        """Close the session."""
        self._session.close()
