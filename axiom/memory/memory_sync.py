"""Synchronous adapter over the async MemoryStore for AXIOM.

Provides a sync interface for consumers that cannot use async/await
(OrchestratorAgent, Engine, CLI). Delegates all work to MemoryStore.
"""

import asyncio
from typing import Any, Dict, List, Optional

from axiom.memory.memory_async import MemoryStore


def _run(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class SyncMemoryStore:
    """Sync adapter wrapping the async MemoryStore."""

    def __init__(self, db_path: str = "axiom.db"):
        self._store = MemoryStore(db_path)
        _run(self._store.initialize())

    @property
    def store(self) -> MemoryStore:
        """Access the underlying async store."""
        return self._store

    @property
    def _conn(self):
        """Direct connection access for backward compatibility."""
        return self._store._conn()

    def close(self) -> None:
        _run(self._store.close())

    def set(
        self, key: str, value: Any, tags: Optional[List[str]] = None, ttl: Optional[float] = None
    ) -> None:
        _run(self._store.set(key, value, tags, ttl))

    def get(self, key: str) -> Any | None:
        return _run(self._store.get(key))

    def delete(self, key: str) -> bool:
        return _run(self._store.delete(key))

    def search(self, tags: List[str]) -> List[Dict[str, Any]]:
        return _run(self._store.search(tags))

    def expire_ttl(self) -> int:
        return _run(self._store.expire_ttl())

    def log_event(
        self,
        event_name: str,
        payload: Any = None,
        source: Optional[str] = None,
        data: Any = None,
    ) -> int:
        return _run(self._store.log_event(event_name, payload or data, source))

    def get_events(
        self, event_name: Optional[str] = None, source: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        return _run(self._store.get_events(event_name, source, limit))

    def list_keys(self) -> List[str]:
        """List all non-expired memory keys."""
        return _run(self._list_keys_async())

    async def _list_keys_async(self) -> List[str]:
        import time as _time

        db = self._store._conn()
        now = _time.time()
        cursor = await db.execute(
            "SELECT key FROM memories WHERE ttl_seconds IS NULL OR created_at + ttl_seconds > ?",
            (now,),
        )
        rows = await cursor.fetchall()
        return [row["key"] for row in rows]

    def expire(self, key: str = None, ttl_seconds: float = None) -> int:
        """Backward-compatible expire method.

        Called with no args: cleans up expired entries.
        Called with key + ttl_seconds: sets TTL on that key.
        """
        if key is None and ttl_seconds is None:
            return self.expire_ttl()
        return _run(self._set_ttl(key, ttl_seconds))

    async def _set_ttl(self, key: str, ttl: float) -> int:
        import time as _time

        db = self._store._conn()
        now = _time.time()
        await db.execute(
            "UPDATE memories SET ttl_seconds = ?, created_at = ?, updated_at = ? WHERE key = ?",
            (ttl, now, now, key),
        )
        await db.commit()
        return 0

    def create_agent_session(self, agent_name: str, task: str) -> int:
        return _run(self._store.create_agent_session(agent_name, task))

    def log_tool_call(
        self,
        session_id: int,
        tool_name: str,
        params: Any,
        result: Any,
        duration_ms: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> int:
        return _run(
            self._store.log_tool_call(
                session_id, tool_name, params, result, duration_ms, success, error_message
            )
        )

    def get_session_tool_calls(self, session_id: int) -> List[Dict[str, Any]]:
        return _run(self._store.get_session_tool_calls(session_id))

    def complete_agent_session(self, session_id: int, result: Any, success: bool = True) -> None:
        _run(self._store.complete_agent_session(session_id, result, success))
