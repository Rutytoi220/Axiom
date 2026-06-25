"""SQLite-backed memory storage for AXIOM."""

import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class MemoryStore:
    """Synchronous SQLite-backed memory store."""

    def __init__(self, db_path: str = "axiom.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize_schema()
        # #region agent log
        import json as _json, time as _time, inspect as _inspect
        try:
            with open("/run/media/rutytoi/fast af/ChienGPT/.cursor/debug-e94045.log", "a", encoding="utf-8") as _f:
                _f.write(_json.dumps({"sessionId": "e94045", "hypothesisId": "C", "location": "memory.py:MemoryStore.__init__", "message": "memory_capabilities", "data": {"has_initialize": hasattr(self, "initialize"), "set_is_coroutine": _inspect.iscoroutinefunction(getattr(self, "set", None)), "db_path": db_path}, "timestamp": int(_time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion

    def _initialize_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    ttl_seconds REAL DEFAULT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    data TEXT DEFAULT NULL,
                    source TEXT DEFAULT NULL,
                    timestamp REAL NOT NULL
                )
                """
            )

    def close(self) -> None:
        if self._conn:
            with self._lock:
                self._conn.close()
                self._conn = None

    def _now(self) -> float:
        return time.time()

    def set(self, key: str, value: Any, tags: Optional[List[str]] = None, ttl: float = None) -> None:
        tags_json = json.dumps(tags or [])
        value_json = json.dumps(value)
        now = self._now()

        with self._lock, self._conn:
            cursor = self._conn.execute(
                "SELECT created_at FROM memories WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            created_at = row["created_at"] if row else now

            self._conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (key, value, tags, created_at, updated_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (key, value_json, tags_json, created_at, now, ttl),
            )

    def get(self, key: str) -> Any | None:
        now = self._now()

        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                SELECT value FROM memories
                WHERE key = ?
                  AND (ttl_seconds IS NULL OR created_at + ttl_seconds > ?)
                """,
                (key, now),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return json.loads(row["value"])

    def delete(self, key: str) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "DELETE FROM memories WHERE key = ?",
                (key,),
            )
            return cursor.rowcount > 0

    def search(self, tags: List[str]) -> List[Dict[str, Any]]:
        if not tags:
            return []

        now = self._now()
        results: List[Dict[str, Any]] = []

        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                SELECT key, value, tags, created_at, updated_at
                FROM memories
                WHERE ttl_seconds IS NULL OR created_at + ttl_seconds > ?
                """,
                (now,),
            )
            rows = cursor.fetchall()

        for row in rows:
            stored_tags = json.loads(row["tags"])
            if any(tag in stored_tags for tag in tags):
                results.append(
                    {
                        "key": row["key"],
                        "value": json.loads(row["value"]),
                        "tags": stored_tags,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )

        return results

    def list_keys(self) -> List[str]:
        now = self._now()

        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                SELECT key FROM memories
                WHERE ttl_seconds IS NULL OR created_at + ttl_seconds > ?
                """,
                (now,),
            )
            return [row["key"] for row in cursor.fetchall()]

    def log_event(self, event_name: str, data: Any = None, source: str = None) -> int:
        payload = json.dumps(data) if data is not None else None
        timestamp = self._now()

        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO event_log (event_name, data, source, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (event_name, payload, source, timestamp),
            )
            return cursor.lastrowid

    def get_events(self, event_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT id, event_name, data, source, timestamp FROM event_log"
        params: List[Any] = []

        if event_name is not None:
            query += " WHERE event_name = ?"
            params.append(event_name)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock, self._conn:
            cursor = self._conn.execute(query, tuple(params))
            rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "event_name": row["event_name"],
                "data": json.loads(row["data"]) if row["data"] is not None else None,
                "source": row["source"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def expire(self, key: str = None, ttl_seconds: float = None) -> int:
        """Manage TTL expiration.
        
        If called with no arguments, cleans up expired entries.
        If called with key and ttl_seconds, sets TTL on that specific key.
        
        Returns:
            Count of expired entries deleted (if cleanup), or 0 (if setting TTL)
        """
        if key is None and ttl_seconds is None:
            # Backward compatible: cleanup expired entries
            now = self._now()
            with self._lock, self._conn:
                cursor = self._conn.execute(
                    """
                    DELETE FROM memories
                    WHERE ttl_seconds IS NOT NULL AND created_at + ttl_seconds < ?
                    """,
                    (now,),
                )
                return cursor.rowcount
        else:
            # New functionality: set TTL on specific key
            now = self._now()
            with self._lock, self._conn:
                self._conn.execute(
                    """
                    UPDATE memories SET ttl_seconds = ?, updated_at = ? WHERE key = ?
                    """,
                    (ttl_seconds, now, key),
                )
            return 0
