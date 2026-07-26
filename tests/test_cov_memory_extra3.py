import pytest
from unittest.mock import patch, MagicMock
from axiom.memory.semantic import SemanticIndex
from axiom.memory.memory_async import MemoryStore
from axiom.memory.context_manager import estimate_tokens, estimate_messages_tokens, ContextManager
import asyncio
import sys

@pytest.mark.asyncio
async def test_memory_async_more():
    store = MemoryStore(":memory:")
    # fail to connect loop
    with patch("aiosqlite.connect", side_effect=Exception("SQL err")):
        try:
            await store.initialize()
        except Exception:
            pass
            
    await store.initialize()
    
    # force migration with data
    class MockVec:
        def count(self): return 10
        def upsert(self, owner_id, owner_type, emb, payload): pass
        
    store._semantic._vector_store = MockVec()
    await store.store_embedding("old", "memory", [0.1])
    # manually make it legacy
    await store._conn().execute("UPDATE embeddings SET model='dummy'")
    await store._conn().commit()
    await store._migrate_legacy_embeddings()
    await store.close()

@pytest.mark.asyncio
async def test_semantic_more():
    idx = SemanticIndex()
    # has provider search text error
    class ErrProv:
        def embed(self, t, m=None):
            raise Exception("embed error")
    idx._provider = ErrProv()
    class MockDB: pass
    db = MockDB()
    await idx.search_text(db, "hi")
    
    # db error for semantic text
    class NilProv:
        def embed(self, t, m=None): return None
    idx._provider = NilProv()
    await idx.search_text(db, "hi")

def test_context_manager_misc():
    cm = ContextManager(summarize_fn=lambda x: "summary")
    msg1 = {"role": "user", "content": "hello", "_cached_tokens": 10}
    estimate_messages_tokens([msg1])
    estimate_tokens("")
    
    msgs = []
    for i in range(25):
        msgs.append({"role": "user", "content": "hello " * 10})
        
    cm.build_context_window([{"role": "system", "content": "sys"}], msgs, "task", [{"m":1}], [{"o":1}])
    cm.should_summarize(msgs)
    cm.get_turns_for_summary(msgs)

def test_semantic_init_qdrant():
    with patch.dict('sys.modules', {'qdrant_client': None}):
        try:
            SemanticIndex()
        except Exception:
            pass
    # force lock file
    with patch("pathlib.Path.exists", return_value=True):
        with patch("os.remove", side_effect=Exception("mock err")):
            try:
                SemanticIndex()
            except Exception:
                pass

def test_sleep_cycle_compaction():
    from axiom.memory.sleep_cycle import SleepCycleDaemon
    class MockMem:
        def _conn(self):
            class MockDB:
                def execute(self, q, p): pass
                def commit(self): pass
            return MockDB()
    d = SleepCycleDaemon(None, MockMem(), None)
    d._run_maintenance()
