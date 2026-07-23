"""Tests for Memory Compaction and Sleep Cycle."""

import pytest
import asyncio
import json
import numpy as np
from datetime import datetime, timedelta
import math

from axiom.memory.memory_async import MemoryStore
from axiom.memory.compactor import MemoryCompactor

@pytest.fixture
async def memory_store(tmp_path):
    db_path = str(tmp_path / "test_memory.db")
    store = MemoryStore(db_path)
    await store.initialize()
    
    # Enable test mode without an external LLM
    class DummyProvider:
        def embed(self, text, model=None):
            # Deterministic simple vectors for testing
            if "apple" in text:
                vec = [1.0, 0.0, 0.0]
            elif "banana" in text:
                vec = [0.99, 0.1, 0.0] # High similarity to apple
            elif "dog" in text:
                vec = [0.0, 1.0, 0.0]
            else:
                vec = [0.0, 0.0, 1.0]
            return vec + [0.0] * (768 - len(vec))
            
    store.semantic._provider = DummyProvider()
    yield store
    await store.close()

@pytest.mark.asyncio
async def test_compactor_deduplicates(memory_store):
    db = memory_store._conn()
    
    # Store two very similar memories manually to bypass any LLM calls
    # One is older, one is newer
    vec1 = [1.0, 0.0, 0.0] + [0.0] * 765
    vec2 = [0.99, 0.1, 0.0] + [0.0] * 765
    
    await memory_store.set("mem1", "apple is red", tags=[])
    await memory_store.set("mem2", "banana is yellow", tags=[])
    
    await memory_store.semantic.store(db, "mem1", "memory", vec1)
    await memory_store.semantic.store(db, "mem2", "memory", vec2)
    
    # Manually tweak dates and retrieval counts
    await db.execute("UPDATE memories SET created_at = '2023-01-01 10:00:00', retrieval_count = 5 WHERE key = 'mem1'")
    await db.execute("UPDATE memories SET created_at = '2023-01-02 10:00:00', retrieval_count = 2, confidence_weight = 1.0 WHERE key = 'mem2'")
    await db.commit()
    
    compactor = MemoryCompactor(db)
    result = await compactor.run_compaction()
    
    assert result["scanned"] == 2
    assert result["merged"] == 1
    assert result["deleted"] == 1
    
    # Check that mem1 (older) was deleted and mem2 (newer) kept
    cursor = await db.execute("SELECT * FROM memories")
    rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["key"] == "mem2"
    
    # Check that retrieval_count was merged (max of 5 and 2)
    assert rows[0]["retrieval_count"] == 5
    
    # Check that confidence was boosted (+0.1)
    assert abs(rows[0]["confidence_weight"] - 1.1) < 0.001

@pytest.mark.asyncio
async def test_semantic_search_decay(memory_store):
    db = memory_store._conn()
    
    vec1 = [1.0, 0.0, 0.0] + [0.0] * 765
    vec2 = [1.0, 0.0, 0.0] + [0.0] * 765
    
    await memory_store.set("mem_new", "apple", tags=[])
    await memory_store.set("mem_old", "apple old", tags=[])
    
    await memory_store.semantic.store(db, "mem_new", "memory", vec1)
    await memory_store.semantic.store(db, "mem_old", "memory", vec2)
    
    # Tweak dates to simulate decay
    # mem_old is 100 days old
    import time
    now_dt = datetime.fromtimestamp(time.time())
    old_dt = now_dt - timedelta(days=100)
    old_str = old_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    new_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    await db.execute("UPDATE memories SET created_at = ? WHERE key = 'mem_old'", (old_str,))
    await db.execute("UPDATE memories SET created_at = ? WHERE key = 'mem_new'", (new_str,))
    await db.commit()
    
    results = await memory_store.semantic.search(db, [1.0, 0.0, 0.0] + [0.0] * 765, owner_type="memory")
    
    assert len(results) == 2
    
    # new should have higher similarity score due to decay on old
    new_res = next(r for r in results if r["owner_id"] == "mem_new")
    old_res = next(r for r in results if r["owner_id"] == "mem_old")
    
    assert new_res["similarity"] > old_res["similarity"]
    assert math.isclose(new_res["decay_factor"], 1.0, rel_tol=1e-4)
    
    # old_res decay should be roughly e^(-0.01 * 100) = e^-1 ≈ 0.367
    assert 0.35 < old_res["decay_factor"] < 0.38
    
@pytest.mark.asyncio
async def test_retrieval_count_increments(memory_store):
    await memory_store.set("test_key", "value")
    
    val1 = await memory_store.get("test_key")
    assert val1 == "value"
    
    val2 = await memory_store.get("test_key")
    
    db = memory_store._conn()
    cursor = await db.execute("SELECT retrieval_count FROM memories WHERE key = 'test_key'")
    row = await cursor.fetchone()
    
    # Should have been retrieved 2 times
    assert row["retrieval_count"] == 2
