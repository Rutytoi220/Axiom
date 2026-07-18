"""Async SQLite-backed memory store for AXIOM."""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
import shutil
import sqlite3

import aiosqlite

logger = logging.getLogger(__name__)

from axiom.memory.protocol import MemoryBackend
from axiom.memory.semantic import SemanticIndex

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


class MemoryStore(MemoryBackend):
    """Async SQLite-backed memory store implementing the MemoryBackend protocol.

    Provides key-value storage, conversations, summaries, semantic search,
    event logging, and agent session tracking.
    """

    def __init__(self, db_path: str = "axiom.db", semantic_index: Optional[SemanticIndex] = None):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized = False
        self._semantic = semantic_index or SemanticIndex()
        import asyncio

        self._lock = asyncio.Lock()

    @property
    def semantic(self) -> SemanticIndex:
        return self._semantic

    async def initialize(self) -> None:
        if self._initialized:
            return
        
        try:
            await self._init_db_connection()
        except sqlite3.DatabaseError as e:
            if self._db:
                await self._db.close()
                self._db = None
            backup_path = f"{self.db_path}.corrupted.{int(time.time())}"
            logger.error(f"Database corruption detected ({e}). Backing up to {backup_path} and resetting.")
            try:
                shutil.move(self.db_path, backup_path)
            except OSError:
                pass
            # Retry initialization once with fresh file
            await self._init_db_connection()
            
    async def _init_db_connection(self) -> None:
        self._db = await aiosqlite.connect(self.db_path, timeout=30)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=30000")
        
        async with self._db.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row else 0
            
        if current_version == 0:
            await self._db.executescript(_SCHEMA)
            await self._db.execute("PRAGMA user_version = 1")
            await self._db.commit()
        elif current_version > 1:
            raise sqlite3.DatabaseError(f"Database version {current_version} is higher than supported version 1. Please upgrade AXIOM.")
            
        self._initialized = True

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
        self._initialized = False
        import asyncio

        self._lock = asyncio.Lock()

    def _conn(self) -> aiosqlite.Connection:
        if not self._initialized or self._db is None:
            raise RuntimeError("MemoryStore not initialized")
        return self._db

    # -- Key-value store --

    async def set(
        self, key: str, value: Any, tags: Optional[List[str]] = None, ttl: Optional[float] = None
    ) -> None:
        db = self._conn()
        now = time.time()
        tags_json = json.dumps(tags or [])
        value_json = json.dumps(value)
        cursor = await db.execute("SELECT created_at FROM memories WHERE key = ?", (key,))
        row = await cursor.fetchone()
        created_at = float(row["created_at"]) if row else now
        await db.execute(
            """INSERT OR REPLACE INTO memories
            (key, value_json, tags_json, created_at, updated_at, ttl_seconds)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (key, value_json, tags_json, created_at, now, ttl),
        )
        await db.commit()

    async def get(self, key: str) -> Any | None:
        db = self._conn()
        now = time.time()
        cursor = await db.execute(
            """SELECT value_json FROM memories
            WHERE key = ? AND (ttl_seconds IS NULL OR created_at + ttl_seconds > ?)""",
            (key, now),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["value_json"])

    async def delete(self, key: str) -> bool:
        db = self._conn()
        cursor = await db.execute("DELETE FROM memories WHERE key = ?", (key,))
        await db.commit()
        return cursor.rowcount > 0

    async def search(self, tags: List[str]) -> List[Dict[str, Any]]:
        if not tags:
            return []
        db = self._conn()
        now = time.time()
        cursor = await db.execute(
            """SELECT key, value_json, tags_json, created_at, updated_at
            FROM memories WHERE ttl_seconds IS NULL OR created_at + ttl_seconds > ?""",
            (now,),
        )
        rows = await cursor.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            stored_tags = json.loads(row["tags_json"])
            if all(tag in stored_tags for tag in tags):
                results.append(
                    {
                        "key": row["key"],
                        "value": json.loads(row["value_json"]),
                        "tags": stored_tags,
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )
        return results

    async def search_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        return await self.search(tags)

    async def expire_ttl(self) -> int:
        db = self._conn()
        now = time.time()
        cursor = await db.execute(
            "DELETE FROM memories WHERE ttl_seconds IS NOT NULL AND created_at + ttl_seconds < ?",
            (now,),
        )
        await db.commit()
        return cursor.rowcount

    # -- Conversations --

    async def create_conversation(self, title: str = "") -> str:
        db = self._conn()
        conv_id = uuid.uuid4().hex
        await db.execute(
            "INSERT INTO conversations (id, title, updated_at) VALUES (?, ?, ?)",
            (conv_id, title, time.time()),
        )
        await db.commit()
        return conv_id

    async def add_message(
        self, conversation_id: str, role: str, content: str, metadata: Optional[Dict] = None
    ) -> str:
        db = self._conn()
        msg_id = uuid.uuid4().hex
        await db.execute(
            """INSERT INTO messages (id, conversation_id, role, content, metadata_json)
            VALUES (?, ?, ?, ?, ?)""",
            (msg_id, conversation_id, role, content, json.dumps(metadata) if metadata else None),
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (time.time(), conversation_id),
        )
        await db.commit()
        return msg_id

    async def get_messages(self, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        db = self._conn()
        cursor = await db.execute(
            """SELECT id, role, content, timestamp, metadata_json
            FROM messages WHERE conversation_id = ?
            ORDER BY rowid ASC LIMIT ?""",
            (conversation_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            }
            for row in rows
        ]

    async def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = self._conn()
        cursor = await db.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    # -- Summaries --

    async def save_summary(
        self, conversation_id: str, summary: str, msg_start: int, msg_end: int
    ) -> None:
        db = self._conn()
        await db.execute(
            """INSERT INTO summaries (conversation_id, summary, msg_start, msg_end)
            VALUES (?, ?, ?, ?)""",
            (conversation_id, summary, msg_start, msg_end),
        )
        await db.commit()

    async def get_summaries(self, conversation_id: str) -> List[Dict[str, Any]]:
        db = self._conn()
        cursor = await db.execute(
            """SELECT id, summary, msg_start, msg_end, created_at
            FROM summaries WHERE conversation_id = ?
            ORDER BY msg_start ASC""",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "summary": row["summary"],
                "msg_start": row["msg_start"],
                "msg_end": row["msg_end"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -- Semantic search --

    async def store_embedding(
        self, owner_id: str, owner_type: str, embedding: List[float], model: str = ""
    ) -> None:
        await self._semantic.store(self._conn(), owner_id, owner_type, embedding, model)

    async def search_similar(
        self, embedding: List[float], owner_type: str = "", top_k: int = 5
    ) -> List[Dict[str, Any]]:
        return await self._semantic.search(self._conn(), embedding, owner_type, top_k)

    # -- Events --

    async def log_event(
        self, event_name: str, payload: Any = None, source: Optional[str] = None
    ) -> int:
        db = self._conn()
        cursor = await db.execute(
            "INSERT INTO events (event_name, payload_json, source, timestamp) VALUES (?, ?, ?, ?)",
            (event_name, json.dumps(payload) if payload is not None else None, source, time.time()),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_events(
        self, event_name: Optional[str] = None, source: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        db = self._conn()
        query = "SELECT id, event_name, payload_json, source, timestamp FROM events WHERE 1=1"
        params: List[Any] = []
        if event_name is not None:
            query += " AND event_name = ?"
            params.append(event_name)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "event_name": row["event_name"],
                "payload": json.loads(row["payload_json"]) if row["payload_json"] else None,
                "source": row["source"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    # -- Agent sessions --

    async def create_agent_session(self, agent_name: str, task: str) -> int:
        db = self._conn()
        cursor = await db.execute(
            "INSERT INTO agent_sessions "
            "(agent_name, task, started_at, status) VALUES (?, ?, ?, 'running')",
            (agent_name, task, time.time()),
        )
        await db.commit()
        return cursor.lastrowid

    async def log_tool_call(
        self,
        session_id: int,
        tool_name: str,
        params: Any,
        result: Any,
        duration_ms: int,
        success: bool,
        error_message: Optional[str] = None,
    ) -> int:
        db = self._conn()
        cursor = await db.execute(
            """INSERT INTO tool_calls
            (session_id, tool_name, params_json, result_json,
             duration_ms, success, error_message, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                tool_name,
                json.dumps(params),
                json.dumps(result),
                duration_ms,
                success,
                error_message,
                time.time(),
            ),
        )
        await db.commit()
        return cursor.lastrowid

    async def get_session_tool_calls(self, session_id: int) -> List[Dict[str, Any]]:
        db = self._conn()
        cursor = await db.execute(
            """SELECT tool_name, params_json, result_json, duration_ms, success, error_message
            FROM tool_calls WHERE session_id = ? ORDER BY timestamp""",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "tool_name": row["tool_name"],
                "params": json.loads(row["params_json"]) if row["params_json"] else {},
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "duration_ms": row["duration_ms"],
                "success": bool(row["success"]),
                "error_message": row["error_message"],
            }
            for row in rows
        ]

    async def complete_agent_session(
        self, session_id: int, result: Any, success: bool = True
    ) -> None:
        db = self._conn()
        status = "completed" if success else "failed"
        await db.execute(
            "UPDATE agent_sessions SET completed_at = ?, result_json = ?, status = ? WHERE id = ?",
            (time.time(), json.dumps(result), status, session_id),
        )
        await db.commit()
