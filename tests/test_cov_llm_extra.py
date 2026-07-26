import pytest
from unittest.mock import patch, MagicMock
from axiom.llm.ollama_client import OllamaClient, OllamaError
from axiom.memory.semantic import SemanticIndex
from axiom.memory.sleep_cycle import SleepCycleDaemon
from axiom.memory.memory_async import MemoryStore
from axiom.memory.vector_store import QdrantLocalStore
import asyncio

def test_ollama_client_capabilities_404():
    client = OllamaClient()
    
    with patch("axiom.llm.ollama_client.OllamaClient._request") as mock_req:
        mock_req.side_effect = [
            {"models": [{"name": "dummy"}]},  # GET /api/tags
            OllamaError("HTTP 404"),         # POST /api/chat
        ]
        client._detect_capabilities()
        assert client.capabilities["chat"] is True
        
        mock_req.side_effect = [
            {"models": [{"name": "real"}]},
            OllamaError("HTTP 404"),
        ]
        client._detect_capabilities()
        assert client.capabilities["chat"] is False
        
        mock_req.side_effect = [
            {"models": [{"name": "real"}]},
            OllamaError("HTTP 500"),
        ]
        client._detect_capabilities()
        assert client.capabilities["chat"] is True

def test_ollama_generate_error():
    client = OllamaClient()
    with patch("axiom.llm.ollama_client.OllamaClient._request", side_effect=OllamaError("err")):
        with pytest.raises(OllamaError):
            client.generate("hi")

def test_ollama_chat_fallback():
    client = OllamaClient()
    client.capabilities["chat"] = False
    
    with patch("axiom.llm.ollama_client.OllamaClient.generate", return_value="generated"):
        res = client.chat([{"role": "user", "content": "hi"}, {"role": "system", "content": "sys"}, {"role": "assistant", "content": "hello"}])
        assert res == "generated"

def test_ollama_chat_404_fallback():
    client = OllamaClient()
    client.capabilities["chat"] = True
    
    with patch("axiom.llm.ollama_client.OllamaClient._request", side_effect=OllamaError("HTTP 404")):
        with patch("axiom.llm.ollama_client.OllamaClient.generate", return_value="fallback_gen"):
            res = client.chat([{"role": "user", "content": "hi"}])
            assert res == "fallback_gen"
            assert client.capabilities["chat"] is False

@pytest.mark.asyncio
async def test_memory_async_extras():
    store = MemoryStore(":memory:")
    await store.initialize()
    
    # Try corrupt DB
    with patch("aiosqlite.connect", side_effect=Exception("DatabaseError")):
        try:
            await store.initialize()
        except Exception:
            pass
            
    # Try migration legacy embeddings
    class MockVec:
        def count(self): return 0
        def upsert(self, owner_id, owner_type, emb, payload): pass
        
    store._semantic._vector_store = MockVec()
    await store._migrate_legacy_embeddings()
    
    # search_by_tags is tested manually
    await store.search_by_tags(["t1"])
    
    # create_agent_session
    sid = await store.create_agent_session("agent", "task")
    await store.log_tool_call(sid, "tool", {"a": 1}, {"b": 2}, 100, False, "err")
    
    await store.close()

def test_qdrant_misc():
    store = QdrantLocalStore(":memory:")
    # collection exist
    store._collection_initialized = True
    store._ensure_collection(10)
    store.search([0.1])
    store.delete("id")
    store.count()
    
def test_semantic_qdrant_fallback():
    from axiom.memory.semantic import SemanticIndex
    idx = SemanticIndex()
    # force db err
    class MockDB:
        async def execute(self, *args):
            raise Exception("sqlite err")
    db = MockDB()
    import asyncio
    asyncio.run(idx.search(db, [0.1]))

def test_sleep_cycle_more():
    daemon = SleepCycleDaemon(None, None, None)
    daemon._last_activity_time = 0
    daemon._last_compaction_time = 0
    daemon._idle_threshold = 0
    # try maintenance
    try:
        daemon._run_maintenance()
    except Exception:
        pass
    
    # Mock LLM for episodic memory
    class MockMem:
        def _conn(self): return None
        def get_conversation_history(self, limit):
            return [{"role": "user", "content": "hi"} for _ in range(5)]
        def set(self, key, value, tags):
            pass
        def create_conversation(self, title):
            pass
    class MockLLM:
        def chat_with_tools(self, m, t, timeout):
            return {"content": "```json\n{\"key_facts\":[],\"user_preferences\":[]}\n```"}
    daemon2 = SleepCycleDaemon(None, MockMem(), MockLLM())
    daemon2._run_consolidation()

def test_sync_memory_extras():
    from axiom.memory.memory_sync import SyncMemoryStore
    store = SyncMemoryStore(":memory:")
    store._conn
    store.get_events("event", "src", 10)
    store.get_conversation()
    
    # no conversation add_message
    with pytest.raises(RuntimeError):
        store.add_message("user", "hi")
        
    store.create_conversation()
    
    store.search_relevant("")
    store.search_semantic("hello")
    store.close()
