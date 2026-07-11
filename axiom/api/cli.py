"""AXIOM Command-line interface."""

import asyncio
import cmd
import json
import logging
from typing import Optional
from axiom.core import Engine
from axiom.memory import MemoryManager, SyncMemoryStore
from axiom.llm import OllamaClient, OllamaConfig
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.tools import (
    EchoTool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    SystemInfoTool
)
from axiom.plugins import NXBTPlugin, AutomationPlugin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CLI(cmd.Cmd):
    """AXIOM Command-line interface."""
    
    intro = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    AXIOM - AI Orchestration                   ║
    ║              Local-First LLM Framework for Linux              ║
    ║                    Type 'help' for commands                   ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    
    prompt = "axiom> "
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create memory store first
        self.memory_store = SyncMemoryStore(":memory:")
        # Pass memory store to engine
        self.engine = Engine(memory=self.memory_store)
        self.memory = MemoryManager()
        self.ollama = OllamaClient(OllamaConfig(model="qwen2.5:14b"))
        self.orchestrator = OrchestratorAgent(self.engine.registry, self.engine.event_bus, self.memory_store, llm=self.ollama)
        self._event_log = []
        self._closed = False
        self._subscribe_events()
        self._init_system()
    
    def _subscribe_events(self) -> None:
        """Capture events via pub/sub instead of monkey-patching the event bus."""
        bus = self.engine.event_bus
        if hasattr(bus, "subscribe"):
            try:
                bus.subscribe("*", self._on_event)
            except Exception:
                logger.debug("Unable to subscribe CLI event listener", exc_info=True)

    def _on_event(self, event) -> None:
        try:
            name = getattr(event, "name", getattr(event, "event_type", "unknown"))
            payload = getattr(event, "payload", getattr(event, "data", None))
            self._event_log.append({"event": name, "payload": payload})
            self._event_log = self._event_log[-200:]
        except Exception:
            logger.debug("CLI event handler failed", exc_info=True)

    def _run_async(self, coro):
        """Helper to run async code in synchronous context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a new one
                return asyncio.run(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop in thread, create a new one
            return asyncio.run(coro)
    
    def _init_system(self) -> None:
        """Initialize the AXIOM system."""
        logger.info("Initializing AXIOM...")
        
        # Initialize engine
        self.engine.initialize()
        
        # Register tools
        self._register_tools()
        
        # Register agents
        self._register_agents()
        
        # Initialize plugins
        self._init_plugins()
        
        # Create initial conversation
        self.memory.create_conversation("AXIOM Session")
        
        logger.info("AXIOM initialization complete")
    
    def _register_tools(self) -> None:
        """Register system tools."""
        tools = [
            EchoTool(),
            ShellTool(),
            FileReadTool("."),
            FileWriteTool("."),
            SystemInfoTool()
        ]
        
        for tool in tools:
            self.engine.registry.register_tool(tool.tool_id, tool)
        
        logger.info(f"Registered {len(tools)} tools")
    
    def _register_agents(self) -> None:
        """Register agents."""
        # Register the orchestrator itself
        self.engine.registry.register_agent(self.orchestrator.name, self.orchestrator)
        
        # Register specialized agents with the orchestrator
        from axiom.agents import EchoAgent
        echo_agent = EchoAgent("echo_agent", self.engine.registry, self.engine.event_bus, self.memory_store)
        self.orchestrator.register_agent(echo_agent)
        
        logger.info("Registered orchestrator agent with echo_agent")
    
    def _init_plugins(self) -> None:
        """Initialize plugins."""
        plugins = [
            NXBTPlugin(),
            AutomationPlugin()
        ]
        
        for plugin in plugins:
            if plugin.initialize():
                plugin.enable()
                self.engine.registry.register_plugin(plugin.plugin_id, plugin)
        
        logger.info(f"Initialized {len(plugins)} plugins")
    
    def do_ask(self, arg: str) -> None:
        """Ask AXIOM a question: ask <question>"""
        if not arg:
            print("Usage: ask <question>")
            return
        
        print(f"\n[Processing: {arg[:50]}...]")
        
        try:
            # Process through orchestrator (OrchestratorAgent is synchronous)
            response = self.orchestrator.run(arg)
            
            # Convert output for display
            output_str = ""
            if response.output:
                if isinstance(response.output, dict):
                    # Agentic loop output
                    output_str = response.output.get("response", "")
                    tool_results = response.output.get("tool_results", [])
                    if tool_results:
                        output_str += "\n\n--- Tool calls ---"
                        for tr in tool_results:
                            output_str += f"\n  ▸ {tr['tool']}({json.dumps(tr['arguments'], default=str)[:80]})"
                elif isinstance(response.output, str):
                    output_str = response.output
                else:
                    output_str = json.dumps(response.output, indent=2, default=str)
            
            # Store in memory
            self.memory.add_message("user", arg)
            self.memory.add_message("assistant", output_str)
            
            # Display response
            print("\n" + "="*60)
            if output_str:
                print(output_str)
            elif response.error:
                print(f"Error: {response.error}")
            else:
                print("(No output)")
            print("="*60 + "\n")
        except Exception as e:
            print(f"\nError processing request: {e}\n")
            logger.exception(f"Error in do_ask: {e}")
    
    def do_tools(self, arg: str) -> None:
        """List all registered tools"""
        tools = self.engine.registry.list_tools()
        
        if not tools:
            print("No tools registered")
            return
        
        print("\nRegistered Tools:")
        print("="*60)
        for tool_id, tool in tools.items():
            info = tool.get_info()
            print(f"\n  {info['name']} ({tool_id})")
            print(f"    Description: {info['description']}")
            print(f"    Executions: {info['execution_count']}")
            if info['parameters']:
                print(f"    Parameters:")
                for param in info['parameters']:
                    req = "required" if param['required'] else "optional"
                    print(f"      - {param['name']} ({param['type']}) [{req}]")
        print("\n")
    
    def do_agents(self, arg: str) -> None:
        """List all registered agents"""
        agents = self.engine.registry.list_agents()
        
        if not agents:
            print("No agents registered")
            return
        
        print("\nRegistered Agents:")
        print("="*60)
        for agent_id, agent in agents.items():
            info = agent.get_info()
            print(f"\n  {info['name']} ({agent_id})")
            print(f"    Description: {info['description']}")
            print(f"    State: {info['state']}")
            print(f"    Executions: {info['execution_count']}")
        print("\n")
    
    def do_plugins(self, arg: str) -> None:
        """List all registered plugins"""
        plugins = self.engine.registry.list_plugins()
        
        if not plugins:
            print("No plugins registered")
            return
        
        print("\nRegistered Plugins:")
        print("="*60)
        for plugin_id, plugin in plugins.items():
            info = plugin.get_info()
            status = "enabled" if info['enabled'] else "disabled"
            print(f"\n  {info['name']} ({plugin_id})")
            print(f"    Version: {info['version']}")
            print(f"    Status: {status}")
        print("\n")
    
    def do_status(self, arg: str) -> None:
        """Show AXIOM system status"""
        print("\n" + "="*60)
        print("AXIOM System Status")
        print("="*60)
        
        # Engine status
        print(f"\nEngine:")
        print(f"  Running: {self.engine.is_running()}")
        
        # LLM status
        print(f"\nLLM (Ollama):")
        print(f"  Available: {self.ollama.is_available()}")
        if self.ollama.is_available():
            models = self.ollama.list_models()
            print(f"  Models available: {len(models)}")
            print(f"  Current model: {self.ollama.config.model}")
        else:
            print("  Status: Not available (Ollama not running)")
        
        # Memory status
        print(f"\nMemory:")
        print(f"  Current conversation: {self.memory.get_conversation()}")
        history = self.memory.get_conversation_history(limit=1)
        print(f"  Messages in conversation: {len(self.memory.get_conversation_history())}")
        
        # Registry status
        tools = self.engine.registry.list_tools()
        agents = self.engine.registry.list_agents()
        plugins = self.engine.registry.list_plugins()
        print(f"\nRegistry:")
        print(f"  Tools: {len(tools)}")
        print(f"  Agents: {len(agents)}")
        print(f"  Plugins: {len(plugins)}")
        
        print("\n" + "="*60 + "\n")
    
    def do_history(self, arg: str) -> None:
        """Show conversation history"""
        history = self.memory.get_conversation_history()
        
        if not history:
            print("No conversation history")
            return
        
        print("\nConversation History:")
        print("="*60)
        for msg in history:
            role = msg['role'].upper()
            content = msg['content']
            if len(content) > 100:
                content = content[:100] + "..."
            print(f"\n{role}: {content}")
        print("\n")
    

    def do_resume(self, arg: str) -> None:
        """Resume a conversation by ID: resume <conversation_id>"""
        conversation_id = arg.strip()
        if not conversation_id:
            print("Usage: resume <conversation_id>")
            return
        try:
            history = self.memory.restore_conversation(conversation_id)
            print(f"Resumed conversation {conversation_id} ({len(history)} messages)")
        except Exception as e:
            print(f"Unable to resume conversation: {e}")
            logger.exception("Conversation resume failed")

    def do_clear_history(self, arg: str) -> None:
        """Clear conversation history"""
        if self.memory.get_conversation():
            self.memory.create_conversation("AXIOM Session")
            print("History cleared")
        else:
            print("No active conversation")
    
    def do_memory_log(self, arg: str) -> None:
        """Show memory event log: memory-log [--limit N]"""
        limit = 20
        if arg:
            try:
                if arg.startswith("--limit"):
                    limit = int(arg.split()[-1])
            except (ValueError, IndexError):
                print("Usage: memory-log [--limit N]")
                return
        
        events = self.engine.memory.get_events(limit=limit)
        
        if not events:
            print("No events recorded.")
            return
        
        print("\nMemory Event Log:")
        print("="*80)
        print(f"{'Timestamp':<20} | {'Event Name':<30} | {'Data':<25}")
        print("-"*80)
        
        for event in events:
            timestamp = str(event['timestamp'])[:10]  # Format timestamp
            event_name = event['event_name'][:28]
            data = json.dumps(event['payload'])[:23] if event['payload'] else "None"
            print(f"{timestamp:<20} | {event_name:<30} | {data:<25}")
        
        print("="*80 + "\n")
    
    def do_quit(self, arg: str) -> None:
        """Exit AXIOM"""
        print("\nShutting down AXIOM...")
        self.close()
        print("Goodbye!")
        return True

    def close(self) -> None:
        """Release engine and memory resources exactly once."""
        if self._closed:
            return
        self._closed = True
        self.engine.shutdown()
        self.memory.close()
        self.memory_store.close()

    def postloop(self) -> None:
        """Ensure resources are released when the command loop exits."""
        self.close()
    
    def do_help(self, arg: str) -> None:
        """Show help information"""
        if arg:
            super().do_help(arg)
        else:
            print("\n" + "="*60)
            print("AXIOM Commands")
            print("="*60)
            print("""
  ask <question>      - Ask AXIOM a question
  tools              - List all registered tools
  agents             - List all registered agents
  plugins            - List all registered plugins
  status             - Show system status
  history            - Show conversation history
  clear_history      - Clear conversation history
  resume <id>        - Resume conversation/session by ID
  memory_log         - Show memory event log
  exit/quit          - Exit AXIOM
  help               - Show this help message
            """)
            print("="*60 + "\n")
    
    def emptyline(self) -> None:
        """Handle empty line input."""
        pass


def run_cli() -> None:
    """Run the AXIOM CLI."""
    cli = CLI()
    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Shutting down...")
        cli.close()
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
        print(f"Error: {e}")
        cli.close()
    else:
        cli.close()
