"""Plugin Loader Service.

Scans ~/.config/axiom/plugins/ on daemon boot and loads any Python scripts
found. Functions decorated with @axiom.tool are auto-discovered and registered.
"""
import os
import sys
import importlib.util
import logging
from pathlib import Path

from axiom.sdk.plugin import get_registered_plugins

logger = logging.getLogger(__name__)

class PluginLoaderService:
    """Service to discover and load external plugins dynamically."""

    def __init__(self, plugins_dir: str = "~/.config/axiom/plugins/"):
        self.plugins_dir = Path(os.path.expanduser(plugins_dir))
        self._loaded_plugins = set()

    def discover_and_load(self) -> None:
        """Scan the plugins directory and load all valid python modules."""
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created plugins directory at {self.plugins_dir}")
            return

        for child in self.plugins_dir.iterdir():
            if child.is_file() and child.suffix == '.py':
                self._load_module(child)
                
        # Force import our internal cross-platform OS tools that use the @axiom.tool SDK
        try:
            import axiom.tools.os_vision
            import axiom.tools.os_input
            import axiom.tools.screen_perception
        except ImportError as e:
            logger.warning(f"Could not load internal OS plugins: {e}")

        # Register them with the tool registry
        # (In a real implementation, we would inject these into `axiom/tool_registry.py`)
        plugins = get_registered_plugins()
        if plugins:
            logger.info(f"Loaded {len(plugins)} external plugin tools.")

    def _load_module(self, filepath: Path) -> None:
        """Dynamically import a Python file."""
        module_name = f"axiom.dynamic_plugins.{filepath.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(filepath))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._loaded_plugins.add(module_name)
                logger.info(f"Successfully loaded plugin module: {filepath.name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {filepath.name}: {e}")
