"""SQLite database layer for AXIOM."""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe SQLite wrapper for conversations, tool results and state."""

    def __init__(self, db_path: str = "axiom.db"):
        self.db_path = Path(db_path)
        if self.db_path.parent != Path(""):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = self._connect()
        self._init_tables()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _get_connection(self):
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _init_tables(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, title TEXT, metadata TEXT)""")
                cursor.execute("""CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, metadata TEXT, FOREIGN KEY (conversation_id) REFERENCES conversations(id))""")
                cursor.execute("""CREATE TABLE IF NOT EXISTS tool_results (id TEXT PRIMARY KEY, context_id TEXT, tool_name TEXT NOT NULL, input_data TEXT, output_data TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'success')""")
                cursor.execute("""CREATE TABLE IF NOT EXISTS agent_memory (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(agent_id, key))""")
                cursor.execute("""CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
                conn.commit()
            finally:
                pass

    def _json(self, value: Any) -> Optional[str]:
        return json.dumps(value, default=str) if value is not None else None

    def save_conversation(self, conversation_id: str, title: str = "", metadata: Optional[Dict] = None) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""INSERT OR REPLACE INTO conversations (id, title, metadata, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)""", (conversation_id, title, self._json(metadata)))
                conn.commit()
            finally:
                pass

    def add_message(self, conversation_id: str, message_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""INSERT INTO messages (id, conversation_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)""", (message_id, conversation_id, role, content, self._json(metadata)))
                conn.commit()
            finally:
                pass

    def get_messages(self, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                rows = conn.execute("""SELECT id, role, content, timestamp, metadata FROM messages WHERE conversation_id = ? ORDER BY timestamp DESC, id DESC LIMIT ?""", (conversation_id, limit)).fetchall()
            finally:
                pass
        messages = []
        for row in rows:
            msg = dict(row)
            if msg.get("metadata"):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except Exception:
                    pass
            messages.append(msg)
        return list(reversed(messages))

    def search_messages(self, query: str, conversation_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        terms = [t.lower() for t in query.split() if len(t) >= 3]
        if not terms:
            return []
        with self._lock:
            conn = self._get_connection()
            try:
                if conversation_id:
                    rows = conn.execute("""SELECT id, conversation_id, role, content, timestamp, metadata FROM messages WHERE conversation_id = ? ORDER BY timestamp DESC LIMIT 200""", (conversation_id,)).fetchall()
                else:
                    rows = conn.execute("""SELECT id, conversation_id, role, content, timestamp, metadata FROM messages ORDER BY timestamp DESC LIMIT 500""").fetchall()
            finally:
                pass
        scored = []
        for row in rows:
            text = row["content"].lower()
            score = sum(1 for term in terms if term in text)
            if score:
                scored.append((score, dict(row)))
        return [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]

    def save_tool_result(self, result_id: str, context_id: str, tool_name: str, input_data: Any, output_data: Any, status: str = "success") -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""INSERT INTO tool_results (id, context_id, tool_name, input_data, output_data, status) VALUES (?, ?, ?, ?, ?, ?)""", (result_id, context_id, tool_name, self._json(input_data), self._json(output_data), status))
                conn.commit()
            finally:
                pass

    def save_agent_memory(self, agent_id: str, key: str, value: Any) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""INSERT OR REPLACE INTO agent_memory (id, agent_id, key, value, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""", (f"{agent_id}:{key}", agent_id, key, self._json(value) or "null"))
                conn.commit()
            finally:
                pass

    def get_agent_memory(self, agent_id: str, key: str) -> Optional[Any]:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute("SELECT value FROM agent_memory WHERE agent_id = ? AND key = ?", (agent_id, key)).fetchone()
            finally:
                pass
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return None

    def save_system_state(self, key: str, value: Any) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)""", (key, self._json(value) or "null"))
                conn.commit()
            finally:
                pass

    def get_system_state(self, key: str) -> Optional[Any]:
        with self._lock:
            conn = self._get_connection()
            try:
                row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
            finally:
                pass
        if row:
            try:
                return json.loads(row[0])
            except Exception:
                return row[0]
        return None
