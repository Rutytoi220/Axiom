import pytest
import uuid
import sys
from typing import List

# Conditional import/skipping if qdrant is not installed
try:
    from axiom.memory.vector_store import QdrantLocalStore
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

pytestmark = pytest.mark.skipif(not HAS_QDRANT, reason="qdrant-client not installed")


@pytest.fixture
def store():
    """Provides a fresh in-memory vector store."""
    return QdrantLocalStore(location=":memory:")


def test_upsert_and_count(store):
    assert store.count() == 0
    
    # Upsert a single vector
    store.upsert(
        owner_id="mem_1",
        owner_type="memory",
        embedding=[0.1, 0.2, 0.3],
        payload={"model": "test-model"}
    )
    
    assert store.count() == 1


def test_upsert_replaces_existing(store):
    # Initial upsert
    store.upsert(
        owner_id="mem_1",
        owner_type="memory",
        embedding=[0.1, 0.2, 0.3],
        payload={"model": "test-model"}
    )
    
    # Update same owner
    store.upsert(
        owner_id="mem_1",
        owner_type="memory",
        embedding=[0.4, 0.5, 0.6],
        payload={"model": "updated-model"}
    )
    
    assert store.count() == 1


def test_search_similarity(store):
    # Upsert vectors with different similarities to [1.0, 0.0, 0.0]
    store.upsert("v1", "test", [1.0, 0.0, 0.0])   # Exact match
    store.upsert("v2", "test", [0.0, 1.0, 0.0])   # Orthogonal
    store.upsert("v3", "test", [0.8, 0.2, 0.0])   # Close match
    
    results = store.search([1.0, 0.0, 0.0], owner_type="test", top_k=2)
    
    assert len(results) == 2
    # Exact match should be first
    assert results[0]["owner_id"] == "v1"
    # Close match should be second
    assert results[1]["owner_id"] == "v3"


def test_search_filters_by_owner_type(store):
    store.upsert("msg1", "message", [0.5, 0.5, 0.5])
    store.upsert("mem1", "memory", [0.5, 0.5, 0.5])
    
    # Search specifically for messages
    results = store.search([0.5, 0.5, 0.5], owner_type="message")
    
    assert len(results) == 1
    assert results[0]["owner_id"] == "msg1"


def test_delete_vector(store):
    store.upsert("v1", "test", [0.1, 0.1, 0.1])
    assert store.count() == 1
    
    store.delete("v1")
    assert store.count() == 0


def test_search_empty_store(store):
    results = store.search([0.1, 0.2, 0.3])
    assert results == []


def test_empty_embedding_upsert(store):
    store.upsert("v1", "test", [])
    assert store.count() == 0
