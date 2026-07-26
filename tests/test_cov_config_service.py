import pytest
from unittest.mock import MagicMock
from axiom.core.config_service import initialize_model_config

def test_initialize_model_config():
    config = MagicMock()
    ollama = MagicMock()
    
    # 1. Not available
    ollama.is_available.return_value = False
    initialize_model_config(config, ollama)
    
    # 2. Available but no models
    ollama.is_available.return_value = True
    ollama.list_models.return_value = []
    initialize_model_config(config, ollama)
    
    # 3. Models available, exact matches
    ollama.list_models.return_value = ["my-reasoning", "my-embedding"]
    config.ollama_model = "my-reasoning"
    config.embedding_model = "my-embedding"
    initialize_model_config(config, ollama)
    
    # 4. Models available, missing reasoning, fallback 1
    ollama.list_models.return_value = ["llama3.1:latest", "nomic-embed-text"]
    config.ollama_model = "not-found"
    config.embedding_model = "not-found"
    initialize_model_config(config, ollama)
    
    # 5. Missing reasoning, fallback to first
    ollama.list_models.return_value = ["random-model", "nomic-embed-text:latest"]
    config.ollama_model = "not-found"
    config.embedding_model = "not-found"
    initialize_model_config(config, ollama)
    
    # 6. Exception handling
    ollama.list_models.side_effect = Exception("error")
    initialize_model_config(config, ollama)
