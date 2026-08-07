import asyncio
import logging
from axiom.tool_registry import ToolRegistry
from axiom.tools.plugin_loader import load_plugins
from axiom.services.watchdog import WatchdogService

logging.basicConfig(level=logging.INFO)

async def test_watchdog():
    loop = asyncio.get_running_loop()
    registry = ToolRegistry()
    watchdog = WatchdogService(registry, None)
    watchdog.start(loop)
    
    # Load plugins
    load_plugins(registry)
    
    # Trigger crash
    print("Triggering broken tool...")
    result = await registry.execute_async("broken_tool")
    print(f"Result: {result}")
    
    # Wait a bit to let the repair loop run
    print("Waiting for repair loop... (Ctrl+C to cancel if stuck)")
    # Just wait 5 seconds, if it triggers the log we know it works
    await asyncio.sleep(5)
    
if __name__ == "__main__":
    asyncio.run(test_watchdog())
