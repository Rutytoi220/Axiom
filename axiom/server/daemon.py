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
from axiom.core.events import Event

logger = logging.getLogger(__name__)

class AxiomDaemonServer:
    def __init__(self):
        self.cli = CLI()
        self.event_bus = self.cli.engine.event_bus
        
        # Start background services that used to run in GUI
        self.scheduler_service = BackgroundSchedulerService(event_bus=self.event_bus)
        self.scheduler_service.start()
        
        self.sys_watchdog = SystemHealthWatchdog(submit_task_callback=self._submit_task)
        
        self.dir_watchdog = DirectoryWatchdog()
        # The loop isn't running yet, we will start it in run()
        
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
        
        for ws in list(self.clients):
            asyncio.create_task(self._send_safe(ws, msg_str))

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
                            # Run async in executor to avoid blocking the websocket loop
                            loop = asyncio.get_running_loop()
                            asyncio.create_task(
                                loop.run_in_executor(None, self.cli.orchestrator.run, prompt, True)
                            )
                except Exception as e:
                    logger.error(f"Error handling WS message: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info("Client disconnected.")

    async def run(self):
        loop = asyncio.get_running_loop()
        self.dir_watchdog.start(loop)
        
        logger.info("Starting AXIOM Daemon WebSocket server on ws://127.0.0.1:9410")
        async with websockets.serve(self.handle_client, "127.0.0.1", 9410):
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
