"""AXIOM GUI — Async Signal Bridge.

Bridges AXIOM's synchronous EventBus and async OrchestratorAgent
to Qt's main thread via thread-safe Signal emissions.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import subprocess
from typing import Any

from PySide6.QtCore import QObject, Signal, QThread, Slot
from axiom.client.ipc_client import AxiomDaemonClient

logger = logging.getLogger(__name__)


class AxiomBridge(QObject):
    """Thread-safe bridge between the AXIOM EventBus and the PySide6 UI.

    All Qt signals are emitted from the Qt main thread (via
    ``QMetaObject.invokeMethod`` / ``Signal`` auto-connection), so
    widget access is always safe.

    Signals
    -------
    token_received(str)
        Streamed LLM markdown chunk — connect to the chat renderer.
    tool_status_changed(str, str)
        (tool_id, status_message) emitted when a tool starts/finishes.
    telemetry_updated(dict)
        Routing telemetry snapshot: model, auth_mode, cpu %, ram %.
    response_finished(str)
        Complete aggregated response text when streaming ends.
    error_occurred(str)
        Human-readable error message.
    """

    # --- Qt Signals (all emitted from Qt thread) ---
    token_received: Signal = Signal(str)
    tool_status_changed: Signal = Signal(str, str)
    telemetry_updated: Signal = Signal(dict)
    response_finished: Signal = Signal(str)
    error_occurred: Signal = Signal(str)
    request_gui_auth: Signal = Signal(str, str, dict)
    
    # Swarm Signals
    swarm_agent_started: Signal = Signal(str, str)
    swarm_agent_token: Signal = Signal(str, str)
    swarm_agent_completed: Signal = Signal(str, str)
    connection_status_changed: Signal = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = AxiomDaemonClient()
        self._client.on_event = self._on_daemon_event
        self._client.on_connect = self._on_daemon_connect
        self._client.on_disconnect = self._on_daemon_disconnect
        self._lock = threading.Lock()

    def _on_daemon_connect(self):
        self.connection_status_changed.emit(True)
        
    def _on_daemon_disconnect(self):
        self.connection_status_changed.emit(False)

    # ------------------------------------------------------------------
    # Public API (called from the Qt main thread)
    # ------------------------------------------------------------------
    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the qasync event loop so we can schedule coroutines."""
        self._loop = loop

    def initialize_client(self) -> None:
        """Attempt to connect to the daemon, starting it if necessary."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._connect_to_daemon(), self._loop)

    async def _connect_to_daemon(self):
        success = await self._client.connect()
        if not success:
            logger.info("Daemon offline, attempting to start via systemctl...")
            try:
                subprocess.run(['systemctl', '--user', 'start', 'axiom.service'], check=False)
                await asyncio.sleep(1.0)
                await self._client.connect()
            except Exception as e:
                logger.error(f"Failed to start daemon: {e}")

    def refresh_models(self) -> None:
        """Trigger a background refresh of the available models."""
        pass

    def submit_task(self, user_input: str) -> None:
        """Schedule an orchestrator run on the async event loop.

        This is the *only* correct entry-point for sending a user message.
        It schedules a coroutine on the async loop (running in the Qt
        thread via qasync) so inference never blocks the UI.
        """
        if self._loop is None:
            self.error_occurred.emit("Event loop not initialised — cannot submit task.")
            return
        if not self._client.is_connected:
            self.error_occurred.emit("Daemon offline — cannot submit task.")
            return
        asyncio.run_coroutine_threadsafe(self._client.submit_task(user_input), self._loop)

    # ------------------------------------------------------------------
    # Internal async task runner
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # EventBus subscription handlers (called from EventBus thread)
    # ------------------------------------------------------------------

    def _on_daemon_event(self, data: dict) -> None:
        """Route incoming daemon JSON events to Qt signals."""
        event_type = data.get("event_type", "")
        payload = data.get("payload", {})
        
        if event_type == "llm.token":
            self.token_received.emit(payload.get("chunk", ""))
        elif event_type.startswith("tool."):
            tool_id = payload.get("tool_id", "Unknown Tool")
            if event_type == "tool.started":
                self.tool_status_changed.emit(tool_id, f"Running {tool_id}...")
            elif event_type == "tool.finished":
                self.tool_status_changed.emit(tool_id, f"{tool_id} completed.")
        elif event_type == "telemetry.update":
            self.telemetry_updated.emit(payload)
        elif event_type == "orchestrator.finished":
            self.response_finished.emit(payload.get("response", ""))
        elif event_type.startswith("swarm."):
            self._on_swarm_event(event_type, payload)

    def _on_swarm_event(self, event_type: str, payload: dict) -> None:
        """Relay swarm telemetry to the Qt thread."""
        agent = payload.get("agent_name", "Unknown")
        if event_type == "swarm.agent.started":
            self.swarm_agent_started.emit(agent, str(payload.get("assigned_task")))
        elif event_type == "swarm.agent.token":
            self.swarm_agent_token.emit(agent, str(payload.get("chunk")))
        elif event_type == "swarm.agent.completed":
            self.swarm_agent_completed.emit(agent, str(payload.get("result_summary")))

