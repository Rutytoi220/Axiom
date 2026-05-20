"""Async memory storage with SQLite backend."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiosqlite
except ImportError:
    raise ImportError(
        "aiosqlite is required for MemoryStore. "
        "Install it with: pip install aiosqlite"
    )

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Async SQLite-based memory store for AXIOM.
    
    Supports:
    - Key-value storage with TTL
    - Tag-based searching
    - Event audit logging
    - Tool call tracking
    - Concurrent async access
    """
    
    def __init__(self, db_path: str = "axiom_memory.db"):
        """
        Initialize memory store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._db = None
        self._schema_path = Path(__file__).parent / "schema.sql"
    
    async def initialize(self) -> None:
        """Initialize database connection and create schema."""
        # Connect to database
        self._db = await aiosqlite.connect(self.db_path)
        self._db.isolation_level = None  # Autocommit mode
        
        logger.info(f"Connected to memory database: {self.db_path}")
        
        # Load and execute schema
        if self._schema_path.exists():
            with open(self._schema_path, "r") as f:
                schema = f.read()
            
            # Split by semicolon and execute each statement
            for statement in schema.split(";"):
                statement = statement.strip()
                if statement:
                    await self._db.execute(statement)
            
            await self._db.commit()
            logger.info("Database schema initialized")
        else:
            logger.warning(f"Schema file not found: {self._schema_path}")
    
    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            logger.info("Memory store closed")
    
    async def set(self, key: str, value: Any, tags: Optional[List[str]] = None,
                  ttl: Optional[int] = None) -> None:
        """
        Set a value in memory with optional TTL and tags.
        
        Args:
            key: Memory key
            value: Value to store (will be JSON-serialized)
            tags: Optional list of tags for searching
            ttl: Time-to-live in seconds (None for infinite)
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        value_json = json.dumps(value)
        tags_json = json.dumps(tags or [])
        now = datetime.utcnow()
        expires_at = None
        
        if ttl is not None:
            expires_at = (now + timedelta(seconds=ttl)).isoformat()
        
        try:
            await self._db.execute(
                """
                INSERT OR REPLACE INTO memories 
                (key, value_json, tags_json, created_at, updated_at, ttl_seconds, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key, value_json, tags_json, now.isoformat(), now.isoformat(), ttl, expires_at)
            )
            await self._db.commit()
            logger.debug(f"Stored memory: {key}")
        except Exception as e:
            logger.error(f"Failed to store memory {key}: {str(e)}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from memory.
        
        Args:
            key: Memory key
        
        Returns:
            The stored value, or None if not found or expired
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            cursor = await self._db.execute(
                """
                SELECT value_json, expires_at FROM memories 
                WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (key, datetime.utcnow().isoformat())
            )
            row = await cursor.fetchone()
            
            if row:
                value_json, expires_at = row
                return json.loads(value_json)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get memory {key}: {str(e)}")
            return None
    
    async def delete(self, key: str) -> bool:
        """
        Delete a value from memory.
        
        Args:
            key: Memory key
        
        Returns:
            True if deleted, False if not found
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            cursor = await self._db.execute(
                "DELETE FROM memories WHERE key = ?",
                (key,)
            )
            await self._db.commit()
            
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"Deleted memory: {key}")
            
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete memory {key}: {str(e)}")
            return False
    
    async def search(self, tags: List[str]) -> List[Dict[str, Any]]:
        """
        Search memories by tags.
        
        Args:
            tags: List of tags to search for
        
        Returns:
            List of memories matching all tags
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        if not tags:
            return []
        
        try:
            results = []
            cursor = await self._db.execute(
                """
                SELECT key, value_json, tags_json, created_at, updated_at
                FROM memories
                WHERE expires_at IS NULL OR expires_at > ?
                """,
                (datetime.utcnow().isoformat(),)
            )
            
            rows = await cursor.fetchall()
            
            for key, value_json, tags_json, created_at, updated_at in rows:
                stored_tags = json.loads(tags_json)
                
                # Check if all search tags are in stored tags
                if all(tag in stored_tags for tag in tags):
                    results.append({
                        "key": key,
                        "value": json.loads(value_json),
                        "tags": stored_tags,
                        "created_at": created_at,
                        "updated_at": updated_at
                    })
            
            return results
        except Exception as e:
            logger.error(f"Failed to search memories with tags {tags}: {str(e)}")
            return []
    
    async def log_event(self, event_name: str, payload: Optional[Dict[str, Any]] = None,
                       source: Optional[str] = None) -> int:
        """
        Log an event to the event table.
        
        Args:
            event_name: Name of the event
            payload: Event payload (will be JSON-serialized)
            source: Source of the event (optional)
        
        Returns:
            Event ID
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        payload_json = json.dumps(payload) if payload else None
        timestamp = datetime.utcnow().isoformat()
        
        try:
            cursor = await self._db.execute(
                """
                INSERT INTO events (timestamp, event_name, payload_json, source)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, event_name, payload_json, source)
            )
            await self._db.commit()
            
            event_id = cursor.lastrowid
            logger.debug(f"Logged event: {event_name} (id={event_id})")
            return event_id
        except sqlite3.IntegrityError:
            # Handle duplicate event (same timestamp, name, source)
            logger.debug(f"Event already logged: {event_name}")
            # Try to get existing event ID
            cursor = await self._db.execute(
                """
                SELECT id FROM events 
                WHERE timestamp = ? AND event_name = ? AND source = ?
                """,
                (timestamp, event_name, source)
            )
            row = await cursor.fetchone()
            return row[0] if row else -1
        except Exception as e:
            logger.error(f"Failed to log event {event_name}: {str(e)}")
            raise
    
    async def log_tool_call(self, session_id: int, tool_name: str,
                           params: Optional[Dict[str, Any]] = None,
                           result: Optional[Dict[str, Any]] = None,
                           duration_ms: Optional[int] = None,
                           success: Optional[bool] = None,
                           error_message: Optional[str] = None) -> int:
        """
        Log a tool call within an agent session.
        
        Args:
            session_id: Agent session ID
            tool_name: Name of the tool
            params: Tool parameters (will be JSON-serialized)
            result: Tool result (will be JSON-serialized)
            duration_ms: Execution duration in milliseconds
            success: Whether the call was successful
            error_message: Error message if failed
        
        Returns:
            Tool call ID
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        params_json = json.dumps(params) if params else None
        result_json = json.dumps(result) if result else None
        timestamp = datetime.utcnow().isoformat()
        
        try:
            cursor = await self._db.execute(
                """
                INSERT INTO tool_calls 
                (session_id, tool_name, params_json, result_json, duration_ms, timestamp, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, tool_name, params_json, result_json, duration_ms, timestamp, success, error_message)
            )
            await self._db.commit()
            
            tool_call_id = cursor.lastrowid
            logger.debug(f"Logged tool call: {tool_name} (id={tool_call_id}, session={session_id})")
            return tool_call_id
        except Exception as e:
            logger.error(f"Failed to log tool call {tool_name}: {str(e)}")
            raise
    
    async def create_agent_session(self, agent_name: str, task: str) -> int:
        """
        Create a new agent session.
        
        Args:
            agent_name: Name of the agent
            task: Task description
        
        Returns:
            Session ID
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            cursor = await self._db.execute(
                """
                INSERT INTO agent_sessions (agent_name, task, status)
                VALUES (?, ?, 'running')
                """,
                (agent_name, task)
            )
            await self._db.commit()
            
            session_id = cursor.lastrowid
            logger.debug(f"Created agent session: {agent_name} (id={session_id})")
            return session_id
        except Exception as e:
            logger.error(f"Failed to create agent session: {str(e)}")
            raise
    
    async def complete_agent_session(self, session_id: int, result: Optional[Dict[str, Any]] = None,
                                    success: bool = True) -> None:
        """
        Mark an agent session as completed.
        
        Args:
            session_id: Session ID
            result: Session result (will be JSON-serialized)
            success: Whether the session was successful
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        result_json = json.dumps(result) if result else None
        status = "completed" if success else "failed"
        completed_at = datetime.utcnow().isoformat()
        
        try:
            await self._db.execute(
                """
                UPDATE agent_sessions
                SET completed_at = ?, result_json = ?, status = ?
                WHERE id = ?
                """,
                (completed_at, result_json, status, session_id)
            )
            await self._db.commit()
            logger.debug(f"Completed agent session: {session_id} ({status})")
        except Exception as e:
            logger.error(f"Failed to complete agent session {session_id}: {str(e)}")
            raise
    
    async def expire_ttl(self) -> int:
        """
        Delete all expired memories based on TTL.
        
        Should be called periodically (e.g., in a background task).
        
        Returns:
            Number of memories deleted
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            now = datetime.utcnow().isoformat()
            cursor = await self._db.execute(
                """
                DELETE FROM memories
                WHERE expires_at IS NOT NULL AND expires_at <= ?
                """,
                (now,)
            )
            await self._db.commit()
            
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Expired {deleted_count} memories")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to expire TTL memories: {str(e)}")
            return 0
    
    async def get_events(self, event_name: Optional[str] = None,
                        source: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve events from the log.
        
        Args:
            event_name: Filter by event name (optional)
            source: Filter by source (optional)
            limit: Maximum number of events to return
        
        Returns:
            List of events
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            query = "SELECT id, timestamp, event_name, payload_json, source FROM events WHERE 1=1"
            params = []
            
            if event_name:
                query += " AND event_name = ?"
                params.append(event_name)
            
            if source:
                query += " AND source = ?"
                params.append(source)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = await self._db.execute(query, params)
            rows = await cursor.fetchall()
            
            results = []
            for event_id, timestamp, event_name, payload_json, source in rows:
                results.append({
                    "id": event_id,
                    "timestamp": timestamp,
                    "event_name": event_name,
                    "payload": json.loads(payload_json) if payload_json else None,
                    "source": source
                })
            
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve events: {str(e)}")
            return []
    
    async def get_session_tool_calls(self, session_id: int) -> List[Dict[str, Any]]:
        """
        Get all tool calls for an agent session.
        
        Args:
            session_id: Agent session ID
        
        Returns:
            List of tool calls
        """
        if not self._db:
            raise RuntimeError("Memory store not initialized. Call initialize() first.")
        
        try:
            cursor = await self._db.execute(
                """
                SELECT id, tool_name, params_json, result_json, duration_ms, timestamp, success, error_message
                FROM tool_calls
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,)
            )
            rows = await cursor.fetchall()
            
            results = []
            for tool_id, tool_name, params_json, result_json, duration_ms, timestamp, success, error_msg in rows:
                results.append({
                    "id": tool_id,
                    "tool_name": tool_name,
                    "params": json.loads(params_json) if params_json else None,
                    "result": json.loads(result_json) if result_json else None,
                    "duration_ms": duration_ms,
                    "timestamp": timestamp,
                    "success": success,
                    "error_message": error_msg
                })
            
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve tool calls for session {session_id}: {str(e)}")
            return []
