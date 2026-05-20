"""AXIOM Configuration module."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AxiomConfig:
    """AXIOM system configuration."""
    
    # System
    debug: bool = False
    log_level: str = "INFO"
    
    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "neural-chat"
    ollama_temperature: float = 0.7
    
    # Memory
    db_path: str = "axiom.db"
    max_history: int = 1000
    
    # Engine
    max_agents: int = 10
    max_tools: int = 100
    event_history_limit: int = 1000
    
    # Security
    sandbox_mode: bool = True
    allow_system_tools: bool = True
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "AxiomConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "debug": self.debug,
            "log_level": self.log_level,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "ollama_temperature": self.ollama_temperature,
            "db_path": self.db_path,
            "max_history": self.max_history,
            "max_agents": self.max_agents,
            "max_tools": self.max_tools,
            "event_history_limit": self.event_history_limit,
            "sandbox_mode": self.sandbox_mode,
            "allow_system_tools": self.allow_system_tools,
        }


# Default global config
_config = AxiomConfig()


def get_config() -> AxiomConfig:
    """Get global AXIOM configuration."""
    return _config


def set_config(config: AxiomConfig) -> None:
    """Set global AXIOM configuration."""
    global _config
    _config = config
