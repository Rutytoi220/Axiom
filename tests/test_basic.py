"""Test suite for AXIOM MemoryStore."""

import unittest
import time
from axiom.memory import SyncMemoryStore as MemoryStore
from axiom.llm import PromptBuilder


class TestMemoryStore(unittest.TestCase):
    """Test MemoryStore implementation."""

    def setUp(self):
        """Create a MemoryStore instance for each test."""
        self.mem = MemoryStore(":memory:")

    def test_set_and_get_dict_value(self):
        """Test storing and retrieving a dict value."""
        test_data = {"name": "test", "count": 42}
        self.mem.set("mykey", test_data)
        result = self.mem.get("mykey")
        self.assertEqual(result, test_data)

    def test_set_and_get_string_value(self):
        """Test storing and retrieving a string value."""
        test_string = "hello world"
        self.mem.set("strkey", test_string)
        result = self.mem.get("strkey")
        self.assertEqual(result, test_string)

    def test_get_missing_key_returns_none(self):
        """Test that getting a missing key returns None."""
        result = self.mem.get("nonexistent_key")
        self.assertIsNone(result)

    def test_delete_existing_key_returns_true(self):
        """Test that deleting an existing key returns True."""
        self.mem.set("to_delete", "value")
        result = self.mem.delete("to_delete")
        self.assertTrue(result)
        # Verify it's gone
        self.assertIsNone(self.mem.get("to_delete"))

    def test_delete_missing_key_returns_false(self):
        """Test that deleting a missing key returns False."""
        result = self.mem.delete("never_existed")
        self.assertFalse(result)

    def test_list_keys_returns_all_non_expired_keys(self):
        """Test that list_keys returns all non-expired keys."""
        self.mem.set("key1", "value1")
        self.mem.set("key2", "value2")
        self.mem.set("key3", "value3")
        
        keys = self.mem.list_keys()
        self.assertIn("key1", keys)
        self.assertIn("key2", keys)
        self.assertIn("key3", keys)
        self.assertEqual(len(keys), 3)

    def test_set_same_key_twice_updates_value(self):
        """Test that setting the same key twice updates the value."""
        self.mem.set("updatekey", "value1")
        self.mem.set("updatekey", "value2")
        result = self.mem.get("updatekey")
        self.assertEqual(result, "value2")

    def test_set_same_key_twice_updates_timestamp(self):
        """Test that updated_at changes when key is updated."""
        self.mem.set("timekey", "value1")
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        
        # Get the created_at from the database
        import sqlite3
        cursor = self.mem._conn.execute(
            "SELECT created_at, updated_at FROM memories WHERE key = ?",
            ("timekey",),
        )
        row = cursor.fetchone()
        created_at_1 = row["created_at"]
        updated_at_1 = row["updated_at"]
        
        # Update the key
        self.mem.set("timekey", "value2")
        
        cursor = self.mem._conn.execute(
            "SELECT created_at, updated_at FROM memories WHERE key = ?",
            ("timekey",),
        )
        row = cursor.fetchone()
        created_at_2 = row["created_at"]
        updated_at_2 = row["updated_at"]
        
        # created_at should remain the same
        self.assertEqual(created_at_1, created_at_2)
        # updated_at should have changed
        self.assertGreater(updated_at_2, updated_at_1)

    def test_ttl_expiry_with_expire(self):
        """Test that TTL expiry works with the expire() method."""
        # Set a key with very short TTL (0.05 seconds)
        self.mem.set("expiring_key", "value", ttl=0.05)
        
        # Should exist immediately
        self.assertEqual(self.mem.get("expiring_key"), "value")
        
        # Wait for expiration
        time.sleep(0.1)
        
        # Call expire to clean up expired entries
        expired_count = self.mem.expire()
        self.assertGreaterEqual(expired_count, 1)
        
        # Should now return None
        self.assertIsNone(self.mem.get("expiring_key"))

    def test_log_event_stores_entry(self):
        """Test that log_event stores an entry."""
        event_id = self.mem.log_event("test.event", data={"action": "test"}, source="unittest")
        self.assertGreater(event_id, 0)

    def test_get_events_returns_entries(self):
        """Test that get_events returns logged entries."""
        self.mem.log_event("event1", data={"num": 1}, source="test")
        self.mem.log_event("event2", data={"num": 2}, source="test")
        
        events = self.mem.get_events()
        self.assertGreaterEqual(len(events), 2)

    def test_get_events_filtered_by_event_name(self):
        """Test that get_events can be filtered by event_name."""
        self.mem.log_event("event.a", data={"action": "a"}, source="test")
        self.mem.log_event("event.b", data={"action": "b"}, source="test")
        self.mem.log_event("event.a", data={"action": "a2"}, source="test")
        
        events_a = self.mem.get_events(event_name="event.a")
        events_b = self.mem.get_events(event_name="event.b")
        
        self.assertGreaterEqual(len(events_a), 2)
        self.assertGreaterEqual(len(events_b), 1)
        
        # All returned events should have the correct name
        for event in events_a:
            self.assertEqual(event["event_name"], "event.a")

    def test_search_by_tag_returns_matching_entries(self):
        """Test that search returns entries matching tags."""
        self.mem.set("item1", "value1", tags=["urgent", "work"])
        self.mem.set("item2", "value2", tags=["work", "review"])
        self.mem.set("item3", "value3", tags=["personal"])
        
        results = self.mem.search(["urgent"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "item1")

    def test_search_returns_empty_when_no_match(self):
        """Test that search returns empty list when no entries match."""
        self.mem.set("item1", "value1", tags=["work"])
        self.mem.set("item2", "value2", tags=["home"])
        
        results = self.mem.search(["nonexistent"])
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()


class TestEventBus(unittest.TestCase):
    """Test EventBus functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        from axiom.events import EventBus
        self.bus = EventBus()
    
    def test_publish_returns_entry_dict(self):
        """Test that publish returns entry dict with correct event/data keys."""
        result = self.bus.publish_sync("test.event", {"key": "value"})
        self.assertIsInstance(result, dict)
        self.assertIn("event", result)
        self.assertIn("data", result)
        self.assertIn("timestamp", result)
        self.assertEqual(result["event"], "test.event")
        self.assertEqual(result["data"], {"key": "value"})
    
    def test_log_records_events_in_order(self):
        """Test that log records events in order."""
        self.bus.publish_sync("event1", {"num": 1})
        self.bus.publish_sync("event2", {"num": 2})
        self.bus.publish_sync("event3", {"num": 3})
        
        log = self.bus.log()
        self.assertEqual(len(log), 3)
        self.assertEqual(log[0]["event"], "event1")
        self.assertEqual(log[1]["event"], "event2")
        self.assertEqual(log[2]["event"], "event3")
    
    def test_subscribe_handler_is_called_on_publish(self):
        """Test that subscribe handler is called on publish."""
        received = []
        self.bus.subscribe("test.event", lambda n, d: received.append((n, d)))
        self.bus.publish_sync("test.event", {"message": "hello"})
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "test.event")
        self.assertEqual(received[0][1], {"message": "hello"})
    
    def test_unsubscribed_handler_is_not_called(self):
        """Test that unsubscribed handler is NOT called."""
        received = []
        handler = lambda n, d: received.append((n, d))
        self.bus.subscribe("test.event", handler)
        self.bus.unsubscribe("test.event", handler)
        self.bus.publish_sync("test.event", {"message": "hello"})
        
        self.assertEqual(len(received), 0)
    
    def test_publishing_with_no_handlers_does_not_crash(self):
        """Test that publishing with no handlers does not crash."""
        try:
            self.bus.publish_sync("no.handlers", {"data": "test"})
        except Exception as e:
            self.fail(f"Publishing with no handlers raised {type(e).__name__}")
    
    def test_multiple_handlers_all_called(self):
        """Test that multiple handlers all called."""
        received1 = []
        received2 = []
        received3 = []
        self.bus.subscribe("test.event", lambda n, d: received1.append((n, d)))
        self.bus.subscribe("test.event", lambda n, d: received2.append((n, d)))
        self.bus.subscribe("test.event", lambda n, d: received3.append((n, d)))
        
        self.bus.publish_sync("test.event", {"message": "test"})
        
        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)
        self.assertEqual(len(received3), 1)
    
    def test_clear_log_empties_the_log(self):
        """Test that clear_log empties the log."""
        self.bus.publish_sync("event1", {"data": 1})
        self.bus.publish_sync("event2", {"data": 2})
        self.assertEqual(len(self.bus.log()), 2)
        
        self.bus.clear_log()
        self.assertEqual(len(self.bus.log()), 0)
    
    def test_non_callable_subscribe_raises_typeerror(self):
        """Test that non-callable subscribe raises TypeError."""
        with self.assertRaises(TypeError):
            self.bus.subscribe("test.event", "not_callable")


class TestRegistry(unittest.TestCase):
    """Test Registry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        from axiom.registry import Registry
        self.registry = Registry()
    
    def test_register_and_get_roundtrip(self):
        """Test that register and get roundtrip correctly."""
        self.registry.register("test_obj", "my_value")
        result = self.registry.get("test_obj")
        self.assertEqual(result, "my_value")
    
    def test_get_missing_returns_none(self):
        """Test that get missing returns None."""
        result = self.registry.get("nonexistent")
        self.assertIsNone(result)
    
    def test_get_or_raise_missing_raises_registryerror(self):
        """Test that get_or_raise missing raises RegistryError."""
        from axiom.registry import RegistryError
        with self.assertRaises(RegistryError):
            self.registry.get_or_raise("nonexistent")
    
    def test_duplicate_register_raises_registryerror(self):
        """Test that duplicate register raises RegistryError."""
        from axiom.registry import RegistryError
        self.registry.register("test_obj", "value1")
        with self.assertRaises(RegistryError):
            self.registry.register("test_obj", "value2")
    
    def test_list_returns_sorted_names(self):
        """Test that list returns sorted names."""
        self.registry.register("charlie", "c")
        self.registry.register("apple", "a")
        self.registry.register("bob", "b")
        
        names = self.registry.list()
        self.assertEqual(names, ["apple", "bob", "charlie"])
    
    def test_unregister_returns_true_then_get_returns_none(self):
        """Test that unregister returns True, then get returns None."""
        self.registry.register("test_obj", "value")
        result = self.registry.unregister("test_obj")
        self.assertTrue(result)
        self.assertIsNone(self.registry.get("test_obj"))
    
    def test_unregister_missing_returns_false(self):
        """Test that unregister missing returns False."""
        result = self.registry.unregister("nonexistent")
        self.assertFalse(result)
    
    def test_contains_works(self):
        """Test that __contains__ works."""
        self.registry.register("test_obj", "value")
        self.assertIn("test_obj", self.registry)
        self.assertNotIn("nonexistent", self.registry)
    
    def test_len_works(self):
        """Test that __len__ works."""
        self.assertEqual(len(self.registry), 0)
        self.registry.register("obj1", "value1")
        self.assertEqual(len(self.registry), 1)
        self.registry.register("obj2", "value2")
        self.assertEqual(len(self.registry), 2)
    
    def test_empty_string_name_raises_registryerror(self):
        """Test that empty string name raises RegistryError."""
        from axiom.registry import RegistryError
        with self.assertRaises(RegistryError):
            self.registry.register("", "value")


class TestTools(unittest.TestCase):
    """Test Tool classes."""
    
    def test_echo_tool_name(self):
        """Test that EchoTool.name == 'echo'."""
        from axiom.tools import EchoTool
        tool = EchoTool()
        self.assertEqual(tool.name, "echo")
    
    def test_execute_with_text_returns_success(self):
        """Test that execute with text returns success=True, correct output."""
        from axiom.tools import EchoTool
        tool = EchoTool()
        result = tool.execute({"text": "hello world"})
        self.assertTrue(result.success)
        self.assertEqual(result.output, "hello world")
    
    def test_execute_without_text_returns_error(self):
        """Test that execute without text returns success=False with error."""
        from axiom.tools import EchoTool
        tool = EchoTool()
        result = tool.execute({})
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("text", result.error)
    
    def test_execute_converts_non_string_to_str(self):
        """Test that execute converts non-string to str."""
        from axiom.tools import EchoTool
        tool = EchoTool()
        result = tool.execute({"text": 42})
        self.assertTrue(result.success)
        self.assertEqual(result.output, "42")
    
    def test_base_tool_execute_raises_notimplementederror(self):
        """Test that BaseTool.execute raises NotImplementedError."""
        from axiom.tools import BaseTool
        tool = BaseTool()
        with self.assertRaises(NotImplementedError):
            tool.execute({})


class TestEnginePhase2(unittest.TestCase):
    """Test Engine Phase 2 functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        from axiom.engine import Engine
        self.engine = Engine()
    
    def test_engine_has_bus_attribute(self):
        """Test that engine has .bus attribute (EventBus instance)."""
        from axiom.events import EventBus
        self.assertIsNotNone(self.engine.bus)
        self.assertIsInstance(self.engine.bus, EventBus)
    
    def test_engine_has_registry_attribute(self):
        """Test that engine has .registry attribute (Registry instance)."""
        from axiom.registry import Registry
        self.assertIsNotNone(self.engine.registry)
        self.assertIsInstance(self.engine.registry, Registry)
    
    def test_start_emits_engine_started_event(self):
        """Test that start() emits 'engine.started' event."""
        received = []
        self.engine.bus.subscribe("engine.started", lambda n, d: received.append((n, d)))
        self.engine.start()
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "engine.started")
    
    def test_stop_emits_engine_stopped_event(self):
        """Test that stop() emits 'engine.stopped' event."""
        self.engine.start()
        received = []
        self.engine.bus.subscribe("engine.stopped", lambda n, d: received.append((n, d)))
        self.engine.stop()
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "engine.stopped")
    
    def test_start_stop_appear_in_bus_log(self):
        """Test that start/stop appear in bus.log()."""
        self.engine.start()
        self.engine.stop()
        
        log = self.engine.bus.log()
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0]["event"], "engine.started")
        self.assertEqual(log[1]["event"], "engine.stopped")
    
    def test_registry_is_usable_from_engine_instance(self):
        """Test that registry is usable from engine instance."""
        self.engine.registry.register("test_tool", "test_value")
        result = self.engine.registry.get("test_tool")
        self.assertEqual(result, "test_value")


class TestMemoryStoreComprehensive(unittest.TestCase):
    """Comprehensive tests for MemoryStore - verify all operations."""
    
    def setUp(self):
        """Create a MemoryStore instance for each test."""
        from axiom.memory import SyncMemoryStore as MemoryStore
        self.mem = MemoryStore(":memory:")
    
    def test_set_and_get_dict(self):
        """Test: set("k", {"a": 1}), get("k") == {"a": 1}"""
        self.mem.set("k", {"a": 1})
        self.assertEqual(self.mem.get("k"), {"a": 1})
    
    def test_set_and_get_string(self):
        """Test: set("k", "hello"), get("k") == "hello" """
        self.mem.set("k", "hello")
        self.assertEqual(self.mem.get("k"), "hello")
    
    def test_get_missing_returns_none(self):
        """Test: get("nonexistent") is None"""
        self.assertIsNone(self.mem.get("nonexistent"))
    
    def test_delete_existing_returns_true(self):
        """Test: set then delete → True"""
        self.mem.set("k", "value")
        result = self.mem.delete("k")
        self.assertTrue(result)
    
    def test_delete_missing_returns_false(self):
        """Test: delete("nope") == False"""
        result = self.mem.delete("nope")
        self.assertFalse(result)
    
    def test_list_keys(self):
        """Test: set 3 keys, list_keys() contains all 3"""
        self.mem.set("key1", "v1")
        self.mem.set("key2", "v2")
        self.mem.set("key3", "v3")
        keys = self.mem.list_keys()
        self.assertIn("key1", keys)
        self.assertIn("key2", keys)
        self.assertIn("key3", keys)
        self.assertEqual(len(keys), 3)
    
    def test_update_same_key(self):
        """Test: set("k", 1), set("k", 2) — should not raise; get("k") == 2"""
        self.mem.set("k", 1)
        self.mem.set("k", 2)  # Should not raise
        self.assertEqual(self.mem.get("k"), 2)
    
    def test_ttl_expiry(self):
        """Test: set with ttl=0.001, sleep, get returns None"""
        self.mem.set("k", "v", ttl=0.001)
        time.sleep(0.05)
        self.assertIsNone(self.mem.get("k"))
    
    def test_log_event_stored(self):
        """Test: log_event("ping", {"x": 1}); get_events() has 1 entry"""
        self.mem.log_event("ping", {"x": 1})
        events = self.mem.get_events()
        self.assertEqual(len(events), 1)
    
    def test_get_events_filtered(self):
        """Test: log multiple events, filter by name returns correct entry"""
        self.mem.log_event("a", None)
        self.mem.log_event("b", None)
        
        events_a = self.mem.get_events(event_name="a")
        self.assertEqual(len(events_a), 1)
        self.assertEqual(events_a[0]["event_name"], "a")
    
    def test_search_by_tags(self):
        """Test: search by tags returns matching entries"""
        self.mem.set("item1", "v1", tags=["urgent", "work"])
        self.mem.set("item2", "v2", tags=["work", "review"])
        self.mem.set("item3", "v3", tags=["personal"])
        
        results = self.mem.search(["urgent"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["key"], "item1")
    
    def test_set_with_tags(self):
        """Test: set with tags stores and retrieves tags correctly"""
        self.mem.set("k", "value", tags=["tag1", "tag2"])
        results = self.mem.search(["tag1"])
        self.assertEqual(len(results), 1)
        self.assertIn("tag1", results[0]["tags"])
        self.assertIn("tag2", results[0]["tags"])
    
    def test_expire_sets_ttl(self):
        """Test: expire() method sets TTL on existing key"""
        self.mem.set("k", "value")
        self.mem.expire("k", 0.001)
        self.assertIsNotNone(self.mem.get("k"))
        time.sleep(0.05)
        self.assertIsNone(self.mem.get("k"))


class TestPromptBuilder(unittest.TestCase):
    """Test suite for PromptBuilder class."""
    
    def test_build_returns_list(self):
        """Test: PromptBuilder().user('hi').build() is a list"""
        result = PromptBuilder().user('hi').build()
        self.assertIsInstance(result, list)
    
    def test_system_prepended(self):
        """Test: .system('s').user('u').build()[0]['role'] == 'system'"""
        result = PromptBuilder().system('s').user('u').build()
        self.assertEqual(result[0]['role'], 'system')
    
    def test_order_preserved(self):
        """Test: .user('a').assistant('b').user('c').build() preserves order"""
        result = PromptBuilder().user('a').assistant('b').user('c').build()
        roles = [msg['role'] for msg in result]
        self.assertEqual(roles, ['user', 'assistant', 'user'])
    
    def test_build_raw_returns_string(self):
        """Test: .user('hi').build_raw() is a str"""
        result = PromptBuilder().user('hi').build_raw()
        self.assertIsInstance(result, str)
    
    def test_reset_clears(self):
        """Test: pb.reset() clears all messages and system"""
        pb = PromptBuilder().user('x')
        pb.reset()
        self.assertEqual(pb.build(), [])
    
    def test_chaining(self):
        """Test: method chaining works correctly"""
        result = PromptBuilder().system('s').user('u').assistant('a').build()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]['role'], 'system')
        self.assertEqual(result[1]['role'], 'user')
        self.assertEqual(result[2]['role'], 'assistant')
    
    def test_no_system(self):
        """Test: .user('hi').build() without system has length 1"""
        result = PromptBuilder().user('hi').build()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['role'], 'user')


if __name__ == "__main__":
    unittest.main()
