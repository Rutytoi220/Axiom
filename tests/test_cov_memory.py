import pytest
from axiom.memory.memory_sync import SyncMemoryStore
from axiom.memory.memory_async import MemoryStore
from axiom.memory.vector_store import QdrantLocalStore

def test_sync_memory_store_coverage():
    store = SyncMemoryStore(":memory:")
    
    store.expire_ttl()
    store.log_event("test_event", {"a": 1})
    store.create_agent_session("agent1", "task")
    store.log_tool_call(1, "tool", {}, {}, 100, True)
    store.get_session_tool_calls(1)
    store.complete_agent_session(1, {})
    store.create_conversation("title")
    store.add_message("user", "hello")
    store.get_conversation_history()
    store.restore_conversation("conv_id")
    store.search_relevant("hello")
    store.search_semantic("hello")
    store.save_tool_execution("tool", {}, {})
    store.list_keys()
    store.expire("key", 10)
    store.expire()
    
    # TTL and search
    store.set("key", "val", ttl=10, tags=["t1"])
    store.get("key")
    store.search(["t1"])
    store.delete("key")
    
    store.close()

@pytest.mark.asyncio
async def test_async_memory_store_coverage():
    store = MemoryStore(":memory:")
    await store.initialize()
    
    await store.expire_ttl()
    await store.log_event("test_event", {"a": 1})
    await store.create_agent_session("agent1", "task")
    await store.log_tool_call(1, "tool", {}, {}, 100, True)
    await store.get_session_tool_calls(1)
    await store.complete_agent_session(1, {})
    await store.create_conversation("title")
    await store.add_message("conv_id", "user", "hello")
    await store.get_messages("conv_id")
    await store.list_conversations()
    await store.save_summary("conv_id", "summary", 1, 2)
    await store.get_summaries("conv_id")
    await store.store_embedding("id", "type", [0.1, 0.2])
    await store.search_similar([0.1, 0.2], top_k=2)
    await store.get_events()
    
    await store.set("key", "val", ttl=10, tags=["t1"])
    await store.get("key")
    await store.search(["t1"])
    await store.delete("key")
    
    await store.close()

def test_vector_store_coverage():
    store = QdrantLocalStore(":memory:")
    
    # Store text
    store.upsert("id1", "type1", [0.1, 0.2], {"a": 1})
    store.upsert("id2", "type1", []) # empty
    
    # Search
    store.search([0.1, 0.2], owner_type="type1", top_k=2)
    store.search([])
    
    store.count()
    store.delete("id1")
