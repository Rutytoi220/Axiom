"""AXIOM GUI Bridge Tests.

Uses pytest-qt to verify that AxiomBridge signals fire correctly when
the underlying EventBus publishes events, without raising thread-safety
exceptions.  Uses MagicMock for the OrchestratorAgent so we never make
real LLM calls.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# Guard: skip ALL tests if PySide6 isn't installed so the test suite
# doesn't fail on headless CI machines without Qt.
pytest.importorskip("PySide6", reason="PySide6 not installed — skipping GUI tests")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from axiom.core.events import EventBus, Event  # noqa: E402
from axiom.gui.bridge import AxiomBridge  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    """Module-scoped QCoreApplication so we can test signals without a display."""
    import sys
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    yield app


@pytest.fixture
def bridge(qapp):
    """Create a fresh AxiomBridge for each test."""
    return AxiomBridge()


@pytest.fixture
def event_bus():
    return EventBus()


class TestAxiomBridgeSignals:
    """Verify EventBus → Qt Signal wiring without touching real LLM."""

    def test_token_received_emits_on_llm_event(self, bridge, event_bus, qtbot):
        """Publishing an llm.token event must emit token_received Signal."""
        bridge.set_event_bus(event_bus)

        received: list[str] = []
        bridge.token_received.connect(received.append)

        event_bus.publish(Event(
            event_type="llm.token",
            source="test",
            data={"token": "Hello, world!"},
        ))

        assert received == ["Hello, world!"]

    def test_tool_status_changed_emits_on_tool_event(self, bridge, event_bus, qtbot):
        """Publishing a tool.started event must emit tool_status_changed."""
        bridge.set_event_bus(event_bus)

        calls: list[tuple[str, str]] = []
        bridge.tool_status_changed.connect(lambda tid, msg: calls.append((tid, msg)))

        event_bus.publish(Event(
            event_type="tool.started",
            source="test",
            data={"tool_id": "safe_file_search", "status": "started", "message": "Searching…"},
        ))

        assert len(calls) == 1
        assert calls[0][0] == "safe_file_search"
        assert "started" in calls[0][1]

    def test_telemetry_updated_emits_on_telemetry_event(self, bridge, event_bus, qtbot):
        """Publishing a telemetry event must emit telemetry_updated with cpu/ram keys."""
        bridge.set_event_bus(event_bus)

        updates: list[dict] = []
        bridge.telemetry_updated.connect(updates.append)

        with patch("psutil.cpu_percent", return_value=42.0), \
             patch("psutil.virtual_memory") as mock_vmem:
            mock_vmem.return_value.percent = 60.0
            event_bus.publish(Event(
                event_type="telemetry.snapshot",
                source="test",
                data={"model": "qwen3:8b"},
            ))

        assert len(updates) == 1
        assert updates[0]["model"] == "qwen3:8b"
        assert "cpu" in updates[0]
        assert "ram" in updates[0]

    def test_error_signal_emits_on_orchestrator_error(self, bridge, event_bus, qtbot):
        """Publishing orchestrator.error event must emit error_occurred."""
        bridge.set_event_bus(event_bus)

        errors: list[str] = []
        bridge.error_occurred.connect(errors.append)

        event_bus.publish(Event(
            event_type="orchestrator.error",
            source="test",
            data={"error": "LLM timed out"},
        ))

        assert errors == ["LLM timed out"]

    def test_no_thread_access_exception_on_multiple_events(self, bridge, event_bus, qtbot):
        """Emit 50 events rapidly and assert no exceptions surface."""
        bridge.set_event_bus(event_bus)

        tokens: list[str] = []
        bridge.token_received.connect(tokens.append)

        for i in range(50):
            event_bus.publish(Event(
                event_type="llm.token",
                source="stress_test",
                data={"token": f"tok{i}"},
            ))

        assert len(tokens) == 50

    def test_no_event_without_bus_attached(self, bridge, qtbot):
        """Signals must NOT raise if event_bus is not set."""
        received: list[str] = []
        bridge.token_received.connect(received.append)
        # Do NOT call bridge.set_event_bus — just verify nothing crashes
        assert received == []


class TestSubmitTask:
    """Verify task submission delegates correctly to the orchestrator."""

    def test_submit_task_without_loop_emits_error(self, bridge, qtbot):
        """submit_task before set_event_loop must gracefully emit error_occurred."""
        errors: list[str] = []
        bridge.error_occurred.connect(errors.append)
        bridge.submit_task("open a file")
        assert len(errors) == 1
        assert "Event loop" in errors[0] or "loop" in errors[0].lower()

    def test_submit_task_without_orchestrator_emits_error(self, bridge, qtbot):
        """submit_task without an orchestrator must gracefully emit error_occurred."""
        errors: list[str] = []
        bridge.error_occurred.connect(errors.append)
        bridge.set_event_loop(asyncio.new_event_loop())
        bridge.submit_task("do something")
        assert len(errors) == 1
        assert "rchestrator" in errors[0]
