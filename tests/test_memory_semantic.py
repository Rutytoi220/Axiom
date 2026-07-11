"""Tests for MemoryManager's optional semantic search integration.

Uses a deterministic fake embedding provider so these tests do not require a
running Ollama instance.
"""

from typing import List, Optional

from axiom.memory import MemoryManager


class FakeEmbeddingProvider:
    """Maps known strings to fixed vectors so similarity is deterministic."""

    def __init__(self, vectors: dict):
        self._vectors = vectors
        self.embed_calls: List[str] = []

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        self.embed_calls.append(text)
        return self._vectors.get(text, [])


class ExplodingEmbeddingProvider:
    """Always raises, to verify embedding failures never break message storage."""

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        raise RuntimeError("embedding service unavailable")


def test_add_message_without_provider_is_unchanged(tmp_path):
    """No embedding_provider means behavior matches the pre-existing contract."""
    memory = MemoryManager(str(tmp_path / "memory.db"))
    memory.create_conversation("Test")

    message_id = memory.add_message("user", "hello world")

    assert message_id is not None
    assert memory.search_semantic("hello") == []


def test_search_semantic_without_provider_returns_empty_list(tmp_path):
    memory = MemoryManager(str(tmp_path / "memory.db"))
    memory.create_conversation("Test")
    memory.add_message("user", "hello world")

    assert memory.search_semantic("hello") == []


def test_search_semantic_ranks_by_similarity(tmp_path):
    provider = FakeEmbeddingProvider(
        {
            "I love cats": [1.0, 0.0],
            "The weather is sunny today": [0.0, 1.0],
            "cats": [1.0, 0.0],
        }
    )
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")
    memory.add_message("user", "I love cats")
    memory.add_message("user", "The weather is sunny today")

    results = memory.search_semantic("cats", limit=5)

    assert len(results) == 2
    assert results[0]["content"] == "I love cats"
    assert results[0]["similarity"] == 1.0
    assert results[1]["content"] == "The weather is sunny today"
    assert results[1]["similarity"] == 0.0


def test_search_semantic_respects_limit(tmp_path):
    provider = FakeEmbeddingProvider(
        {
            "a": [1.0, 0.0],
            "b": [1.0, 0.0],
            "c": [1.0, 0.0],
            "query": [1.0, 0.0],
        }
    )
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")
    memory.add_message("user", "a")
    memory.add_message("user", "b")
    memory.add_message("user", "c")

    results = memory.search_semantic("query", limit=2)

    assert len(results) == 2


def test_messages_without_embeddable_content_are_skipped_gracefully(tmp_path):
    """Provider returning an empty embedding must not break message storage."""
    provider = FakeEmbeddingProvider({})  # embed() returns [] for everything
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")

    message_id = memory.add_message("user", "unembeddable content")

    assert message_id is not None
    assert memory.search_semantic("unembeddable content") == []


def test_embedding_failure_does_not_break_add_message(tmp_path):
    provider = ExplodingEmbeddingProvider()
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")

    message_id = memory.add_message("user", "hello")

    assert message_id is not None
    history = memory.get_conversation_history()
    assert len(history) == 1


def test_search_semantic_failure_returns_empty_list_without_raising(tmp_path):
    provider = ExplodingEmbeddingProvider()
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")
    memory.add_message("user", "hello")

    assert memory.search_semantic("hello") == []


def test_keyword_search_relevant_still_works_alongside_semantic(tmp_path):
    """search_relevant (keyword) and search_semantic are independent, additive APIs."""
    provider = FakeEmbeddingProvider({"urgent task": [1.0, 0.0]})
    memory = MemoryManager(str(tmp_path / "memory.db"), embedding_provider=provider)
    memory.create_conversation("Test")
    memory.add_message("user", "urgent task")

    keyword_results = memory.search_relevant("urgent")
    semantic_results = memory.search_semantic("urgent task")

    assert len(keyword_results) == 1
    assert len(semantic_results) == 1
