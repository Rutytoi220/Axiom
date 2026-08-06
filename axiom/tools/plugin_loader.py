"""Dynamic Plugin Loader.

Scans ~/.config/axiom/plugins/ on boot and loads any Python scripts
found into the provided ToolRegistry.
"""
import os
import sys
import importlib.util
import logging
from pathlib import Path
from axiom.tools.base import AxiomPlugin, DecoratorTool

logger = logging.getLogger(__name__)

def load_plugins(registry) -> None:
    """Scan the plugins directory, discover tools, and register them."""
    plugins_dir = Path.home() / ".config" / "axiom" / "plugins"
    
    if not plugins_dir.exists():
        plugins_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created plugins directory at {plugins_dir}")
        _generate_example_plugin(plugins_dir)
        return

    # Check if directory is empty (other than directories/hidden)
    has_py_files = any(p.suffix == '.py' for p in plugins_dir.iterdir() if p.is_file())
    if not has_py_files:
        _generate_example_plugin(plugins_dir)

    for filepath in plugins_dir.glob("*.py"):
        _load_module_and_register(filepath, registry)

def _generate_example_plugin(plugins_dir: Path) -> None:
    example_file = plugins_dir / "system_info_plugin.py.example"
    if not example_file.exists():
        example_content = '''"""
Example AXIOM Plugin

To use this plugin, remove the '.example' extension so it becomes a '.py' file.
AXIOM will dynamically load it on the next boot!
"""
from axiom.tools.base import axiom_tool

@axiom_tool(
    name="get_uptime",
    description="Returns the current system uptime",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def get_uptime(**kwargs):
    import subprocess
    result = subprocess.check_output("uptime -p", shell=True, text=True).strip()
    return result
'''
        example_file.write_text(example_content)

def _load_module_and_register(filepath: Path, registry) -> None:
    """Dynamically import a Python file and register its tools."""
    module_name = f"axiom.dynamic_plugins.{filepath.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(filepath))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Inspect the module
            count = 0
            for name in dir(module):
                obj = getattr(module, name)
                
                # Check for @axiom_tool decorators
                if callable(obj) and getattr(obj, "__axiom_tool__", False):
                    tool = DecoratorTool(
                        func=obj,
                        name=obj.__tool_name__,
                        description=obj.__tool_description__,
                        parameters=obj.__tool_parameters__
                    )
                    registry.register(tool)
                    count += 1
                    
                # Check for AxiomPlugin subclasses
                elif isinstance(obj, type) and issubclass(obj, AxiomPlugin) and obj is not AxiomPlugin:
                    # Instantiate the plugin
                    tool = obj()
                    registry.register(tool)
                    count += 1
                    
            if count > 0:
                logger.info(f"Loaded {count} tools from plugin: {filepath.name}")
    except Exception as e:
        logger.warning(f"Failed to load plugin {filepath.name}: {e}")
