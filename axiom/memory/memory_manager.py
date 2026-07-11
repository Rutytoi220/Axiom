"""Memory manager for AXIOM - conversation and state management.

Thin wrapper over MemoryStore that tracks the active conversation.
"""

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from axiom.memory.memory_async import MemoryStore
from axiom.memory.semantic import EmbeddingProvider

logger = logging.getLogger(__name__)


class MemoryManager:
    """Conversation-focused wrapper over MemoryStore.

    Optionally accepts an ``embedding_provider`` (anything satisfying
    :class:`axiom.memory.semantic.EmbeddingProvider`, such as
    :class:`axiom.llm.OllamaClient`) to enable semantic search over
    conversation messages via :meth:`search_semantic`. Without a provider,
    behavior is unchanged from before this was added: messages are stored
    without embeddings and only keyword-based :meth:`search_relevant` is
    available.
    """

    def __init__(self, db_path: str = "axiom.db", embedding_provider: Optional[EmbeddingProvider] = None):
        self._store = MemoryStore(db_path)
        self._current_conversation: Optional[str] = None
        self._lock = threading.RLock()
        self._embedding_provider = embedding_provider
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
        message_id = _run(self._store.add_message(conversation_id, role, content, metadata))
        if self._embedding_provider is not None:
            self._try_embed_message(message_id, content)
        return message_id

    def _try_embed_message(self, message_id: str, content: str) -> None:
        """Best-effort embedding of a stored message for semantic search.

        Failures (provider unavailable, network error, etc.) are logged and
        swallowed so semantic search is strictly additive: it never causes
        message storage itself to fail.
        """
        from axiom.memory.memory_sync import _run

        try:
            embedding = self._embedding_provider.embed(content)
        except Exception as exc:
            logger.warning("Failed to compute embedding for message %s: %s", message_id, exc)
            return
        if not embedding:
            return
        try:
            _run(self._store.store_embedding(message_id, "message", embedding))
        except Exception as exc:
            logger.warning("Failed to store embedding for message %s: %s", message_id, exc)

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

    def search_semantic(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search messages in the current conversation by embedding similarity.

        Requires an ``embedding_provider`` to have been supplied at
        construction time. Returns an empty list (never raises) if no
        provider is configured, the provider fails, or no messages have been
        embedded yet — callers can safely use this as a drop-in enhancement
        over :meth:`search_relevant` without special-casing availability.

        Each result is the matched message dict plus a ``similarity`` key
        (cosine similarity in ``[-1.0, 1.0]``, higher is more similar).
        """
        from axiom.memory.memory_sync import _run

        if self._embedding_provider is None:
            return []
        try:
            query_embedding = self._embedding_provider.embed(query)
        except Exception as exc:
            logger.warning("Semantic search embedding failed: %s", exc)
            return []
        if not query_embedding:
            return []

        matches = _run(self._store.search_similar(query_embedding, owner_type="message", top_k=limit))
        if not matches:
            return []

        history_by_id = {msg["id"]: msg for msg in self.get_conversation_history(limit=1000)}
        results = []
        for match in matches:
            msg = history_by_id.get(match["owner_id"])
            if msg is not None:
                results.append({**msg, "similarity": match["similarity"]})
        return results

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
