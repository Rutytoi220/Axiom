f"""AXIOM main entry point and initialization."""

from axiom.core import Engine
from axiom.llm import OllamaClient
from axiom.api.cli import CLI, run_cli
from axiom.config import AxiomConfig, get_config, set_config

__version__ = "1.0.0"
__author__ = "AXIOM Team"

__all__ = [
    "Engine",
    "MemoryManager",
    "OllamaClient",
    "CLI",
    "run_cli",
    "AxiomConfig",
    "get_config",
    "set_config",
    "__version__",
]


def main():
    """Run AXIOM CLI."""
    run_cli()


if __name__ == "__main__":
    main()
