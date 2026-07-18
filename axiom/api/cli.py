"""AXIOM Command-line interface."""

import cmd
import json
import logging
import os
from pathlib import Path
from typing import Optional
from axiom.core import Engine, shutdown_bridge
from axiom.memory import SyncMemoryStore
from axiom.llm import OllamaClient, OllamaConfig
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.tool_registry import ToolRegistry
from axiom.tools import (
    EchoTool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    SystemInfoTool
)
from axiom.legacy_wrapper import create_legacy_tools
from axiom.plugins import NXBTPlugin, AutomationPlugin
from axiom.memory.sleep_cycle import SleepCycleDaemon

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
        # Create LLM client
        model = os.environ.get("AXIOM_MODEL", "llama3:8b")
        self.ollama = OllamaClient(OllamaConfig(model=model))
        
        # Create unified memory store backed by persistent database
        axiom_dir = Path.home() / ".axiom"
        axiom_dir.mkdir(exist_ok=True, parents=True)
        db_path = str(axiom_dir / "axiom.db")
        self.memory = SyncMemoryStore(db_path, embedding_provider=self.ollama)
        self.memory_store = self.memory  # Alias for backward compatibility internally
        
        # Pass unified memory store to engine
        self.engine = Engine(memory=self.memory)
        
        self.tool_registry = ToolRegistry(self.engine.registry)
        self.orchestrator = OrchestratorAgent(self.tool_registry, self.engine.event_bus, self.memory_store, llm=self.ollama)
        self._event_log = []
        self._closed = False
        self._subscribe_events()
        self._init_system()
        
        # Start Sleep Cycle Daemon
        self.sleep_daemon = SleepCycleDaemon(self.engine.event_bus, self.memory)
        self.sleep_daemon.start()
    
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
        """Run an async coroutine from synchronous CLI context."""
        from axiom.core.async_bridge import run_sync
        return run_sync(coro)
    
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
        
        # Bridge legacy brain.action_registry actions into the modern tool system.
        tools.extend(create_legacy_tools())
        
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
        except KeyboardInterrupt:
            print("\n\n[Generation cancelled by user]")
            # Optionally store an aborted message, but for now just return cleanly
            return
        except Exception as e:
            print(f"\nError processing request: {e}\n")
            logger.exception(f"Error in do_ask: {e}")

    def do_eval(self, arg: str) -> None:
        """Run the Autonomous SWE-Bench Evaluation Harness: eval --run-suite"""
        if "--run-suite" not in arg:
            print("Usage: eval --run-suite")
            return
            
        print("\n[Starting SWE-Bench Autonomous Evaluation...]")
        
        try:
            from axiom.evals.swe_harness import SWEBenchHarness
            harness = SWEBenchHarness(self.engine)
            report = self._run_async(harness.run_suite())
            
            # Save the report
            eval_dir = Path.cwd() / "eval_reports"
            eval_dir.mkdir(exist_ok=True)
            report_path = eval_dir / "swe_bench_scorecard.md"
            report_path.write_text(report)
            
            print("\n" + "="*60)
            print(report)
            print("="*60)
            print(f"\nScorecard saved to: {report_path}\n")
            
        except Exception as e:
            print(f"\nError running evaluation: {e}\n")
            logger.exception(f"Error in do_eval: {e}")

    def do_monitor(self, arg: str) -> None:
        """Launch the Interactive Textual TUI System Monitor: monitor"""
        try:
            from axiom.client.tui import AxiomMonitorApp
            app = AxiomMonitorApp()
            # Run the TUI (this is a blocking call that takes over the terminal)
            app.run()
        except ImportError:
            print("Error: Required dependencies for monitor not found. Please install textual.")
        except Exception as e:
            print(f"Error launching monitor: {e}")
            logger.exception(f"Error in do_monitor: {e}")
    
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
        
    def do_memory(self, arg: str) -> None:
        """Memory management commands: memory --compact"""
        if arg.strip() == "--compact":
            print("Running memory compaction sweep...")
            try:
                from axiom.core.async_bridge import run_sync
                from axiom.memory.compactor import MemoryCompactor
                db = self.memory.store._conn()
                compactor = MemoryCompactor(db)
                result = run_sync(compactor.run_compaction())
                print(f"Compaction complete. Scanned: {result['scanned']}, Merged: {result['merged']}, Deleted: {result['deleted']}")
            except Exception as e:
                print(f"Error during memory compaction: {e}")
                logger.exception("Memory compaction failed")
        else:
            print("Usage: memory --compact")
    
    def do_daemon(self, arg: str) -> None:
        """Manage the headless background daemon: daemon [start|stop|status]"""
        cmd = arg.strip().lower()
        if cmd == "start":
            print("Starting AXIOM Daemon...")
            try:
                from axiom.core.ipc_server import AxiomDaemon
                import asyncio
                
                # We need to run the asyncio loop forever in the main thread for the daemon.
                async def run_daemon():
                    daemon = AxiomDaemon(self)
                    await daemon.start()
                    print(f"Daemon running. Token: {daemon.token}")
                    try:
                        # Block forever
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        pass
                    finally:
                        await daemon.stop()
                        
                # Start the loop
                asyncio.run(run_daemon())
                
            except KeyboardInterrupt:
                print("\nDaemon stopped by user.")
            except Exception as e:
                print(f"Failed to start daemon: {e}")
                logger.exception("Daemon start failed")
                
        elif cmd == "stop":
            print("Stopping AXIOM Daemon...")
            # We connect via UDS and send stop command
            try:
                import socket
                sock_path = Path.home() / ".axiom" / "axiom.sock"
                if not sock_path.exists():
                    print("Daemon is not running (socket not found).")
                    return
                
                if os.name != 'nt':
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(str(sock_path))
                    msg = json.dumps({"jsonrpc": "2.0", "method": "axiom.stop", "id": 1})
                    sock.sendall(msg.encode("utf-8") + b"\n")
                    response = sock.recv(4096)
                    print(f"Response: {response.decode('utf-8').strip()}")
                    sock.close()
                else:
                    print("Stop via UDS not supported on Windows yet. Press Ctrl+C in daemon window.")
            except Exception as e:
                print(f"Failed to stop daemon: {e}")
                
        elif cmd == "status":
            # Check if UDS exists and connects
            sock_path = Path.home() / ".axiom" / "axiom.sock"
            if not sock_path.exists():
                print("Daemon is offline.")
                return
                
            try:
                import socket
                if os.name != 'nt':
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(str(sock_path))
                    msg = json.dumps({"jsonrpc": "2.0", "method": "axiom.status", "id": 1})
                    sock.sendall(msg.encode("utf-8") + b"\n")
                    response = json.loads(sock.recv(4096).decode("utf-8").strip())
                    sock.close()
                    if response.get("result"):
                        print("Daemon is ONLINE.")
                        print(json.dumps(response["result"], indent=2))
                    else:
                        print("Daemon returned error.")
                else:
                    print("Daemon might be running (UDS check skipped on Windows).")
            except ConnectionRefusedError:
                print("Daemon is offline (stale socket).")
            except Exception as e:
                print(f"Failed to check status: {e}")
                
        else:
            print("Usage: daemon [start|stop|status]")
            
    def do_quit(self, arg: str) -> None:
        """Exit AXIOM"""
        print("\nShutting down AXIOM...")
        self.close()
        print("Goodbye!")
        return True

    def close(self) -> None:
        """Release engine, memory, and LLM client resources exactly once."""
        if self._closed:
            return
        self._closed = True
        if hasattr(self, 'sleep_daemon'):
            self.sleep_daemon.stop()
        self.engine.shutdown()
        self.memory.close()
        self.ollama.close()
        shutdown_bridge()

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
  trace --last       - Replay telemetry from the last execution
  exit/quit          - Exit AXIOM
  help               - Show this help message
            """)
            print("="*60 + "\n")
    
    def emptyline(self) -> None:
        """Handle empty line input."""
        pass

    def do_trace(self, arg: str) -> None:
        """Trace telemetry: trace --last"""
        trace_file = Path.home() / ".axiom" / "traces" / "flight_recorder.jsonl"
        if not trace_file.exists():
            print("No traces found. Run a task first.")
            return
            
        print("\n=== FLIGHT RECORDER TELEMETRY ===")
        events = []
        try:
            with open(trace_file, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception as e:
            print(f"Error reading trace file: {e}")
            return
            
        if not events:
            print("Trace file is empty.")
            return
            
        # If --last, find the last session_id
        session_id = None
        for evt in reversed(events):
            if evt.get("event_type") == "orchestrator.task.received":
                data = evt.get("data") or {}
                # The payload might be nested under 'payload' due to bus.published meta-event wrapping
                if "payload" in data and "session_id" in data["payload"]:
                    session_id = data["payload"]["session_id"]
                    break
        
        filtered = events[-50:] if not session_id else [e for e in events if e.get("data", {}).get("session_id") == session_id or e.get("data", {}).get("payload", {}).get("session_id") == session_id]
        
        for evt in filtered:
            etype = evt.get("event_type")
            ts = evt.get("timestamp")
            data = evt.get("data", {})
            if "payload" in data:
                data = data["payload"]
            
            if etype == "loop.cycle":
                print(f"[{ts}] LOOP CYCLE (Round {data.get('round')}): {data.get('duration_ms', 0):.2f}ms | Queue Depth: {data.get('queue_depth')}")
            elif etype == "tool.executed":
                print(f"[{ts}] TOOL EXECUTED ({data.get('tool_name')}): {data.get('duration_ms', 0):.2f}ms | Success: {data.get('success')}")
            elif etype == "memory.retrieved":
                print(f"[{ts}] MEMORY LATENCY: {data.get('latency_ms', 0):.2f}ms | Results: {data.get('results_count')}")
            elif etype in ("orchestrator.task.received", "orchestrator.task.completed"):
                print(f"\n[{ts}] {etype.upper()}: {data.get('task')}")
        print("=================================\n")

    def do_replay(self, arg: str) -> None:
        """Alias for trace --last"""
        self.do_trace("--last")


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
