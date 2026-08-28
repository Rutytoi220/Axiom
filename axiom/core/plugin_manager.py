import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import Dict

from axiom.sdk.tool import AxiomTool
from axiom.config import get_config

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path.home() / ".config" / "ChienGPT" / "plugins"

class PluginManager:
    def __init__(self):
        self.active_tools: Dict[str, AxiomTool] = {}

    def load_plugins(self):
        self.active_tools.clear()
        config = get_config()
        if not getattr(config, 'allow_third_party_plugins', False):
            logger.warning("Third-party plugins are disabled in config. Skipping plugin load.")
            return

        if not PLUGIN_DIR.exists():
            PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

        for py_file in PLUGIN_DIR.glob("*.py"):
            try:
                module_name = f"axiom_plugin_{py_file.stem}"
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # Add to sys.modules so it can do relative imports if needed
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, AxiomTool) and obj is not AxiomTool:
                            instance = obj()
                            self.active_tools[instance.name] = instance
                            logger.info(f"Loaded plugin tool: {instance.name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {py_file.name}: {e}")
