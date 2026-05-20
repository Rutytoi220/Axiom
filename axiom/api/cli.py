"""AXIOM Command-line interface."""

import cmd
import json
import logging
from typing import Optional
from axiom.core import Engine
from axiom.memory import MemoryManager
from axiom.llm import OllamaClient, OllamaConfig
from axiom.agents import OrchestratorAgent
from axiom.tools import (
    ShellTool,
    FileTool
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
        self.engine = Engine()
        self.memory = MemoryManager()
        self.ollama = OllamaClient()
        self.orchestrator = OrchestratorAgent()
        self._init_system()
    
    def _init_system(self) -> None:
        """Initialize the AXIOM system."""
        logger.info("Initializing AXIOM...")
        
        # Initialize engine
        self.engine.initialize()
        self.orchestrator.set_engine_refs(self.engine.event_bus, self.engine.registry)
        
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
            ShellTool(),
            FileTool(".")
        ]
        
        for tool in tools:
            self.engine.registry.register_tool(tool.tool_id, tool)
        
        logger.info(f"Registered {len(tools)} tools")
    
    def _register_agents(self) -> None:
        """Register agents."""
        self.engine.registry.register_agent(self.orchestrator.agent_id, self.orchestrator)
        logger.info("Registered orchestrator agent")
    
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
        
        # Process through orchestrator
        response = self.orchestrator(arg)
        
        # Store in memory
        self.memory.add_message("user", arg)
        self.memory.add_message("assistant", response.output or "")
        
        # Display response
        print("\n" + "="*60)
        print(response.output)
        print("="*60 + "\n")
    
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
    
    def do_clear_history(self, arg: str) -> None:
        """Clear conversation history"""
        if self.memory.get_conversation():
            self.memory.create_conversation("AXIOM Session")
            print("History cleared")
        else:
            print("No active conversation")
    
    def do_quit(self, arg: str) -> None:
        """Exit AXIOM"""
        print("\nShutting down AXIOM...")
        self.engine.shutdown()
        print("Goodbye!")
        return True
    
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
        cli.engine.shutdown()
    except Exception as e:
        logger.error(f"CLI error: {e}", exc_info=True)
        print(f"Error: {e}")
