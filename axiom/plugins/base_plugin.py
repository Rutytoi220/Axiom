"""Base plugin class for AXIOM."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """Base class for AXIOM plugins."""
    
    def __init__(self, plugin_id: str, name: str, version: str = "1.0.0"):
        self.plugin_id = plugin_id
        self.name = name
        self.version = version
        self.enabled = False
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    def initialize(self, config: Optional[Dict] = None) -> bool:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """Shutdown the plugin."""
        pass
    
    def enable(self) -> None:
        """Enable the plugin."""
        self.enabled = True
        logger.info(f"Plugin {self.plugin_id} enabled")
    
    def disable(self) -> None:
        """Disable the plugin."""
        self.enabled = False
        logger.info(f"Plugin {self.plugin_id} disabled")
    
    def is_enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self.enabled
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
            "config": self.config
        }
