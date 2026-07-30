import asyncio
from axiom.engine.telemetry import StructuredTracer, setup_structured_logging
from axiom.engine.plugin_loader import PluginLoaderService
from axiom.sdk.plugin import tool, get_registered_plugins
import os
from pathlib import Path

# 1. Test Structured Logging
setup_structured_logging()
tracer = StructuredTracer()
trace_id = tracer.start_trace("TestOperation", custom_tag="verification")
tracer.log_step("Doing some work")
tracer.end_trace("TestOperation")

# 2. Test Plugin Loader
plugin_dir = Path(os.path.expanduser("~/.config/axiom/plugins"))
plugin_dir.mkdir(parents=True, exist_ok=True)
with open(plugin_dir / "hello_plugin.py", "w") as f:
    f.write("""
from axiom.sdk.plugin import tool

@tool(name="hello_world", description="Prints hello world")
def hello_world():
    return "Hello from plugin!"
""")

loader = PluginLoaderService()
loader.discover_and_load()
plugins = get_registered_plugins()
print("Discovered Plugins:", plugins.keys())
assert "hello_world" in plugins, "Plugin was not registered!"
print("SUCCESS!")
