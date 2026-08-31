"""AXIOM Configuration module."""
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from enum import Enum

CONFIG_DIR = Path.home() / ".config" / "ChienGPT"

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
    allow_third_party_plugins: bool = False

    def __post_init__(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if self.behavior is None:
            self.behavior = BehaviorConfig()
    ollama_base_url: str = 'http://localhost:11434'
    ollama_model: str = 'qwen3:8b'
    power_saving_model: str = 'qwen2.5:1.5b'
    embedding_model: str = 'nomic-embed-text'
    ollama_temperature: float = 0.7
    db_path: str = 'axiom.db'
    max_history: int = 1000
    max_agents: int = 10
    max_tools: int = 100
    event_history_limit: int = 1000
    sandbox_mode: bool = True
    allow_system_tools: bool = True
    max_vector_memories: int = 5000
    
    # UI / GUI Settings
    first_launch: bool = True
    oobe_completed: bool = False
    vision_model: str = ''
    theme: str = 'minimalist'  # 'minimalist', 'cyberpunk', 'nothing'
    theme_mode: str = 'dark'  # 'system', 'dark', 'light'
    ui_profile_level: str = 'standard' # 'standard', 'advanced', 'developer'
    persona: dict = field(default_factory=dict)
    persona_key: str = 'default'
    llm_complexity: str = 'detailed'
    auto_ollama_start: bool = True
    model_selection_mode: str = 'auto'  # 'auto', 'manual'
    auto_index_watchdog: bool = False
    monitored_paths: list[str] = field(default_factory=lambda: [str(Path.home() / 'Documents')])

    # Swarm Compute
    swarm_enabled: bool = False
    remote_endpoints: list[str] = field(default_factory=list)
    offload_strategy: str = 'thermal_trigger'

    # Plugins
    disabled_plugins: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'AxiomConfig':
        """Create config from dictionary."""
        filtered = {k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__}
        
        # Migrate legacy loose persona strings to new dict structure
        if 'persona' not in filtered:
            filtered['persona'] = {}
            if 'persona_tone' in config_dict:
                filtered['persona']['communication'] = {'tone': config_dict['persona_tone'], 'verbosity': config_dict.get('persona_complexity', 'standard')}
            if 'special_instructions' in config_dict and config_dict['special_instructions']:
                filtered['persona']['directives'] = [config_dict['special_instructions']]
                
        if 'auth_mode' in filtered and isinstance(filtered['auth_mode'], str):
            try:
                filtered['auth_mode'] = AuthMode(filtered['auth_mode'])
            except ValueError:
                filtered['auth_mode'] = AuthMode.BASIC
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            'auth_mode': self.auth_mode.value, 
            'debug': self.debug, 
            'log_level': self.log_level, 
            'proactive_kernel': self.proactive_kernel, 
            'ollama_base_url': self.ollama_base_url, 
            'ollama_model': self.ollama_model, 
            'embedding_model': self.embedding_model, 
            'ollama_temperature': self.ollama_temperature, 
            'db_path': self.db_path, 
            'max_history': self.max_history, 
            'max_agents': self.max_agents, 
            'max_tools': self.max_tools, 
            'event_history_limit': self.event_history_limit, 
            'sandbox_mode': self.sandbox_mode, 
            'allow_system_tools': self.allow_system_tools,
            'max_vector_memories': self.max_vector_memories,
            'allow_cloud_fallback': self.allow_cloud_fallback, 
            'monitor_window_focus': self.monitor_window_focus, 
            'monitor_clipboard': self.monitor_clipboard,
            'allow_third_party_plugins': self.allow_third_party_plugins,
            'first_launch': self.first_launch,
            'oobe_completed': self.oobe_completed,
            'vision_model': self.vision_model,
            'theme': self.theme,
            'theme_mode': self.theme_mode,
            'ui_profile_level': self.ui_profile_level,
            'persona': self.persona,
            'persona_key': self.persona_key,
            'llm_complexity': self.llm_complexity,
            'auto_ollama_start': self.auto_ollama_start,
            'model_selection_mode': self.model_selection_mode,
            'auto_index_watchdog': self.auto_index_watchdog,
            'monitored_paths': self.monitored_paths,
            'swarm_enabled': self.swarm_enabled,
            'remote_endpoints': self.remote_endpoints,
            'offload_strategy': self.offload_strategy,
            'disabled_plugins': self.disabled_plugins
        }

    def save(self) -> None:
        """Save configuration to ~/.config/ChienGPT/config.json."""
        import json
        from pathlib import Path
        config_dir = CONFIG_DIR
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.json"
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Failed to save AXIOM config: {e}")

    @classmethod
    def load(cls) -> 'AxiomConfig':
        """Load configuration from ~/.config/ChienGPT/config.json."""
        import json
        from pathlib import Path
        config_path = CONFIG_DIR / "config.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'oobe_completed' not in data:
                    # Migrating a pre-v11 install: if the legacy UI config already
                    # exists, this user was already onboarded once and should not
                    # be forced through the new wizard again.
                    legacy_ui_config = CONFIG_DIR / "ui_config.json"
                    data['oobe_completed'] = legacy_ui_config.exists()
                return cls.from_dict(data)
            except Exception as e:
                print(f"Failed to load AXIOM config: {e}")
        return cls()

_config = AxiomConfig.load()

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
