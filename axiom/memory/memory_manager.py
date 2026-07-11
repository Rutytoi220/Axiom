"""Memory manager for AXIOM - conversation and state management.

Thin wrapper over MemoryStore that tracks the active conversation.
"""

import threading
import uuid
from typing import Any, Dict, List, Optional

from axiom.memory.memory_async import MemoryStore


class MemoryManager:
    """Conversation-focused wrapper over MemoryStore."""

    def __init__(self, db_path: str = "axiom.db"):
        self._store = MemoryStore(db_path)
        self._current_conversation: Optional[str] = None
        self._lock = threading.RLock()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        from axiom.memory.memory_sync import _run

        _run(self._store.initialize())

    def close(self) -> None:
        """Release the underlying SQLite connection.

        The operation is idempotent, allowing application shutdown paths to
        call it safely after an interrupted or partially initialized session.
        """
        from axiom.memory.memory_sync import _run

        _run(self._store.close())

    def create_conversation(self, title: str = "") -> str:
        from axiom.memory.memory_sync import _run

        conversation_id = _run(self._store.create_conversation(title))
        with self._lock:
            self._current_conversation = conversation_id
        return conversation_id

    def set_conversation(self, conversation_id: str) -> None:
        with self._lock:
            self._current_conversation = conversation_id

    def get_conversation(self) -> Optional[str]:
        with self._lock:
            return self._current_conversation

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        from axiom.memory.memory_sync import _run

        with self._lock:
            conversation_id = self._current_conversation
        if not conversation_id:
            raise RuntimeError("No active conversation")
        return _run(self._store.add_message(conversation_id, role, content, metadata))

    def get_conversation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        from axiom.memory.memory_sync import _run

        with self._lock:
            conversation_id = self._current_conversation
        if not conversation_id:
            return []
        return _run(self._store.get_messages(conversation_id, limit))

    def restore_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        self.set_conversation(conversation_id)
        return self.get_conversation_history(limit=1000)

    def search_relevant(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search messages in current conversation by keyword scoring."""
        history = self.get_conversation_history(limit=200)
        terms = [t.lower() for t in query.split() if len(t) >= 3]
        if not terms:
            return []
        scored = []
        for msg in history:
            text = msg.get("content", "").lower()
            score = sum(1 for term in terms if term in text)
            if score:
                scored.append((score, msg))
        return [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]

    def save_tool_execution(
        self, tool_name: str, input_data: Any, output_data: Any, context_id: Optional[str] = None
    ) -> str:
        from axiom.memory.memory_sync import _run

        result_id = str(uuid.uuid4())
        status = (
            "success"
            if not isinstance(output_data, dict) or output_data.get("success", True)
            else "error"
        )
        _run(
            self._store.log_tool_call(0, tool_name, input_data, output_data, 0, status == "success")
        )
        return result_id
