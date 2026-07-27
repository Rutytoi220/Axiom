"""AXIOM GUI — Async Signal Bridge.

Bridges AXIOM's synchronous EventBus and async OrchestratorAgent
to Qt's main thread via thread-safe Signal emissions.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from PySide6.QtCore import QObject, Signal, QThread, Slot

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

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_bus = None
        self._orchestrator = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API (called from the Qt main thread)
    # ------------------------------------------------------------------

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the qasync event loop so we can schedule coroutines."""
        self._loop = loop

    def set_event_bus(self, event_bus: Any) -> None:
        """Attach the AXIOM EventBus and subscribe to relevant events."""
        self._event_bus = event_bus
        self._subscribe_to_bus()

    def set_orchestrator(self, orchestrator: Any) -> None:
        """Register the OrchestratorAgent for async task dispatch."""
        self._orchestrator = orchestrator

    def refresh_models(self) -> None:
        """Trigger a background refresh of the available models."""
        if self._orchestrator and hasattr(self._orchestrator, "_llm"):
            llm = self._orchestrator._llm
            if hasattr(llm, "refresh_models"):
                # Spawn non-blocking background thread to refresh cache
                import threading
                threading.Thread(target=llm.refresh_models, daemon=True).start()

    def submit_task(self, user_input: str) -> None:
        """Schedule an orchestrator run on the async event loop.

        This is the *only* correct entry-point for sending a user message.
        It schedules a coroutine on the async loop (running in the Qt
        thread via qasync) so inference never blocks the UI.
        """
        if self._loop is None:
            self.error_occurred.emit("Event loop not initialised — cannot submit task.")
            return
        if self._orchestrator is None:
            self.error_occurred.emit("Orchestrator not attached — cannot submit task.")
            return
        asyncio.run_coroutine_threadsafe(self._run_task(user_input), self._loop)

    # ------------------------------------------------------------------
    # Internal async task runner
    # ------------------------------------------------------------------

    async def _run_task(self, user_input: str) -> None:
        """Run the orchestrator and stream results back via signals."""
        try:
            # OrchestratorAgent.run is a sync method, run it in thread pool
            result = await self._loop.run_in_executor(
                None,
                lambda: self._orchestrator.run(user_input, use_tools=True),
            )
            # If the result is a simple AgentResult/dict
            if hasattr(result, "output"):
                text = result.output.get("response", "")
            elif isinstance(result, dict):
                text = result.get("response", str(result))
            else:
                text = str(result)

            # Emit the final complete response
            self.response_finished.emit(text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Orchestrator run failed: %s", exc)
            self.error_occurred.emit(f"Error: {exc}")

    # ------------------------------------------------------------------
    # EventBus subscription handlers (called from EventBus thread)
    # ------------------------------------------------------------------

    def _subscribe_to_bus(self) -> None:
        """Wire EventBus events to Qt signal emitters."""
        if self._event_bus is None:
            return
        self._event_bus.subscribe("llm.token", self._on_llm_token)
        self._event_bus.subscribe("tool.*", self._on_tool_event)
        self._event_bus.subscribe("telemetry.*", self._on_telemetry_event)
        self._event_bus.subscribe("orchestrator.*", self._on_orchestrator_event)
        self._event_bus.subscribe("swarm.*", self._on_swarm_event)

    def _on_swarm_event(self, event: Any) -> None:
        """Relay swarm telemetry to the Qt thread."""
        agent = event.data.get("agent_name", "Unknown")
        if event.event_type == "swarm.agent.started":
            self.swarm_agent_started.emit(agent, str(event.data.get("assigned_task")))
        elif event.event_type == "swarm.agent.token":
            self.swarm_agent_token.emit(agent, str(event.data.get("chunk")))
        elif event.event_type == "swarm.agent.completed":
            self.swarm_agent_completed.emit(agent, str(event.data.get("result_summary")))

    def _on_llm_token(self, event: Any) -> None:
        """Relay LLM streaming tokens to the Qt thread."""
        token = event.data.get("token", "")
        if token:
            self.token_received.emit(token)

    def _on_tool_event(self, event: Any) -> None:
        """Relay tool start/finish events."""
        tool_id = event.data.get("tool_name", event.data.get("tool_id", "unknown_tool"))
        status = event.data.get("status", event.event_type)
        message = event.data.get("message", "")
        self.tool_status_changed.emit(tool_id, f"{status}: {message}")

    def _on_telemetry_event(self, event: Any) -> None:
        """Relay telemetry snapshots for the expert drawer."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
        except Exception:
            cpu, ram = 0.0, 0.0

        from axiom.config import get_config
        config = get_config()

        payload = {
            "model": event.data.get("model", config.ollama_model or "—"),
            "auth_mode": config.auth_mode.name,
            "cpu": cpu,
            "ram": ram,
            **event.data,
        }
        self.telemetry_updated.emit(payload)

    def _on_orchestrator_event(self, event: Any) -> None:
        """Relay orchestrator completion events."""
        if event.event_type == "orchestrator.task.completed":
            response = event.data.get("response", "")
            if response:
                self.response_finished.emit(response)
        elif event.event_type == "orchestrator.error":
            self.error_occurred.emit(event.data.get("error", "Unknown error"))
