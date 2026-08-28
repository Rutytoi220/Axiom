import asyncio
import json
import logging
import os
import sys
from pathlib import Path
import websockets

from axiom.api.cli import CLI
from axiom.services.watchdog_service import DirectoryWatchdog
from axiom.services.scheduler_service import BackgroundSchedulerService
from axiom.services.sys_watchdog import SystemHealthWatchdog
from axiom.services.governor import GovernorService
from axiom.memory.indexer import IndexerService
from axiom.core.events import Event

logger = logging.getLogger(__name__)

class AxiomDaemonServer:
    def __init__(self):
        self.cli = CLI()
        self.event_bus = self.cli.engine.event_bus
        
        self.scheduler_service = None
        self.telemetry = None
        self.governor = None
        self.swarm_router = None
        self.sys_watchdog = None
        self.governor_service = None
        self.indexer_service = None
        
        self.dir_watchdog = DirectoryWatchdog()
        self.clients = set()
        self.event_bus.subscribe("*", self._on_bus_event)

    async def initialize_background(self):
        from axiom.core.lifecycle import LifecycleState
        from axiom.core.events import Event
        
        # Helper to emit status
        def _emit_status(service_name, state):
            self.event_bus.publish_sync("startup.service.update", {"service": service_name, "state": state})

        try:
            self.scheduler_service = BackgroundSchedulerService(event_bus=self.event_bus)
            self.scheduler_service.start()
            _emit_status("scheduler", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            _emit_status("scheduler", LifecycleState.DEGRADED)

        try:
            from axiom.core.telemetry import TelemetryDaemon
            self.telemetry = TelemetryDaemon(event_bus=self.event_bus)
            self.telemetry.start()
            _emit_status("telemetry", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start telemetry: {e}")
            _emit_status("telemetry", LifecycleState.DEGRADED)

        try:
            from axiom.core.governor import ThermalGovernor
            self.governor = ThermalGovernor.instance(event_bus=self.event_bus)
            self.governor_service = GovernorService.instance(event_bus=self.event_bus)
            _emit_status("governor", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start governor: {e}")
            _emit_status("governor", LifecycleState.DEGRADED)

        try:
            from axiom.core.swarm_router import SwarmRouter
            self.swarm_router = SwarmRouter.instance(event_bus=self.event_bus)
            _emit_status("swarm_router", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start swarm_router: {e}")
            _emit_status("swarm_router", LifecycleState.DEGRADED)

        try:
            self.sys_watchdog = SystemHealthWatchdog(submit_task_callback=self._submit_task)
            _emit_status("sys_watchdog", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start sys_watchdog: {e}")
            _emit_status("sys_watchdog", LifecycleState.DEGRADED)

        try:
            self.indexer_service = IndexerService(event_bus=self.event_bus)
            self.indexer_service.start()
            _emit_status("indexer", LifecycleState.READY)
        except Exception as e:
            logger.error(f"Failed to start indexer: {e}")
            _emit_status("indexer", LifecycleState.DEGRADED)
            
        self.event_bus.publish_sync("startup.service.ready", {"state": LifecycleState.READY})
        
        self.clients = set()
        
        # Subscribe to EventBus to broadcast to websockets
        self.event_bus.subscribe("*", self._on_bus_event)

    def _submit_task(self, prompt: str):
        self.event_bus.publish_sync("orchestrator.trigger", data={"prompt": prompt, "source": "daemon_watchdog"})

    def _on_bus_event(self, event):
        """Broadcast internal events to all connected WS clients."""
        if not self.clients:
            return
            
        name = getattr(event, 'name', getattr(event, 'event_type', 'unknown'))
        payload = getattr(event, 'payload', getattr(event, 'data', None))
        
        # Only broadcast relevant events to frontend to save bandwidth
        if not name.startswith(("llm.", "tool.", "swarm.", "telemetry.", "orchestrator.")):
            return
            
        msg = {
            "type": "event",
            "event_type": name,
            "payload": payload
        }
        msg_str = json.dumps(msg, default=str)
        
        # We may be inside a ThreadPoolExecutor (e.g. from orchestrator LLM calls)
        # We must schedule the async task on the main loop thread-safely
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # We are not in the main thread with a running loop, find the actual loop
            # Fallback for some environments, though get_running_loop might throw here
            pass
            
        # Instead, let's just use the server's main loop if we can capture it
        if hasattr(self, '_loop') and self._loop:
            for ws in list(self.clients):
                asyncio.run_coroutine_threadsafe(self._send_safe(ws, msg_str), self._loop)
        else:
            # Fallback if _loop not set
            for ws in list(self.clients):
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(
                        lambda w=ws, m=msg_str: asyncio.create_task(self._send_safe(w, m))
                    )
                except Exception:
                    pass

    async def _send_safe(self, ws, msg: str):
        try:
            await ws.send(msg)
        except Exception:
            pass

    async def handle_client(self, websocket):
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    if action == "submit_task":
                        prompt = data.get("prompt")
                        if prompt:
                            # Run in executor to avoid blocking the websocket loop.
                            # run_in_executor returns a Future and schedules it automatically.
                            loop = asyncio.get_running_loop()
                            loop.run_in_executor(None, self.cli.orchestrator.run, prompt, True)
                    elif action == "reload_plugins":
                        logger.info("Hot-reloading plugins triggered via IPC...")
                        self.cli.orchestrator.reload_plugins()
                        await websocket.send(json.dumps({"type": "response", "action": "reload_plugins", "success": True}))
                    elif action == "get_tools":
                        tools = self.cli.orchestrator._tool_registry._core_registry.list_tools()
                        from axiom.config import get_config
                        disabled = getattr(get_config(), "disabled_plugins", [])
                        
                        tool_list = []
                        for tid, t in sorted(tools.items()):
                            desc = getattr(t, 'description', '')
                            if not desc and t.__doc__:
                                desc = t.__doc__.strip().split('\n')[0]
                            tool_list.append({
                                "id": tid,
                                "description": desc or "No description provided.",
                                "enabled": tid not in disabled
                            })
                            
                        await websocket.send(json.dumps({
                            "type": "response",
                            "action": "get_tools",
                            "data": tool_list
                        }))
                    elif action == "toggle_tool":
                        tool_id = data.get("tool_id")
                        enabled = data.get("enabled")
                        from axiom.config import get_config
                        config = get_config()
                        disabled_list = getattr(config, 'disabled_plugins', [])
                        
                        if enabled and tool_id in disabled_list:
                            disabled_list.remove(tool_id)
                        elif not enabled and tool_id not in disabled_list:
                            disabled_list.append(tool_id)
                            
                        config.disabled_plugins = disabled_list
                        config.save()
                        
                        await websocket.send(json.dumps({
                            "type": "response",
                            "action": "toggle_tool",
                            "success": True
                        }))
                except Exception as e:
                    logger.error(f"[Daemon] Error handling client message: {e}", exc_info=True)
        except Exception as we:
            logger.error(f"[Daemon] Client connection error: {we}")
        finally:
            self.clients.discard(websocket)
            logger.info("Client disconnected.")

    async def run(self):
        loop = asyncio.get_running_loop()
        self._loop = loop
        self.dir_watchdog.start(loop)
        
        logger.info("Starting AXIOM Daemon WebSocket server on ws://127.0.0.1:9410")
        
        # We start the server in the background
        start_server = websockets.serve(self.handle_client, "127.0.0.1", 9410)
        await start_server
        
        # Now spawn the heavy loading tasks in the background
        asyncio.create_task(self.initialize_background())
        
        await asyncio.Future()  # run forever

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    daemon = AxiomDaemonServer()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Daemon shutting down.")
        daemon.cli.close()

if __name__ == "__main__":
    main()
