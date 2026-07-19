import logging
from typing import Optional, List
from axiom.config import AxiomConfig
from axiom.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

def initialize_model_config(config: AxiomConfig, ollama: OllamaClient) -> None:
    """Dynamically validates and aligns AXIOM's model config with the local Ollama instance."""
    print("[ConfigService] Checking Ollama connection and installed models...")
    
    try:
        if not ollama.is_available():
            print("\n[!] WARNING: Ollama connection failed. Is the Ollama server running on your host?")
            print(f"    Expected at: {config.ollama_base_url}\n")
            return
            
        installed_models = ollama.list_models()
        print(f"[ConfigService] Detected {len(installed_models)} installed models:")
        for m in installed_models:
            print(f"  - {m}")
            
        if not installed_models:
            print("\n[!] WARNING: No models found in Ollama. Please run `ollama run <model>` first.\n")
            return
            
        # Validate reasoning model
        if config.ollama_model not in installed_models:
            print(f"\n[!] WARNING: Configured reasoning model '{config.ollama_model}' is not installed.")
            
            # Prefer llama3.1:latest, then qwen3:8b, else the first available
            candidates = ["llama3.1:latest", "qwen3:8b", "qwen3-coder:latest"]
            swapped = False
            for candidate in candidates:
                if candidate in installed_models:
                    config.ollama_model = candidate
                    swapped = True
                    break
            
            if not swapped:
                config.ollama_model = installed_models[0]
                
            print(f"[*] Dynamically swapped reasoning model to: {config.ollama_model}\n")
            ollama.config.model = config.ollama_model
            
        # Validate embedding model
        if config.embedding_model not in installed_models and f"{config.embedding_model}:latest" not in installed_models:
            print(f"\n[!] WARNING: Configured embedding model '{config.embedding_model}' is not installed.")
            
            # Prefer nomic-embed-text if installed
            if "nomic-embed-text:latest" in installed_models:
                config.embedding_model = "nomic-embed-text:latest"
                print(f"[*] Dynamically swapped embedding model to: {config.embedding_model}\n")
            elif "nomic-embed-text" in installed_models:
                config.embedding_model = "nomic-embed-text"
                print(f"[*] Dynamically swapped embedding model to: {config.embedding_model}\n")
            else:
                print(f"[*] AXIOM may encounter 500 errors during vector storage unless an embedding model is pulled.")
                print(f"    We recommend running: ollama run nomic-embed-text\n")
            
            ollama.config.embedding_model = config.embedding_model
            
        # Detect capabilities explicitly
        ollama._detect_capabilities()
            
    except Exception as e:
        print(f"\n[!] ERROR during model configuration check: {e}")
        print("    Proceeding with default configuration, but failures may occur.\n")
        logger.error(f"initialize_model_config failed: {e}", exc_info=True)
