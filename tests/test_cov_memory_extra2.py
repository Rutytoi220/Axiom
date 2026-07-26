import pytest
import asyncio
from unittest.mock import patch, MagicMock
from axiom.memory.semantic import SemanticIndex
from axiom.memory.sleep_cycle import SleepCycleDaemon
from axiom.memory.context_manager import ContextManager
from axiom.memory.vector_store import QdrantLocalStore

@pytest.mark.asyncio
async def test_semantic_index_sqlite_fallback():
    idx = SemanticIndex()
    idx._vector_store = None
    
    class MockDB:
        async def execute(self, query, params=()):
            class MockCursor:
                async def fetchall(self):
                    if "WHERE e.owner_type = ?" in query:
                        return [{"id": 1, "owner_id": "test", "owner_type": "type1", "embedding_json": "[0.1, 0.2]", "model": "m", "emb_created_at": "2024-01-01 12:00:00", "mem_created_at": None, "confidence_weight": 1.0, "tags_json": "[]"}]
                    return [{"id": 1, "owner_id": "test", "owner_type": "type2", "embedding_json": "[0.1, 0.2]", "model": "m", "emb_created_at": "2024-01-01 12:00:00", "mem_created_at": None, "confidence_weight": 1.0, "tags_json": "[]"}]
            return MockCursor()
    
    db = MockDB()
    await idx.search(db, [0.1, 0.2], owner_type="type1")
    await idx.search(db, [0.1, 0.2])

def test_sleep_cycle_consolidation():
    class MockMem:
        def get_conversation_history(self, limit):
            return [{"role": "user", "content": "hi"} for _ in range(5)]
        def set(self, key, value, tags):
            pass
        def create_conversation(self, title):
            pass

    class MockLLM:
        def chat_with_tools(self, messages, tools, timeout):
            return {"content": "```json\n{\"key_facts\":[],\"user_preferences\":[]}\n```"}
            
    daemon = SleepCycleDaemon(None, MockMem(), MockLLM())
    daemon._run_consolidation()
    
    # Try chat fallback
    class MockLLM2:
        def chat(self, messages, timeout):
            return "{\"key_facts\":[],\"user_preferences\":[]}"
            
    daemon2 = SleepCycleDaemon(None, MockMem(), MockLLM2())
    daemon2._run_consolidation()

def test_context_manager_truncate():
    cm = ContextManager()
    msgs = [{"role": "user", "content": "hello world" * 100}]
    cm._truncate_section(msgs, 10)

def test_qdrant_store():
    # Attempt to hit except blocks by mocking qdrant_client
    with patch.dict('sys.modules', {'qdrant_client': None}):
        try:
            QdrantLocalStore()
        except ImportError:
            pass
    
    # Missing search error
    store = QdrantLocalStore(":memory:")
    original_query = store.client.query_points
    store.client.query_points = MagicMock(side_effect=Exception("mock err"))
    store.search([0.1], owner_type="test")
    
    original_del = store.client.delete
    store.client.delete = MagicMock(side_effect=Exception("mock err"))
    store.delete("id1")
    
    original_count = store.client.count
    store.client.count = MagicMock(side_effect=Exception("mock err"))
    store.count()
    
    # Ensure collection
    store._collection_initialized = False
    original_create = store.client.create_collection
    store.client.create_collection = MagicMock(side_effect=Exception("mock err"))
    store._ensure_collection(128)
