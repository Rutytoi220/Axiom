"""AXIOM Persistent Memory & Session Storage.

SQLite-backed persistent conversational history and session manager for AXIOM.
Provides persistent storage across CLI restarts and backend queries.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_db_path() -> str:
    """Return the absolute path to the SQLite memory database."""
    env_path = os.environ.get("AXIOM_MEMORY_DB")
    if env_path:
        return os.path.abspath(env_path)
    # Default to axiom_memory.db in the repository root
    repo_root = Path(__file__).resolve().parent.parent.parent
    return str(repo_root / "axiom_memory.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and return a SQLite connection with row factory enabled."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize the SQLite memory tables if they do not exist."""
    path = db_path or get_db_path()
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, session_id UNINDEXED, role UNINDEXED);
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def create_session(
    session_id: str,
    title: str = "New Session",
    db_path: Optional[str] = None,
) -> None:
    """Insert a new session record into the database."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions (id, title, created_at)
            VALUES (?, ?, ?)
            """,
            (session_id, title, now),
        )


def get_latest_session_id(db_path: Optional[str] = None) -> Optional[str]:
    """Retrieve the most recently created session ID."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT id FROM sessions ORDER BY created_at DESC, rowid DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row["id"] if row else None


def add_message(
    session_id: str,
    role: str,
    content: str,
    db_path: Optional[str] = None,
) -> None:
    """Add a message entry to the session history."""
    init_db(db_path)
    create_session(session_id, db_path=db_path)
    with get_connection(db_path) as conn:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, now),
        )
        conn.execute(
            """
            INSERT INTO messages_fts (content, session_id, role)
            VALUES (?, ?, ?)
            """,
            (content, session_id, role),
        )


def get_session_messages(
    session_id: str,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all messages for a given session in chronological order."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, session_id, role, content, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_sessions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all stored sessions."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]


def search_historical_context(
    query: str,
    session_id: str,
    limit: int = 5,
    db_path: Optional[str] = None,
) -> List[str]:
    """Search for relevant past messages using SQLite FTS5."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        try:
            # Simple sanitization for FTS5 syntax
            safe_query = query.replace('"', '""')
            cursor = conn.execute(
                """
                SELECT role, content FROM messages_fts
                WHERE messages_fts MATCH ? AND session_id = ?
                ORDER BY rank LIMIT ?
                """,
                (f'"{safe_query}"', session_id, limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append(f"[{row['role']}]: {row['content']}")
            return results
        except sqlite3.OperationalError:
            # Fallback if query syntax is invalid
            return []
