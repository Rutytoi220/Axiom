import os
import argparse
import sys
import json
import asyncio
import subprocess

def send_prompt(prompt: str):
    async def _send():
        import websockets
        try:
            async with websockets.connect("ws://127.0.0.1:9410") as ws:
                # We send the prompt. A real CLI might stream. 
                # We'll just submit it so the daemon executes it.
                await ws.send(json.dumps({"action": "submit_task", "prompt": prompt}))
                print(f"Sent prompt to daemon: {prompt}")
                # We could wait for response, but for now we'll just exit
        except Exception as e:
            print(f"Failed to connect to daemon: {e}")
    asyncio.run(_send())

def list_tools():
    from axiom.core.plugin_manager import PluginManager
    from axiom.tool_registry import ToolRegistry
    
    registry = ToolRegistry()
    pm = PluginManager()
    user_tools = pm.load_user_tools()
    
    for ut in user_tools:
        registry.register_tool(ut.tool_id, ut)
        
    tools = registry._core_registry.list_tools()
    print("Available Tools:")
    for tid, t in sorted(tools.items()):
        desc = getattr(t, 'description', '')
        if not desc and t.__doc__:
            desc = t.__doc__.strip().split('\n')[0]
        print(f"  - {tid}: {desc}")

def run_tool(tool_id: str, args_json: str):
    from axiom.core.plugin_manager import PluginManager
    from axiom.tool_registry import ToolRegistry
    
    registry = ToolRegistry()
    pm = PluginManager()
    for ut in pm.load_user_tools():
        registry.register_tool(ut.tool_id, ut)
        
    tools = registry._core_registry.list_tools()
    
    if tool_id not in tools:
        print(f"Error: Tool '{tool_id}' not found.")
        return
        
    tool = tools[tool_id]
    args = json.loads(args_json) if args_json else {}
    
    async def _run():
        print(f"Running {tool_id} with args {args}...")
        try:
            result = await tool.execute(**args)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Execution failed: {e}")
            
    asyncio.run(_run())

def show_status():
    async def _status():
        import websockets
        import psutil
        try:
            # We just print some local telemetry and daemon status
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            print(f"System Status:")
            print(f"  CPU Usage: {cpu}%")
            print(f"  RAM Usage: {ram}%")
            
            # Check daemon
            try:
                async with websockets.connect("ws://127.0.0.1:9410", close_timeout=1) as ws:
                    print("  Daemon: ONLINE (ws://127.0.0.1:9410)")
            except Exception:
                print("  Daemon: OFFLINE")
                
        except ImportError:
            print("System Status: N/A (psutil not installed)")
            
    asyncio.run(_status())

def run_tests():
    print("Running headless test suite...")
    # Force offscreen for PySide6
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    subprocess.run(["pytest", "tests/test_plugins.py", "tests/test_gui_hub.py", "tests/test_daemon_ipc.py"], env=env)

def main():
    parser = argparse.ArgumentParser(description="AXIOM Universal CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # send command
    parser_send = subparsers.add_parser("send", help="Send a prompt to the daemon")
    parser_send.add_argument("prompt", type=str, help="The prompt text")
    
    # tool command
    parser_tool = subparsers.add_parser("tool", help="Manage tools")
    tool_subparsers = parser_tool.add_subparsers(dest="tool_cmd")
    
    # tool list
    tool_subparsers.add_parser("list", help="List all available tools")
    
    # tool run
    parser_tool_run = tool_subparsers.add_parser("run", help="Run a specific tool")
    parser_tool_run.add_argument("tool_id", type=str, help="ID of the tool to run")
    parser_tool_run.add_argument("--args", type=str, default="{}", help="JSON string of arguments")
    
    # status command
    subparsers.add_parser("status", help="Show system and daemon status")
    
    # test command
    subparsers.add_parser("test", help="Run the automated test suite")
    
    args = parser.parse_args()
    
    if args.command == "send":
        send_prompt(args.prompt)
    elif args.command == "tool":
        if args.tool_cmd == "list":
            list_tools()
        elif args.tool_cmd == "run":
            run_tool(args.tool_id, args.args)
        else:
            parser_tool.print_help()
    elif args.command == "status":
        show_status()
    elif args.command == "test":
        run_tests()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
