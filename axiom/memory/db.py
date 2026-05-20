"""SQLite database layer for AXIOM."""

import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite database wrapper for AXIOM."""
    
    def __init__(self, db_path: str = "axiom.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
    
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self) -> None:
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                metadata TEXT
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        ''')
        
        # Tool results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tool_results (
                id TEXT PRIMARY KEY,
                context_id TEXT,
                tool_name TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'success'
            )
        ''')
        
        # Agent memory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agent_id, key)
            )
        ''')
        
        # System state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_conversation(self, conversation_id: str, title: str = "", 
                         metadata: Optional[Dict] = None) -> None:
        """Save a conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        meta_json = json.dumps(metadata) if metadata else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO conversations (id, title, metadata, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (conversation_id, title, meta_json))
        
        conn.commit()
        conn.close()
    
    def add_message(self, conversation_id: str, message_id: str, role: str, 
                   content: str, metadata: Optional[Dict] = None) -> None:
        """Add a message to conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        meta_json = json.dumps(metadata) if metadata else None
        
        cursor.execute('''
            INSERT INTO messages (id, conversation_id, role, content, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (message_id, conversation_id, role, content, meta_json))
        
        conn.commit()
        conn.close()
    
    def get_messages(self, conversation_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages from a conversation."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, role, content, timestamp, metadata
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (conversation_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            msg = dict(row)
            if msg.get('metadata'):
                msg['metadata'] = json.loads(msg['metadata'])
            messages.append(msg)
        
        return list(reversed(messages))  # Return in chronological order
    
    def save_tool_result(self, result_id: str, context_id: str, tool_name: str,
                        input_data: Any, output_data: Any, status: str = "success") -> None:
        """Save tool execution result."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        input_json = json.dumps(input_data) if input_data else None
        output_json = json.dumps(output_data) if output_data else None
        
        cursor.execute('''
            INSERT INTO tool_results (id, context_id, tool_name, input_data, output_data, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (result_id, context_id, tool_name, input_json, output_json, status))
        
        conn.commit()
        conn.close()
    
    def save_agent_memory(self, agent_id: str, key: str, value: Any) -> None:
        """Save agent memory key-value pair."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        value_json = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute('''
            INSERT OR REPLACE INTO agent_memory (id, agent_id, key, value, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (f"{agent_id}:{key}", agent_id, key, value_json))
        
        conn.commit()
        conn.close()
    
    def get_agent_memory(self, agent_id: str, key: str) -> Optional[Any]:
        """Get agent memory value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT value FROM agent_memory
            WHERE agent_id = ? AND key = ?
        ''', (agent_id, key))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return row[0]
        return None
    
    def save_system_state(self, key: str, value: Any) -> None:
        """Save system state."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        value_json = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value_json))
        
        conn.commit()
        conn.close()
    
    def get_system_state(self, key: str) -> Optional[Any]:
        """Get system state."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM system_state WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return row[0]
        return None
