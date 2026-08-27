import os
import sys
import importlib.util
import inspect
import logging
from pathlib import Path
from axiom.tools import BaseTool

logger = logging.getLogger(__name__)

class PluginManager:
    """Dynamically loads user-defined tools from the plugins directory."""

    def __init__(self):
        self.plugins_dir = Path.home() / ".config" / "ChienGPT" / "plugins"
        
        # If it doesn't exist, create it and write a boilerplate template
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            self._write_boilerplate()

    def _write_boilerplate(self):
        """Writes a heavily documented template to help users get started."""
        boilerplate_path = self.plugins_dir / "example_tool.py.disabled"
        boilerplate_content = '''"""
AXIOM Custom Tool Template
Rename this file to end with .py to enable it (e.g., example_tool.py)
"""
from axiom.tools import BaseTool, ToolParameter, ToolResult

class HelloWorldTool(BaseTool):
    """A simple tool that greets the user."""

    def __init__(self):
        super().__init__(
            tool_id="hello_world",
            name="HelloWorldTool",
            description="Prints a greeting message to a specified name."
        )
        self.add_parameter(ToolParameter(
            name="name",
            type="string",
            description="The name of the person to greet.",
            required=True
        ))

    async def execute(self, name: str, **_kwargs) -> ToolResult:
        # Perform your tool logic here
        greeting = f"Hello, {name}! Welcome to the AXIOM Workshop."
        
        # Return a ToolResult (success=True/False)
        return ToolResult(
            success=True,
            output=greeting
        )
'''
        try:
            boilerplate_path.write_text(boilerplate_content, encoding="utf-8")
        except Exception as e:
            logger.error("Failed to write plugin boilerplate: %s", e)

    def load_user_tools(self) -> list[BaseTool]:
        """Iterates through plugins dir, dynamically imports .py files, and extracts BaseTools."""
        loaded_tools = []
        
        if not self.plugins_dir.exists():
            return loaded_tools

        for item in self.plugins_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                module_name = item.stem
                try:
                    # Dynamically load the module from its file path
                    spec = importlib.util.spec_from_file_location(module_name, str(item))
                    if spec is None or spec.loader is None:
                        logger.warning(f"Could not load plugin spec for {item.name}")
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    # Insert it into sys.modules so it behaves like a normal import
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    # Extract all classes that inherit from BaseTool
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj is not BaseTool:
                            try:
                                tool_instance = obj()
                                loaded_tools.append(tool_instance)
                                logger.info(f"Loaded custom tool '{tool_instance.name}' from {item.name}")
                            except Exception as init_err:
                                logger.error(f"Failed to instantiate tool class {name} in {item.name}: {init_err}")
                
                except Exception as e:
                    # Catch and log safely so one broken plugin doesn't nuke AXIOM
                    logger.error(f"Failed to load plugin file {item.name}: {e}")

        return loaded_tools
