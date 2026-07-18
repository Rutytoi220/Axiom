"""WorkspaceTransactionManager — Atomic filesystem rollback for AXIOM tool sequences.

Wraps multi-step autonomous tool execution so that either all filesystem
mutations succeed (commit) or the workspace is restored to its exact
pre-execution state (rollback).

Usage as a context manager::

    with WorkspaceTransactionManager(bus=event_bus, transaction_id="abc") as txn:
        txn.snapshot("/home/user/project/main.py")
        # ... execute tool that overwrites main.py ...
        # If an exception propagates, __exit__ calls rollback() automatically.

Or imperatively::

    txn = WorkspaceTransactionManager(bus=event_bus)
    txn.begin()
    txn.snapshot("/home/user/project/main.py")
    ...
    txn.rollback()   # or txn.commit()
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional, Set

from axiom.core.events import EventBus, Event

logger = logging.getLogger(__name__)

# Hard cap on total staging area size.  If a snapshot would push us over
# this limit we abort *before* touching the file so the user's workspace
# is always safe.
STAGING_CAP_BYTES: int = 50 * 1024 * 1024  # 50 MB

# Tool names that imply filesystem mutation and should trigger auto-snapshot.
MUTATING_TOOL_NAMES: frozenset[str] = frozenset({
    "write_file",
    "create_file",
    "delete_file",
    "move_file",
    "rename_file",
    "patch_file",
    "append_file",
    "shell",           # shell can do anything — we snapshot on best-effort
    "bash",
    "run_command",
})

# Sentinel stored in the snapshot registry when the original path did NOT
# exist (i.e. the tool is about to create a brand-new file).  On rollback
# we delete that file instead of trying to restore it.
_NEW_FILE_SENTINEL = "__NEW_FILE__"


class StagingCapExceeded(RuntimeError):
    """Raised when a snapshot would exceed the 50 MB staging cap."""


class WorkspaceTransactionManager:
    """Atomic filesystem snapshot / rollback engine.

    Parameters
    ----------
    bus:
        The AXIOM ``EventBus``.  When provided the manager subscribes to
        ``plan.failed`` and ``circuit_breaker.triggered`` and auto-rolls back.
    transaction_id:
        Unique identifier for this transaction.  Defaults to a random UUID.
    staging_root:
        Root directory for staging areas.  Defaults to ``~/.axiom/staging``.
    verbose:
        If ``True``, print human-readable feedback to stdout during rollback.
    """

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        transaction_id: Optional[str] = None,
        staging_root: Optional[Path] = None,
        verbose: bool = True,
        blackboard=None,
        session_id: Optional[str] = None,
    ) -> None:
        self._bus = bus
        self._txn_id = transaction_id or str(uuid.uuid4())
        self._staging_root = staging_root or (Path.home() / ".axiom" / "staging")
        self._staging_dir: Path = self._staging_root / self._txn_id
        self._verbose = verbose

        # Optional Blackboard reference — purged on commit/rollback to free RAM.
        self._blackboard = blackboard
        self._session_id = session_id

        # Maps absolute original path → absolute staging path (or _NEW_FILE_SENTINEL).
        self._snapshots: Dict[str, str] = {}
        # Tracks which files were newly created so we can delete them on rollback.
        self._new_files: Set[str] = set()

        self._active = False
        self._committed = False
        self._staging_bytes = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> "WorkspaceTransactionManager":
        """Explicitly start the transaction.  Called automatically by ``__enter__``."""
        if self._active:
            return self
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        self._active = True
        self._committed = False
        logger.debug("Transaction %s began; staging dir: %s", self._txn_id, self._staging_dir)

        if self._bus is not None:
            self._bus.subscribe("plan.failed", self._on_failure_event)
            self._bus.subscribe("circuit_breaker.triggered", self._on_failure_event)

        return self

    def commit(self) -> None:
        """Mark the transaction successful and clean up the staging directory."""
        if not self._active:
            return
        self._cleanup_staging()
        self._committed = True
        self._active = False
        self._unsubscribe_failure_events()
        logger.debug("Transaction %s committed; staging cleaned.", self._txn_id)
        self._purge_blackboard(reason="commit")

    def rollback(self) -> None:
        """Restore all snapshotted files to their pre-transaction state.

        This is the critical recovery path.  Each file that was backed up
        is atomically restored.  New files created by the failing plan are
        deleted.  Terminal feedback is printed when ``verbose=True``.
        """
        if not self._active:
            return

        modified_count = len(self._snapshots)
        if modified_count == 0:
            self._print("[!] Rollback triggered — no filesystem mutations to undo.")
            self._cleanup_staging()
            self._active = False
            self._unsubscribe_failure_events()
            self._purge_blackboard(reason="rollback")
            return

        self._print(f"[!] Rolling back {modified_count} modified file(s)…")

        restored = 0
        errors = []
        for original_path_str, backup_path_str in self._snapshots.items():
            original_path = Path(original_path_str)
            try:
                if backup_path_str == _NEW_FILE_SENTINEL:
                    # The file did not exist before the plan — delete it.
                    if original_path.exists():
                        original_path.unlink()
                        self._print(f"    ↩ Deleted (new file reverted): {original_path}")
                else:
                    backup_path = Path(backup_path_str)
                    if backup_path.exists():
                        original_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_path, original_path)
                        self._print(f"    ↩ Restored: {original_path}")
                    else:
                        errors.append(f"Backup missing for: {original_path}")
                restored += 1
            except Exception as exc:
                errors.append(f"Failed to restore {original_path}: {exc}")
                logger.error("Rollback error for %s: %s", original_path, exc, exc_info=True)

        self._cleanup_staging()
        self._active = False
        self._unsubscribe_failure_events()

        if errors:
            for err in errors:
                self._print(f"    ✗ {err}")
            self._print(f"[!] Rollback complete with {len(errors)} error(s). {restored}/{modified_count} files restored.")
        else:
            self._print(f"[✓] Rollback complete. {restored}/{modified_count} file(s) restored to prior state.")

        if self._bus is not None:
            self._bus.publish_sync("transaction.rolled_back", {
                "transaction_id": self._txn_id,
                "files_restored": restored,
                "errors": errors,
            })
        self._purge_blackboard(reason="rollback")

    # ------------------------------------------------------------------
    # Snapshotting
    # ------------------------------------------------------------------

    def _purge_blackboard(self, reason: str = "transaction_end") -> None:
        """Purge the associated Blackboard session namespace to free RAM.

        Called automatically by both :meth:`commit` and :meth:`rollback` so
        that ephemeral scratchpad data never outlives its transaction.
        """
        if self._blackboard is None or self._session_id is None:
            return
        freed = self._blackboard.purge_session(self._session_id)
        logger.debug(
            "Transaction %s: Blackboard session '%s' purged on %s (%d artifacts freed).",
            self._txn_id, self._session_id, reason, freed
        )

    def snapshot(self, path: str | Path) -> None:
        """Back up *path* before it is mutated.

        If *path* does not yet exist (the tool will create it), we register a
        sentinel so rollback knows to delete it.

        Parameters
        ----------
        path:
            Absolute or relative path of the file about to be mutated.

        Raises
        ------
        StagingCapExceeded:
            If copying the file would exceed the 50 MB staging cap.
        RuntimeError:
            If called before :meth:`begin`.
        """
        if not self._active:
            raise RuntimeError("snapshot() called outside of an active transaction. Call begin() first.")

        target = Path(path).resolve()
        key = str(target)

        # Already snapshotted — idempotent.
        if key in self._snapshots:
            return

        if not target.exists():
            # Brand-new file — nothing to back up, just record it.
            self._snapshots[key] = _NEW_FILE_SENTINEL
            self._new_files.add(key)
            logger.debug("Transaction %s: registered new file %s", self._txn_id, target)
            return

        # Check size before committing disk space.
        file_size = target.stat().st_size
        if self._staging_bytes + file_size > STAGING_CAP_BYTES:
            raise StagingCapExceeded(
                f"Cannot snapshot '{target}' ({file_size / 1024:.1f} KB): "
                f"staging cap of {STAGING_CAP_BYTES // (1024 * 1024)} MB would be exceeded. "
                f"Current staging use: {self._staging_bytes / (1024 * 1024):.1f} MB."
            )

        # Build a flat backup filename that is unique within the staging dir.
        safe_name = key.replace("/", "__").lstrip("_")
        backup_path = self._staging_dir / safe_name

        try:
            shutil.copy2(target, backup_path)
            self._snapshots[key] = str(backup_path)
            self._staging_bytes += file_size
            logger.debug("Transaction %s: snapshotted %s → %s", self._txn_id, target, backup_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to snapshot '{target}': {exc}") from exc

    def should_snapshot(self, tool_name: str) -> bool:
        """Return ``True`` if *tool_name* implies filesystem mutation."""
        return tool_name.lower() in MUTATING_TOOL_NAMES

    @property
    def transaction_id(self) -> str:
        return self._txn_id

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "WorkspaceTransactionManager":
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        return False  # Never suppress exceptions.

    # ------------------------------------------------------------------
    # EventBus integration
    # ------------------------------------------------------------------

    def _on_failure_event(self, event: Event) -> None:
        """Handle failure events by triggering an automatic rollback."""
        if not self._active:
            return
        event_name = event.event_type
        step = event.data.get("step", "?")
        total = event.data.get("total_steps", "?")
        self._print(f"\n[!] Execution aborted ({event_name}) on step {step}/{total}.")
        self.rollback()

    def _unsubscribe_failure_events(self) -> None:
        if self._bus is not None:
            try:
                self._bus.unsubscribe("plan.failed", self._on_failure_event)
                self._bus.unsubscribe("circuit_breaker.triggered", self._on_failure_event)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cleanup_staging(self) -> None:
        try:
            if self._staging_dir.exists():
                shutil.rmtree(self._staging_dir)
        except Exception as exc:
            logger.warning("Failed to clean staging dir %s: %s", self._staging_dir, exc)

    def _print(self, msg: str) -> None:
        if self._verbose:
            print(msg)
        logger.info(msg)
