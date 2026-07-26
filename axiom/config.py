"""AXIOM Configuration module."""
from dataclasses import dataclass
from typing import Optional

from enum import Enum

class AuthMode(Enum):
    STRICT = 'strict'
    BASIC = 'basic'
    AUTOPILOT = 'autopilot'

@dataclass
class BehaviorConfig:
    """Auto-generated docstring.

"""
    profile: str = 'default'

@dataclass
class AxiomConfig:
    """AXIOM system configuration."""
    auth_mode: AuthMode = AuthMode.BASIC
    behavior: BehaviorConfig | None = None
    debug: bool = False
    log_level: str = 'INFO'
    proactive_kernel: bool = False
    allow_cloud_fallback: bool = False
    monitor_window_focus: bool = False
    monitor_clipboard: bool = False

    def __post_init__(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if self.behavior is None:
            self.behavior = BehaviorConfig()
    ollama_base_url: str = 'http://localhost:11434'
    ollama_model: str = 'qwen3:8b'
    embedding_model: str = 'nomic-embed-text'
    ollama_temperature: float = 0.7
    db_path: str = 'axiom.db'
    max_history: int = 1000
    max_agents: int = 10
    max_tools: int = 100
    event_history_limit: int = 1000
    sandbox_mode: bool = True
    allow_system_tools: bool = True

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'AxiomConfig':
        """Create config from dictionary."""
        filtered = {k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__}
        if 'auth_mode' in filtered and isinstance(filtered['auth_mode'], str):
            try:
                filtered['auth_mode'] = AuthMode(filtered['auth_mode'])
            except ValueError:
                filtered['auth_mode'] = AuthMode.BASIC
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {'auth_mode': self.auth_mode.value, 'debug': self.debug, 'log_level': self.log_level, 'proactive_kernel': self.proactive_kernel, 'ollama_base_url': self.ollama_base_url, 'ollama_model': self.ollama_model, 'embedding_model': self.embedding_model, 'ollama_temperature': self.ollama_temperature, 'db_path': self.db_path, 'max_history': self.max_history, 'max_agents': self.max_agents, 'max_tools': self.max_tools, 'event_history_limit': self.event_history_limit, 'sandbox_mode': self.sandbox_mode, 'allow_system_tools': self.allow_system_tools, 'allow_cloud_fallback': self.allow_cloud_fallback, 'monitor_window_focus': self.monitor_window_focus, 'monitor_clipboard': self.monitor_clipboard}
_config = AxiomConfig()

def get_config() -> AxiomConfig:
    """Get global AXIOM configuration."""
    return _config

def set_config(config: AxiomConfig) -> None:
    """Set global AXIOM configuration."""
    global _config
    _config = config
try:
    from core.settings_registry import SettingCategory, SettingMetadata, SettingsRegistry, get_settings_registry
except ImportError:
    pass
