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
            
        import subprocess
        from rich.console import Console
        from rich.status import Status
        
        console = Console()
        
        def _auto_pull_model(model_name: str) -> bool:
            """Autonomously pull a missing model with a rich spinner."""
            console.print(f"\n[bold yellow]⚠️ Missing Required Model:[/bold yellow] [cyan]{model_name}[/cyan]")
            console.print("[dim]Initiating autonomous cloud-burst to pull the model. This may take a moment...[/dim]")
            
            try:
                with console.status(f"[bold green]Pulling {model_name} from Ollama registry...[/bold green]", spinner="dots"):
                    result = subprocess.run(
                        ["ollama", "pull", model_name], 
                        capture_output=True, 
                        text=True, 
                        check=True
                    )
                console.print(f"[bold green]✓ Successfully pulled {model_name}[/bold green]\n")
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]✗ Failed to pull {model_name}[/bold red]")
                console.print(f"[red]{e.stderr}[/red]\n")
                return False
            except FileNotFoundError:
                console.print("[bold red]✗ Ollama CLI not found. Is it installed and in your PATH?[/bold red]\n")
                return False

        # Validate reasoning model
        if config.ollama_model not in installed_models:
            success = _auto_pull_model(config.ollama_model)
            if not success:
                # If pull failed, fallback to alternatives
                candidates = ["llama3.1:latest", "qwen3:8b", "qwen3-vl:2b"]
                swapped = False
                for candidate in candidates:
                    if candidate in installed_models:
                        config.ollama_model = candidate
                        swapped = True
                        break
                
                if not swapped and installed_models:
                    config.ollama_model = installed_models[0]
                    swapped = True
                    
                if swapped:
                    print(f"[*] Dynamically swapped reasoning model to: {config.ollama_model}\n")
            
            ollama.config.model = config.ollama_model
            
        # Validate embedding model
        # Remove :latest suffix for check if user specified it, or vice versa
        embed_model_clean = config.embedding_model.replace(":latest", "")
        if config.embedding_model not in installed_models and f"{embed_model_clean}:latest" not in installed_models:
            success = _auto_pull_model(config.embedding_model)
            if not success:
                # Fallback to local check
                if "nomic-embed-text:latest" in installed_models:
                    config.embedding_model = "nomic-embed-text:latest"
                    print(f"[*] Dynamically swapped embedding model to: {config.embedding_model}\n")
                elif "nomic-embed-text" in installed_models:
                    config.embedding_model = "nomic-embed-text"
                    print(f"[*] Dynamically swapped embedding model to: {config.embedding_model}\n")
                else:
                    print(f"[*] AXIOM may encounter 500 errors during vector storage unless an embedding model is pulled.")
            
            ollama.config.embedding_model = config.embedding_model
            
        # Detect capabilities explicitly
        ollama._detect_capabilities()
            
    except Exception as e:
        print(f"\n[!] ERROR during model configuration check: {e}")
        print("    Proceeding with default configuration, but failures may occur.\n")
        logger.error(f"initialize_model_config failed: {e}", exc_info=True)
