"""Tests for axiom.agents.sync_adapter — SyncAgentAdapter base class."""

import pytest
from unittest.mock import MagicMock

from axiom.agents.sync_adapter import SyncAgentAdapter
from axiom.agents.base import AgentResult


class ConcreteAdapter(SyncAgentAdapter):
    """Minimal concrete subclass for testing the base class."""

    def run(self, task: str):
        self._execution_count += 1
        return AgentResult(success=True, output=f"echo: {task}")


class FailingAdapter(SyncAgentAdapter):
    """Adapter whose run raises an exception."""

    def run(self, task: str):
        raise ValueError("deliberate failure")


class TestSyncAgentAdapter:
    def test_run_raises_not_implemented(self):
        adapter = SyncAgentAdapter("base")
        with pytest.raises(NotImplementedError, match="must implement run"):
            adapter.run("task")

    def test_concrete_run(self):
        adapter = ConcreteAdapter("worker")
        result = adapter.run("hello")
        assert result.success is True
        assert result.output == "echo: hello"

    def test_execution_count_increments(self):
        adapter = ConcreteAdapter("worker")
        adapter.run("a")
        adapter.run("b")
        info = adapter.get_info()
        assert info["execution_count"] == 2

    def test_get_info_defaults(self):
        adapter = SyncAgentAdapter("base")
        info = adapter.get_info()
        assert info["name"] == "base"
        assert info["state"] == "idle"
        assert info["execution_count"] == 0

    def test_get_info_subclass_override(self):
        adapter = ConcreteAdapter("w")
        adapter.description = "custom desc"
        info = adapter.get_info()
        assert info["description"] == "custom desc"

    def test_emit_with_bus(self):
        bus = MagicMock()
        adapter = SyncAgentAdapter("w", bus=bus)
        adapter._emit("test.event", {"key": "val"})
        bus.publish_sync.assert_called_once_with("test.event", {"key": "val"})

    def test_emit_without_bus(self):
        adapter = SyncAgentAdapter("w")
        adapter._emit("test.event", {"key": "val"})  # should not raise

    def test_emit_bus_without_publish_sync(self):
        adapter = SyncAgentAdapter("w", bus=object())
        adapter._emit("test.event", {})  # should not raise

    def test_emit_bus_exception_silenced(self):
        bus = MagicMock()
        bus.publish_sync.side_effect = RuntimeError("bus error")
        adapter = SyncAgentAdapter("w", bus=bus)
        adapter._emit("test.event", {})  # should not raise

    def test_log_appends_to_steps(self):
        adapter = SyncAgentAdapter("w")
        steps = []
        adapter._log("step one", steps)
        adapter._log("step two", steps)
        assert steps == ["step one", "step two"]

    def test_stores_registry_and_memory(self):
        reg = MagicMock()
        mem = MagicMock()
        adapter = SyncAgentAdapter("w", registry=reg, memory=mem)
        assert adapter.registry is reg
        assert adapter.memory is mem
