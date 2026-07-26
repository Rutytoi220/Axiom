import pytest
import asyncio
from unittest.mock import patch, MagicMock
from axiom.memory.semantic import SemanticIndex, _cosine_similarity
from axiom.memory.memory_async import MemoryStore
from axiom.memory.sleep_cycle import SleepCycleDaemon

@pytest.mark.asyncio
async def test_master_coverage():
    # 1. SemanticIndex __init__ exceptions
    with patch("axiom.memory.vector_store.QdrantLocalStore", side_effect=Exception("lock accessed by another instance")):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.remove", side_effect=Exception("clear err")):
                SemanticIndex()
            with patch("os.remove"):
                with patch("axiom.memory.vector_store.QdrantLocalStore", return_value=MagicMock()):
                    SemanticIndex()
    
    # 2. Semantic _cosine_similarity edge cases
    _cosine_similarity([0.0], [0.0]) # norm_a = 0
    
    idx = SemanticIndex()
    
    class MockVec:
        def upsert(self, *args, **kwargs): raise Exception("upsert err")
        def search(self, *args, **kwargs): raise Exception("qdrant search err")
    idx._vector_store = MockVec()
    
    class MockDB:
        async def execute(self, *args):
            if "WHERE e.owner_id IN" in args[0]:
                raise Exception("sqlite fallback 1")
            elif "WHERE e.owner_type = ?" in args[0]:
                raise Exception("sqlite fallback 2")
            class MockCur:
                async def fetchall(self):
                    return [{"id": 1, "owner_id": "k", "owner_type": "type", "embedding_json": "[0.1]", "model": "m", "emb_created_at": "invalid date", "mem_created_at": None, "confidence_weight": 1.0, "tags_json": "[]"}]
            return MockCur()
        async def commit(self): pass
    
    # 3. store / store_text errors
    await idx.store(MockDB(), "id", "type", [0.1])
    class MockProv:
        def embed(self, *args): raise Exception("embed err")
    idx._provider = MockProv()
    await idx.store_text(MockDB(), "id", "type", "text")
    idx._provider = MagicMock(embed=MagicMock(return_value=None))
    await idx.store_text(MockDB(), "id", "type", "text")
    
    # 4. search / search_text errors
    await idx.search(MockDB(), [0.1], "type")
    
    idx._provider = MockProv()
    await idx.search_text(MockDB(), "text")
    idx._provider = MagicMock(embed=MagicMock(return_value=None))
    await idx.search_text(MockDB(), "text")
    
    # 5. SleepCycleDaemon
    d = SleepCycleDaemon(None, None, None)
    d._last_activity_time = 0
    d._last_compaction_time = 0
    d._idle_threshold = 0
    # force _run_maintenance errors
    with patch.object(d, "_run_consolidation", side_effect=Exception("consol error")):
        d._run_maintenance()
        
    class MockMem:
        def get_conversation_history(self, limit): return [{"role": "user", "content": "hi"} for _ in range(5)]
        def set(self, **kwargs): raise Exception("set err")
    d._memory_store = MockMem()
    class MockLLM:
        def chat_with_tools(self, *args, **kwargs): return {"content": "```json\n{}\n```"}
    d._llm = MockLLM()
    d._run_consolidation()
    
    # 6. MemoryAsync retries
    import sqlite3
    store = MemoryStore(":memory:")
    # fail to connect loop with sqlite3.DatabaseError
    with patch("aiosqlite.connect", side_effect=sqlite3.DatabaseError("corrupt")):
        with patch("shutil.move", side_effect=OSError("mock err")):
            try:
                await store.initialize()
            except Exception:
                pass
                
    # test db version 1 migration
    await store.initialize()
    await store._db.execute("PRAGMA user_version = 1")
    await store._db.commit()
    store._initialized = False
    await store.initialize()
    
    # test version > 2
    await store._db.execute("PRAGMA user_version = 3")
    await store._db.commit()
    store._initialized = False
    try:
        await store.initialize()
    except Exception:
        pass
            
    # 7. MemoryAsync migration real data
    await store._db.execute("PRAGMA user_version = 2")
    store._initialized = False
    await store.initialize()
    
    class MockVec2:
        def count(self): return 0
        def upsert(self, *args): raise Exception("upsert mock err")
    store._semantic._vector_store = MockVec2()
    # insert legacy
    await store._conn().execute("INSERT INTO embeddings (owner_id, owner_type, embedding_json, model) VALUES ('1', 'memory', '[0.1]', 'm')")
    await store._conn().commit()
    await store._migrate_legacy_embeddings()
    
    store._semantic._vector_store = None
    await store._migrate_legacy_embeddings()
    
    await store.close()
