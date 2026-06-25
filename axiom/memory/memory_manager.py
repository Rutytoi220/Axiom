"""Memory manager for AXIOM - conversation and state management."""

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from axiom.memory.db import Database

logger = logging.getLogger(__name__)


class MemoryManager:
    """Thread-safe manager for conversation and state memory."""

    def __init__(self, db_path: str = "axiom.db"):
        self.db = Database(db_path)
        self._current_conversation: Optional[str] = None
        self._lock = threading.RLock()

    def create_conversation(self, title: str = "") -> str:
        conversation_id = str(uuid.uuid4())
        with self._lock:
            self.db.save_conversation(conversation_id, title)
            self._current_conversation = conversation_id
        logger.info("Created conversation %s", conversation_id)
        return conversation_id

    def set_conversation(self, conversation_id: str) -> None:
        with self._lock:
            self._current_conversation = conversation_id

    def get_conversation(self) -> Optional[str]:
        with self._lock:
            return self._current_conversation

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        with self._lock:
            if not self._current_conversation:
                raise RuntimeError("No active conversation")
            conversation_id = self._current_conversation
        message_id = str(uuid.uuid4())
        self.db.add_message(conversation_id, message_id, role, content, metadata)
        return message_id

    def get_conversation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            conversation_id = self._current_conversation
        if not conversation_id:
            return []
        return self.db.get_messages(conversation_id, limit)

    def restore_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Select a session and return its full state chronologically."""
        self.set_conversation(conversation_id)
        return self.get_conversation_history(limit=1000)

    def search_relevant(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return top matching messages for bounded context injection."""
        with self._lock:
            conversation_id = self._current_conversation
        return self.db.search_messages(query, conversation_id=conversation_id, limit=limit)

    def save_tool_execution(self, tool_name: str, input_data: Any, output_data: Any, context_id: Optional[str] = None) -> str:
        result_id = str(uuid.uuid4())
        with self._lock:
            context = context_id or self._current_conversation or "unknown"
        status = "success" if not isinstance(output_data, dict) or output_data.get("success", True) else "error"
        self.db.save_tool_result(result_id, context, tool_name, input_data, output_data, status=status)
        return result_id

    def save_agent_state(self, agent_id: str, state: Dict[str, Any]) -> None:
        for key, value in state.items():
            self.db.save_agent_memory(agent_id, key, value)

    def get_agent_state(self, agent_id: str, key: str, default: Any = None) -> Any:
        value = self.db.get_agent_memory(agent_id, key)
        return value if value is not None else default

    def save_system_state(self, key: str, value: Any) -> None:
        self.db.save_system_state(key, value)

    def get_system_state(self, key: str, default: Any = None) -> Any:
        value = self.db.get_system_state(key)
        return value if value is not None else default
