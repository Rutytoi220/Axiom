"""
Tests for WorkspaceTransactionManager — atomic filesystem rollback engine.

Covers:
  - Clean rollback of modified files restores exact prior state.
  - Committing cleans the staging directory with no side effects.
  - Partial rollback (only files that were snapshotted are touched).
  - New files created mid-plan are deleted on rollback.
  - Staging cap enforcement aborts before any mutation.
  - EventBus integration: plan.failed triggers automatic rollback.
  - Context-manager protocol (with-statement).
  - OrchestratorAgent integration: mid-plan failure restores files.
"""

import shutil
import time
from pathlib import Path

import pytest

from axiom.core.transaction import (
    WorkspaceTransactionManager,
    StagingCapExceeded,
    MUTATING_TOOL_NAMES,
)
from axiom.core.events import EventBus, Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Basic snapshot + rollback
# ---------------------------------------------------------------------------

def test_rollback_restores_modified_file(tmp_path):
    """A modified file is restored to its original content on rollback."""
    target = tmp_path / "hello.txt"
    _write(target, "original content")

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.begin()
    txn.snapshot(target)

    # Simulate a tool overwriting the file
    _write(target, "corrupted content")
    assert _read(target) == "corrupted content"

    txn.rollback()

    assert target.exists(), "File should still exist after rollback"
    assert _read(target) == "original content", "Content must be restored"


def test_rollback_multiple_files(tmp_path):
    """All snapshotted files are restored on rollback."""
    files = {}
    for name in ("a.txt", "b.txt", "c.txt"):
        p = tmp_path / name
        _write(p, f"original {name}")
        files[name] = p

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.begin()
    for p in files.values():
        txn.snapshot(p)

    # Corrupt all files
    for name, p in files.items():
        _write(p, f"corrupted {name}")

    txn.rollback()

    for name, p in files.items():
        assert _read(p) == f"original {name}", f"{name} was not restored"


def test_rollback_partial_snapshot(tmp_path):
    """Only files that were actually snapshotted are touched on rollback."""
    snapshotted = tmp_path / "tracked.txt"
    untracked = tmp_path / "untracked.txt"
    _write(snapshotted, "original")
    _write(untracked, "unrelated")

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.begin()
    txn.snapshot(snapshotted)

    _write(snapshotted, "modified")
    _write(untracked, "also modified")

    txn.rollback()

    assert _read(snapshotted) == "original", "Snapshotted file must be restored"
    assert _read(untracked) == "also modified", "Untracked file must not be touched"


# ---------------------------------------------------------------------------
# 2. New files
# ---------------------------------------------------------------------------

def test_rollback_deletes_new_files(tmp_path):
    """Files that didn't exist before the transaction are deleted on rollback."""
    new_file = tmp_path / "brand_new.txt"
    assert not new_file.exists()

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.begin()
    txn.snapshot(new_file)  # doesn't exist yet → sentinel

    # Simulate tool creating it
    _write(new_file, "I was just created")
    assert new_file.exists()

    txn.rollback()

    assert not new_file.exists(), "New file must be deleted on rollback"


# ---------------------------------------------------------------------------
# 3. Commit
# ---------------------------------------------------------------------------

def test_commit_cleans_staging_dir(tmp_path):
    """Committing deletes the staging directory and leaves the workspace intact."""
    target = tmp_path / "file.txt"
    _write(target, "original")
    staging_root = tmp_path / ".staging"

    txn = WorkspaceTransactionManager(staging_root=staging_root, verbose=False)
    txn.begin()
    txn.snapshot(target)
    txn_staging_dir = txn._staging_dir

    _write(target, "new content")

    txn.commit()

    assert not txn_staging_dir.exists(), "Staging dir must be removed after commit"
    assert _read(target) == "new content", "Committed content must be preserved"


def test_commit_idempotent_on_inactive(tmp_path):
    """Calling commit() on an inactive transaction is a no-op."""
    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.commit()  # Should not raise


# ---------------------------------------------------------------------------
# 4. Staging cap enforcement
# ---------------------------------------------------------------------------

def test_staging_cap_exceeded_before_mutation(tmp_path):
    """StagingCapExceeded is raised before any disk copy happens."""
    big_file = tmp_path / "big.bin"
    big_file.write_bytes(b"x" * 100)  # 100 bytes

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    # Override cap to something tiny for the test
    txn._staging_bytes = 0
    from axiom.core import transaction as txn_mod
    original_cap = txn_mod.STAGING_CAP_BYTES
    txn_mod.STAGING_CAP_BYTES = 50  # 50 bytes cap

    txn.begin()
    try:
        with pytest.raises(StagingCapExceeded, match="staging cap"):
            txn.snapshot(big_file)
    finally:
        txn_mod.STAGING_CAP_BYTES = original_cap
        txn.rollback()


# ---------------------------------------------------------------------------
# 5. Idempotency
# ---------------------------------------------------------------------------

def test_snapshot_is_idempotent(tmp_path):
    """Snapshotting the same file twice doesn't double-copy it."""
    target = tmp_path / "file.txt"
    _write(target, "content")

    txn = WorkspaceTransactionManager(staging_root=tmp_path / ".staging", verbose=False)
    txn.begin()
    txn.snapshot(target)
    count_before = txn.snapshot_count
    txn.snapshot(target)  # Second call — must be no-op
    count_after = txn.snapshot_count

    assert count_before == count_after == 1
    txn.rollback()


# ---------------------------------------------------------------------------
# 6. Context-manager protocol
# ---------------------------------------------------------------------------

def test_context_manager_commits_on_success(tmp_path):
    """Using `with WorkspaceTransactionManager()` commits on clean exit."""
    target = tmp_path / "cm.txt"
    _write(target, "before")
    staging_root = tmp_path / ".staging"

    with WorkspaceTransactionManager(staging_root=staging_root, verbose=False) as txn:
        txn.snapshot(target)
        _write(target, "after")
        staging_dir = txn._staging_dir

    assert not staging_dir.exists(), "Staging dir cleaned on commit"
    assert _read(target) == "after"


def test_context_manager_rolls_back_on_exception(tmp_path):
    """Using `with WorkspaceTransactionManager()` rolls back when an exception propagates."""
    target = tmp_path / "cm.txt"
    _write(target, "before")
    staging_root = tmp_path / ".staging"

    with pytest.raises(RuntimeError, match="deliberate"):
        with WorkspaceTransactionManager(staging_root=staging_root, verbose=False) as txn:
            txn.snapshot(target)
            _write(target, "after")
            raise RuntimeError("deliberate failure")

    assert _read(target) == "before", "File must be restored after exception"


# ---------------------------------------------------------------------------
# 7. EventBus integration
# ---------------------------------------------------------------------------

def test_plan_failed_event_triggers_rollback(tmp_path):
    """Publishing plan.failed on the EventBus triggers automatic rollback."""
    target = tmp_path / "event_test.txt"
    _write(target, "safe")

    bus = EventBus()
    txn = WorkspaceTransactionManager(
        bus=bus, staging_root=tmp_path / ".staging", verbose=False
    )
    txn.begin()
    txn.snapshot(target)
    _write(target, "unsafe")

    bus.publish(Event(
        event_type="plan.failed",
        source="test",
        data={"reason": "test", "step": 2, "total_steps": 5},
    ))

    assert _read(target) == "safe", "EventBus-triggered rollback must restore file"
    assert not txn.is_active, "Transaction must be inactive after auto-rollback"


def test_circuit_breaker_event_triggers_rollback(tmp_path):
    """Publishing circuit_breaker.triggered on the EventBus triggers automatic rollback."""
    target = tmp_path / "cb_test.txt"
    _write(target, "clean")

    bus = EventBus()
    txn = WorkspaceTransactionManager(
        bus=bus, staging_root=tmp_path / ".staging", verbose=False
    )
    txn.begin()
    txn.snapshot(target)
    _write(target, "dirty")

    bus.publish(Event(
        event_type="circuit_breaker.triggered",
        source="test",
        data={"step": 1, "total_steps": 5},
    ))

    assert _read(target) == "clean"


# ---------------------------------------------------------------------------
# 8. should_snapshot detection
# ---------------------------------------------------------------------------

def test_should_snapshot_mutating_tools():
    """Known mutating tool names are detected correctly."""
    txn = WorkspaceTransactionManager(verbose=False)
    for tool in ("write_file", "delete_file", "shell", "bash", "create_file", "patch_file"):
        assert txn.should_snapshot(tool), f"{tool} should be flagged as mutating"


def test_should_not_snapshot_read_tools():
    """Read-only tools are not flagged as mutating."""
    txn = WorkspaceTransactionManager(verbose=False)
    for tool in ("read_file", "list_dir", "search", "memory_retrieve"):
        assert not txn.should_snapshot(tool), f"{tool} must not be flagged as mutating"


# ---------------------------------------------------------------------------
# 9. OrchestratorAgent integration: mid-plan failure restores files
# ---------------------------------------------------------------------------

def test_orchestrator_rollback_on_max_rounds(tmp_path):
    """OrchestratorAgent rolls back filesystem mutations when it hits MAX_TOOL_ROUNDS."""
    from axiom.agents.orchestrator_agent import OrchestratorAgent
    from axiom.core.engine import Engine
    from axiom.memory import SyncMemoryStore
    import axiom.agents.orchestrator_agent as oa_mod

    # Keep MAX_TOOL_ROUNDS low so the test is fast.
    original_max = oa_mod.MAX_TOOL_ROUNDS
    oa_mod.MAX_TOOL_ROUNDS = 3

    target = tmp_path / "agent_target.txt"
    _write(target, "original content")
    target_str = str(target)

    db_path = str(tmp_path / "test.db")
    memory = SyncMemoryStore(db_path)
    engine = Engine(memory=memory)
    engine.initialize()

    class WritingTool:
        name = "write_file"
        schema = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}
        def execute(self, args):
            Path(args["path"]).write_text(args.get("content", "corrupted"), encoding="utf-8")
            return {"output": "written", "success": True}

    engine.registry.register_tool("write_file", WritingTool())

    # LLM that keeps writing to the file forever (will hit MAX_TOOL_ROUNDS)
    class InfiniteWriterLLM:
        def __init__(self): self.call_count = 0
        def chat_with_tools(self, messages, tools, **kw):
            self.call_count += 1
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"name": "write_file", "arguments": {"path": target_str, "content": "corrupted"}}],
            }
        def chat(self, messages, **kw):
            return ""

    agent = OrchestratorAgent(registry=engine.registry, bus=engine.event_bus, memory=memory)
    agent.set_llm(InfiniteWriterLLM())

    result = agent.run("Write to the file forever")
    engine.shutdown()

    # Restore original limit
    oa_mod.MAX_TOOL_ROUNDS = original_max

    # The file must be back to its original content because rollback fired.
    assert _read(target) == "original content", (
        f"Agent rollback must restore file. Got: {_read(target)!r}"
    )
