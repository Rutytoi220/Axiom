"""AXIOM Core Database Manager.

Centralized SQLite connection management ensuring robust daemon resilience.
Explicitly configures Write-Ahead Logging (WAL) and high busy timeouts to
prevent database locks and corruption during abrupt daemon terminations.
"""
import aiosqlite
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class AxiomDatabaseManager:
    """Manages SQLite connections with explicit WAL resilience."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._pool = []
        
    async def get_connection(self) -> aiosqlite.Connection:
        """Returns a robust aiosqlite connection configured for WAL mode."""
        conn = await aiosqlite.connect(self.db_path, timeout=5000.0) # 5000ms busy_timeout
        conn.row_factory = aiosqlite.Row
        
        # Enforce WAL journaling for crash resilience
        await conn.execute("PRAGMA journal_mode = WAL;")
        # NORMAL synchronous is safe with WAL and much faster
        await conn.execute("PRAGMA synchronous = NORMAL;")
        # Increase cache size (e.g. 10000 pages)
        await conn.execute("PRAGMA cache_size = -10000;")
        # Set busy timeout explicitly in SQLite just in case
        await conn.execute("PRAGMA busy_timeout = 5000;")
        
        await conn.commit()
        return conn

    async def close_all(self):
        """Placeholder for connection pooling cleanup."""
        pass
