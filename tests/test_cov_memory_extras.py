import pytest
import asyncio
from axiom.memory.blackboard import BlackboardStore
from axiom.memory.context_manager import ContextManager, estimate_tokens
from axiom.memory.semantic import SemanticIndex
from axiom.memory.sleep_cycle import SleepCycleDaemon

def test_blackboard_store_coverage():
    store = BlackboardStore()
    store.write("session1", "agent1", "key1", "val1")
    assert store.read("session1", "agent1", "key1") == "val1"
    assert store.read("session1", "agent1", "missing", "default") == "default"
    assert "key1" in store.list_keys("session1", "agent1")
    assert "missing" not in store.list_keys("session1", "missing")
    assert "agent1" in store.list_agents("session1")
    dump = store.dump_session("session1")
    assert dump["agent1"]["key1"] == "val1"
    store.purge_session("session1")
    assert store.read("session1", "agent1", "key1") is None
    assert store.uri("session1", "agent1", "key1") == "blackboard://session1/agent1/key1"

def test_context_manager_coverage():
    cm = ContextManager(max_tokens=2000)
    assert cm.input_budget > 0
    sys_msgs = [{"role": "system", "content": "system string"}]
    chat_hist = [{"role": "user", "content": "hi"} for _ in range(15)]
    res = cm.build_context_window(sys_msgs, chat_hist, "current task", [{"mem": 1}], [{"obs": 1}])
    assert len(res) > 0
    assert cm.should_summarize(chat_hist) is True
    assert cm.get_turns_for_summary(chat_hist) == chat_hist[:-12]
    
    # Text truncation
    long_task = "word " * 200
    res2 = cm.build_context_window(sys_msgs, [], long_task, None, None)
    
    # summarize_turns fallback
    cm2 = ContextManager(summarize_fn=lambda x: "summary")
    cm2._summarize_turns([{"role": "user", "content": "hi"}])
    cm3 = ContextManager(summarize_fn=lambda x: "")
    cm3._summarize_turns([{"role": "user", "content": "hi"}])

@pytest.mark.asyncio
async def test_semantic_index_coverage():
    idx = SemanticIndex()
    assert idx.has_provider is False
    
    class MockProvider:
        def embed(self, text, model=None):
            return [0.1, 0.2]
    
    idx2 = SemanticIndex(provider=MockProvider())
    assert idx2.has_provider is True
    
    class MockDB:
        async def execute(self, *args, **kwargs):
            return self
        async def commit(self):
            pass
        async def fetchall(self):
            return []
    
    db = MockDB()
    await idx2.store_text(db, "id1", "type1", "hello")
    await idx2.search_text(db, "hello", "type1")

def test_sleep_cycle_coverage():
    from axiom.core.events import EventBus
    from axiom.memory.memory_sync import SyncMemoryStore
    bus = EventBus()
    sm = SyncMemoryStore(":memory:")
    daemon = SleepCycleDaemon(bus, sm)
    daemon._run_maintenance()
    daemon.start()
    daemon.stop()
