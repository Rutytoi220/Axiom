"""AXIOM Command-line interface."""

import cmd
import json
import logging
import os
from pathlib import Path
from typing import Optional
from axiom.core import Engine, shutdown_bridge
from axiom.memory import SyncMemoryStore
from axiom.llm.universal_client import UniversalLLMClient
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.tool_registry import ToolRegistry
from axiom.tools.mcp_hub import MCPHub
from axiom.tools import (
    EchoTool,
    ShellTool,
    FileReadTool,
    FileWriteTool,
    SystemInfoTool
)
from axiom.legacy_wrapper import create_legacy_tools
from axiom.plugins import NXBTPlugin, AutomationPlugin
from axiom.plugins.visual_automation import VisualAutomationPlugin
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
    ║                    Type '/help' for commands                  ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    
    prompt = "axiom> "
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create LLM client
        from axiom.config import get_config
        config = get_config()
        if "AXIOM_MODEL" in os.environ:
            config.ollama_model = os.environ["AXIOM_MODEL"]
            
        self.ollama = UniversalLLMClient(default_model=config.ollama_model)
        
        # Validate dynamic models
        from axiom.core.config_service import initialize_model_config
        initialize_model_config(config, self.ollama)
        # Create unified memory store backed by persistent database
        axiom_dir = Path.home() / ".axiom"
        axiom_dir.mkdir(exist_ok=True, parents=True)
        db_path = str(axiom_dir / "axiom.db")
        self.memory = SyncMemoryStore(db_path, embedding_provider=self.ollama)
        self.memory_store = self.memory  # Alias for backward compatibility internally
        
        # Pass unified memory store to engine
        self.engine = Engine(memory=self.memory)
        
        self.tool_registry = ToolRegistry(self.engine.registry)
        self.mcp_hub = MCPHub(self.engine.registry)
        self.orchestrator = OrchestratorAgent(self.tool_registry, self.engine.event_bus, self.memory_store, llm=self.ollama)
        self._event_log = []
        self._closed = False
        self._subscribe_events()
        self._init_system()
        
        # Start Sleep Cycle Daemon and Routine Engine only in MainProcess
        import multiprocessing
        if multiprocessing.current_process().name == 'MainProcess':
            self.sleep_daemon = SleepCycleDaemon(self.engine.event_bus, self.memory, self.ollama)
            self.sleep_daemon.start()

            # Start Routine Engine
            from axiom.core.routine import RoutineEngine
            self.routine_engine = RoutineEngine(self)
            self.routine_engine.start()
        else:
            self.sleep_daemon = None
            self.routine_engine = None
    
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
        from axiom.tools.os_assist import SafeFileSearchTool, FileOpenerTool, AppLauncherTool, CaptureScreenContextTool
        from axiom.tools.document_reader import ReadDocumentContentTool
        tools = [
            EchoTool(),
            ShellTool(),
            FileReadTool("."),
            FileWriteTool("."),
            SystemInfoTool(),
            SafeFileSearchTool(),
            FileOpenerTool(),
            AppLauncherTool(),
            CaptureScreenContextTool(),
            ReadDocumentContentTool()
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
            AutomationPlugin(engine=self.engine),
            VisualAutomationPlugin(engine=self.engine)
        ]
        
        for plugin in plugins:
            if plugin.initialize():
                plugin.enable()
                self.engine.registry.register_plugin(plugin.plugin_id, plugin)
        
        logger.info(f"Initialized {len(plugins)} plugins")
    
    def do_ask(self, arg: str) -> None:
        """Ask AXIOM a question: ask <question> [--verbose]"""
        if not arg:
            print("Usage: ask <question> [--verbose]")
            return
            
        is_verbose = "--verbose" in arg
        if is_verbose:
            arg = arg.replace("--verbose", "").strip()
        
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
                    if tool_results and is_verbose:
                        output_str += "\n\n--- Tool calls ---"
                        for tr in tool_results:
                            output_str += f"\n  ▸ {tr['tool']}({json.dumps(tr['arguments'], default=str)[:80]})"
                elif isinstance(response.output, str):
                    output_str = response.output
                else:
                    output_str = json.dumps(response.output, indent=2, default=str)
            
            import re
            output_str = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", output_str, flags=re.IGNORECASE)
            output_str = output_str.replace("</think>", "").replace("<think>", "").strip()
            
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
    def do_run(self, arg: str) -> None:
        """Run an interactive magic DevEx workflow. Usage: run <prompt>"""
        if not arg.strip():
            print("Usage: run <prompt>")
            return
            
        from axiom.cli.interactive import InteractiveWorkflowRunner
        runner = InteractiveWorkflowRunner(engine=self.engine, orchestrator=self.orchestrator)
        
        try:
            # We must run this inside the async bridge because orchestrator.run is async but 
            # wait, orchestrator.run is synchronous here? Let's check:
            # In do_eval we do self._run_async(harness.run_suite())
            # orchestrator.run is synchronous (it has an _agentic_loop that runs until completion).
            runner.run(arg)
        except Exception as e:
            # Exception is already printed by InteractiveWorkflowRunner
            pass

    def do_commit(self, arg: str) -> None:
        """Commit the pending workspace transaction. Usage: commit"""
        txns = getattr(self.engine, 'active_transactions', [])
        if not txns:
            print("No active transaction to commit.")
            return
        txn = txns.pop()
        txn.commit()
        print(f"[✓] Successfully committed transaction.")

    def do_rollback(self, arg: str) -> None:
        """Rollback the pending workspace transaction. Usage: rollback"""
        txns = getattr(self.engine, 'active_transactions', [])
        if not txns:
            print("No active transaction to rollback.")
            return
        txn = txns.pop()
        txn.rollback()
        print(f"[✓] Successfully rolled back transaction.")

    def do_routine(self, arg: str) -> None:
        """Manage background routines. Usage: routine add "<prompt>", routine list, routine delete <id>"""
        parts = arg.split(maxsplit=1)
        if not parts:
            print("Usage: routine add \"<prompt>\", routine list, routine delete <id>")
            return
            
        cmd = parts[0].lower()
        if cmd == "list":
            routines = self.routine_engine.list_routines()
            if not routines:
                print("No active routines.")
                return
            for r in routines:
                print(f"[{r['id'][:8]}] {r['cron_expression']} -> {r['prompt']}")
        elif cmd == "add":
            if len(parts) < 2:
                print("Usage: routine add \"<prompt>\"")
                return
            prompt = parts[1].strip('"\'')
            print(f"Parsing natural language schedule via LLM...")
            cron_expr = self._run_async(self.routine_engine.parse_schedule_to_cron(prompt))
            rid = self.routine_engine.add_routine(prompt, cron_expr)
            print(f"[✓] Added routine {rid[:8]} running at '{cron_expr}'")
        elif cmd == "delete":
            if len(parts) < 2:
                print("Usage: routine delete <id>")
                return
            target_id = parts[1].strip()
            # Find full ID
            for r in self.routine_engine.list_routines():
                if r['id'].startswith(target_id):
                    self.routine_engine.delete_routine(r['id'])
                    print(f"[✓] Deleted routine {r['id'][:8]}")
                    return
            print(f"Routine {target_id} not found.")
        else:
            print("Unknown routine command.")

    def do_eval(self, arg: str) -> None:
        """Run the Autonomous SWE-Bench Evaluation Harness: eval --run-suite"""
        if "--run-suite" not in arg:
            print("Usage: eval --run-suite")
            return
            
        print("\n[Starting SWE-Bench Autonomous Evaluation...]")
        
        try:
            from axiom.evals.swe_harness import SWEBenchHarness
            from pathlib import Path
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

    def do_benchmark(self, arg: str) -> None:
        """Run the Autonomous SWE-Bench Benchmark Engine: benchmark run <path_to_issue_json>"""
        if not arg.startswith("run "):
            print("Usage: benchmark run <path_to_issue_json>")
            return
            
        path = arg.replace("run ", "").strip()
        print(f"\n[Starting SWE-Bench Evaluation Loop for {path}...]")
        
        try:
            from axiom.evals.swe_runner import SWERunner
            runner = SWERunner(self.engine)
            problem = runner.ingest_problem(path)
            
            print(f"Problem: {problem.problem_statement[:50]}...")
            
            result = self._run_async(runner.run_evaluation(problem))
            print("\n=== BENCHMARK TELEMETRY ===")
            print(result)
        except Exception as e:
            print(f"\nBenchmark failed: {e}\n")

    def do_gui(self, arg: str) -> None:
        """Trigger a single-turn visual desktop action: gui act <instruction>"""
        if not arg.startswith("act "):
            print('Usage: gui act "<instruction>"')
            return
            
        instruction = arg.replace("act ", "").strip().strip('"').strip("'")
        print(f"\n[Executing GUI Action: {instruction}...]")
        
        try:
            plugin = self.engine.registry.get_plugin("visual_automation")
            if not plugin:
                print("Error: Visual Automation Plugin is not loaded.")
                return
                
            success = plugin.execute_visual_task(instruction)
            if success:
                print("[✓] GUI Action Completed successfully.")
            else:
                print("[!] GUI Action Failed.")
        except Exception as e:
            print(f"\nGUI action failed: {e}\n")

    def do_repair(self, arg: str) -> None:
        """Trigger the Autonomous Self-Healing Engine on a directory: repair <path>"""
        if not arg.strip():
            print("Usage: repair <path>")
            return
            
        target_dir = arg.strip()
        print(f"\n[Starting Autonomous Self-Healing Engine on {target_dir}...]")
        
        try:
            from axiom.evals.swe_harness import SWEBenchHarness
            harness = SWEBenchHarness(self.engine)
            success = self._run_async(harness.repair(target_dir))
            
            print("\n" + "="*60)
            if success:
                print(f"[✓] Self-Repair SUCCESS: {target_dir} is fixed.")
            else:
                print(f"[✗] Self-Repair FAILED: Could not fix {target_dir}.")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"\nError during self-repair: {e}\n")
            logger.exception(f"Error in do_repair: {e}")

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
        print(f"\nLLM & Routing:")
        print(f"  Router: SmartRouter (qwen3:0.6b micro-model)")
        print(f"  Current model: {self.ollama.config.model}")
        provider = self.ollama.config.model.split("/")[0] if "/" in self.ollama.config.model else "ollama"
        print(f"  Provider: {provider}")
        
        # Vision status
        from axiom.perception.vision_pipeline import VisionPipeline
        vp = VisionPipeline()
        print(f"\nVision Pipeline:")
        print(f"  Enabled: {vp.is_available}")
        if vp.is_available:
            print(f"  Set-of-Mark Grid: Active")
        
        mcp_status = self.mcp_hub.get_status()
        print(f"\nMCP Hub:")
        print(f"  Connected Servers: {len(mcp_status['connected_servers'])}")
        print(f"  Bridged Tools: {mcp_status['bridged_tools_count']}")
        
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

    def do_model(self, arg: str) -> None:
        """Switch active model mid-flight: /model <provider/model_name>"""
        if not arg.strip():
            print("Usage: /model <provider/model_name>")
            return
        new_model = arg.strip()
        self.ollama.config.model = new_model
        # Save to config.json
        from axiom.config import get_config
        config = get_config()
        config.ollama_model = new_model
        config.save()
        print(f"[✓] Active Model set to: {new_model}")
        
        from axiom.core.events import Event
        self.engine.event_bus.publish(Event(event_type="ui.model_changed", source="CLI", data={"model": new_model}))

    def do_provider(self, arg: str) -> None:
        """Switch API gateway and prompt for keys: /provider <name>"""
        if not arg.strip():
            print("Usage: /provider <name>")
            return
        provider = arg.strip().upper()
        if f"{provider}_API_KEY" not in os.environ:
            import getpass
            key = getpass.getpass(f"Enter {provider}_API_KEY: ")
            os.environ[f"{provider}_API_KEY"] = key
        print(f"[✓] Provider {provider} is now active.")

    def do_mcp(self, arg: str) -> None:
        """Manage MCP servers: /mcp list | /mcp add <name> <command_or_url> [args...]"""
        parts = arg.strip().split()
        if not parts:
            print("Usage: /mcp list | /mcp add <name> <command_or_url> [args...]")
            return
        cmd = parts[0].lower()
        if cmd == "list":
            status = self.mcp_hub.get_status()
            print(f"\nMCP Servers ({len(status['connected_servers'])} connected):")
            for s in status['connected_servers']:
                if isinstance(s, dict):
                    print(f" - {s['name']} [{s['type']}] ({s['status']})")
                else:
                    print(f" - {s}")
            print(f"Total Bridged Tools: {status['bridged_tools_count']}\n")
        elif cmd == "add":
            if len(parts) < 3:
                print("Usage: /mcp add <name> <command_or_url> [args...]")
                return
            name = parts[1]
            command = parts[2]
            args = parts[3:]
            is_url = command.startswith("http://") or command.startswith("https://")
            target_type = "URL" if is_url else "command"
            print(f"Adding MCP server '{name}' via {target_type} '{command}'...")
            success = self.mcp_hub.add_server(name, command, args)
            if success:
                print(f"[✓] MCP Server '{name}' added successfully.")
            else:
                print(f"[✗] Failed to add MCP server '{name}'.")
        else:
            print("Unknown mcp command.")
    
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

    def do_service(self, arg: str) -> None:
        """Manage AXIOM as a systemd user service: service [install|start|stop|restart|status]"""
        args = arg.split()
        if not args:
            print("Usage: service [install|start|stop|restart|status]")
            return

        cmd = args[0].lower()
        
        from axiom.core.service_mgr import SystemdServiceManager
        mgr = SystemdServiceManager()

        if not mgr.is_supported():
            print("Error: Systemd user services are not supported on this OS/environment.")
            return

        if cmd == "install":
            print("Installing AXIOM systemd service...")
            if mgr.install():
                print("[✓] Service installed and enabled on boot.")
            else:
                print("[✗] Failed to install service.")
        elif cmd == "start":
            print("Starting service...")
            if mgr.start():
                print("[✓] Service started.")
            else:
                print("[✗] Failed to start service.")
        elif cmd == "stop":
            print("Stopping service...")
            if mgr.stop():
                print("[✓] Service stopped.")
            else:
                print("[✗] Failed to stop service.")
        elif cmd == "restart":
            print("Restarting service...")
            if mgr.restart():
                print("[✓] Service restarted.")
            else:
                print("[✗] Failed to restart service.")
        elif cmd == "status":
            print(mgr.status())
        else:
            print(f"Unknown service command: {cmd}")
            print("Usage: service [install|start|stop|restart|status]")
            
    def do_exit(self, arg: str) -> None:
        """Alias for quit"""
        return self.do_quit(arg)

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
    
    def precmd(self, line: str) -> str:
        """Route slash commands to system methods, else default to chat."""
        stripped = line.strip()
        if not stripped:
            return line
        if stripped == "EOF":
            return line
            
        if stripped.startswith("/"):
            return stripped[1:]
        
        # Backward compatibility for 'ask' and 'run' prefixes
        if stripped.startswith("ask "):
            return stripped
        if stripped.startswith("run "):
            return stripped
            
        # Default to ask
        return f"ask {stripped}"

    def do_help(self, arg: str) -> None:
        """Show help information"""
        if arg:
            super().do_help(arg)
        else:
            print("\n" + "="*60)
            print("AXIOM Commands")
            print("="*60)
            print("""
  (any text)         - Chat directly with AXIOM
  /ask <question>    - Ask AXIOM a question (legacy prefix)
  /tools             - List all registered tools
  /agents            - List all registered agents
  /plugins           - List all registered plugins
  /status            - Show system status
  /history           - Show conversation history
  /clear_history     - Clear conversation history
  /resume <id>       - Resume conversation/session by ID
  /memory_log        - Show memory event log
  /trace --last      - Replay telemetry from the last execution
  /service           - Manage AXIOM systemd user service
  /repair <path>     - Trigger Autonomous Self-Healing Engine on a directory
  /exit or /quit     - Exit AXIOM
  /help              - Show this help message
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

    def do_plugin(self, arg: str) -> None:
        """Manage AXIOM plugins. Usage: plugin <install|list|inspect> [args]"""
        args = arg.split()
        if not args:
            print("Usage: plugin <install|list|inspect> [args]")
            return
            
        cmd = args[0]
        plugin_root = Path.home() / ".axiom" / "plugins"
        
        from axiom.plugins.loader import PluginLoader
        loader = PluginLoader()
        
        if cmd == "list":
            if not plugin_root.exists():
                print("No plugins installed.")
                return
            print("\n=== INSTALLED PLUGINS ===")
            for path in plugin_root.iterdir():
                if path.is_dir() and (path / "plugin.toml").exists():
                    try:
                        manifest = loader.load_manifest(path)
                        print(f" - {manifest.name} (v{manifest.version}) by {manifest.author}")
                    except Exception as e:
                        print(f" - [INVALID] {path.name}: {e}")
            print("=========================\n")
            
        elif cmd == "install":
            if len(args) < 2:
                print("Usage: plugin install <path>")
                return
            src = Path(args[1]).resolve()
            if not src.exists() or not (src / "plugin.toml").exists():
                print(f"Error: Valid plugin.toml not found in {src}")
                return
                
            try:
                manifest = loader.load_manifest(src)
                dest = plugin_root / manifest.plugin_id
                if dest.exists():
                    import shutil
                    shutil.rmtree(dest)
                import shutil
                shutil.copytree(src, dest)
                print(f"Successfully installed plugin '{manifest.name}' to {dest}")
            except Exception as e:
                print(f"Failed to install plugin: {e}")
                
        elif cmd == "inspect":
            if len(args) < 2:
                print("Usage: plugin inspect <name>")
                return
            target_id = args[1]
            dest = plugin_root / target_id
            if not dest.exists():
                print(f"Plugin '{target_id}' not found.")
                return
            try:
                manifest = loader.load_manifest(dest)
                print(f"\n=== PLUGIN AUDIT: {manifest.name} ===")
                print(f"Version:       {manifest.version}")
                print(f"Description:   {manifest.description}")
                print(f"Entrypoint:    {manifest.module}.{manifest.entry_class}")
                print("\n[CAPABILITIES]")
                print(f" Filesystem:   {'GRANTED' if manifest.permissions.allows('filesystem') else 'DENIED'}")
                print(f" Network:      {'GRANTED' if manifest.permissions.allows('network') else 'DENIED'}")
                print(f" Shell:        {'GRANTED' if manifest.permissions.allows('shell') else 'DENIED'}")
                print("=======================================\n")
            except Exception as e:
                print(f"Error inspecting plugin: {e}")
                
        else:
            print(f"Unknown plugin command: {cmd}")

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

if __name__ == "__main__":
    import logging.config
    from pathlib import Path

    log_path = Path.home() / ".axiom" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
        },
        "handlers": {
            "file": {
                "level": "DEBUG",
                "class": "logging.FileHandler",
                "filename": str(log_path),
                "formatter": "standard",
            },
            "console": {
                "level": "WARNING",
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
        },
    }
    logging.config.dictConfig(logging_config)
    
    run_cli()
