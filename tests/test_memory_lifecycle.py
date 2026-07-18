"""Lifecycle tests for synchronous memory consumers."""

from pathlib import Path

from axiom.memory import SyncMemoryStore


def test_memory_manager_close_is_idempotent(tmp_path: Path):
    """Managers can be closed repeatedly without leaving an active store."""
    manager = SyncMemoryStore(str(tmp_path / "memory.db"))

    manager.close()
    manager.close()

    assert manager._store._initialized is False
