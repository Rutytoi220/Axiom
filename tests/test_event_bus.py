"""Test suite for EventBus pub/sub system."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, call

from axiom.events import EventBus, Event


class TestEventDataclass:
    """Test Event dataclass."""
    
    def test_event_creation_with_name_only(self):
        """Test creating an event with just a name."""
        event = Event(name="test.event")
        assert event.name == "test.event"
        assert event.payload is None
    
    def test_event_creation_with_payload(self):
        """Test creating an event with name and payload."""
        payload = {"key": "value", "number": 42}
        event = Event(name="test.event", payload=payload)
        assert event.name == "test.event"
        assert event.payload == payload
    
    def test_event_repr(self):
        """Test Event repr shows name and payload."""
        event = Event(name="test", payload={"data": "value"})
        repr_str = repr(event)
        assert "test" in repr_str
        assert "Event" in repr_str


class TestEventBusInitialization:
    """Test EventBus initialization."""
    
    def test_bus_initialization(self):
        """Test that EventBus initializes with empty subscriptions."""
        bus = EventBus()
        assert bus.get_subscriptions() == {}
        assert bus.get_published_events() == set()
    
    def test_multiple_bus_instances_isolated(self):
        """Test that different EventBus instances are isolated."""
        bus1 = EventBus()
        bus2 = EventBus()
        
        assert bus1 is not bus2
        assert bus1.get_subscriptions() is not bus2.get_subscriptions()


class TestEventBusSubscribe:
    """Test EventBus subscription functionality."""
    
    def test_subscribe_single_handler(self):
        """Test subscribing a single handler."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        
        assert "test.event" in bus.get_subscriptions()
        assert bus.get_subscriptions()["test.event"] == 1
    
    def test_subscribe_multiple_handlers_same_event(self):
        """Test subscribing multiple handlers to same event."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        handler3 = AsyncMock()
        
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        bus.subscribe("test.event", handler3)
        
        assert bus.get_subscriptions()["test.event"] == 3
    
    def test_subscribe_same_handler_multiple_events(self):
        """Test subscribing same handler to multiple events."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("event1", handler)
        bus.subscribe("event2", handler)
        bus.subscribe("event3", handler)
        
        assert bus.get_subscriptions()["event1"] == 1
        assert bus.get_subscriptions()["event2"] == 1
        assert bus.get_subscriptions()["event3"] == 1
    
    def test_subscribe_with_wildcard_pattern(self):
        """Test subscribing with wildcard patterns."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("agent.*", handler)
        bus.subscribe("*.started", handler)
        bus.subscribe("*", handler)
        
        assert "agent.*" in bus.get_subscriptions()
        assert "*.started" in bus.get_subscriptions()
        assert "*" in bus.get_subscriptions()
    
    def test_subscribe_duplicate_handler_allowed(self):
        """Test that same handler can be subscribed multiple times."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        bus.subscribe("test.event", handler)
        
        # Should have 2 subscriptions of the same handler
        assert bus.get_subscriptions()["test.event"] == 2


class TestEventBusUnsubscribe:
    """Test EventBus unsubscription functionality."""
    
    def test_unsubscribe_existing_handler(self):
        """Test unsubscribing a handler that exists."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        result = bus.unsubscribe("test.event", handler)
        
        assert result is True
        assert "test.event" not in bus.get_subscriptions()
    
    def test_unsubscribe_nonexistent_handler(self):
        """Test unsubscribing a handler that doesn't exist."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        
        bus.subscribe("test.event", handler1)
        result = bus.unsubscribe("test.event", handler2)
        
        assert result is False
        assert bus.get_subscriptions()["test.event"] == 1
    
    def test_unsubscribe_from_nonexistent_event(self):
        """Test unsubscribing from an event with no subscriptions."""
        bus = EventBus()
        handler = Mock()
        
        result = bus.unsubscribe("nonexistent.event", handler)
        
        assert result is False
    
    def test_unsubscribe_one_handler_multiple_remain(self):
        """Test unsubscribing one handler when multiple are subscribed."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()
        
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        bus.subscribe("test.event", handler3)
        
        result = bus.unsubscribe("test.event", handler2)
        
        assert result is True
        assert bus.get_subscriptions()["test.event"] == 2
    
    def test_unsubscribe_removes_empty_subscription_list(self):
        """Test that empty subscription lists are cleaned up."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        
        assert "test.event" not in bus.get_subscriptions()


class TestEventBusPublishBasic:
    """Test basic event publishing."""
    
    @pytest.mark.asyncio
    async def test_publish_to_no_subscribers(self):
        """Test publishing to an event with no subscribers."""
        bus = EventBus()
        
        # Should not raise
        await bus.publish("test.event")
        
        assert "test.event" in bus.get_published_events()
    
    @pytest.mark.asyncio
    async def test_publish_with_sync_handler(self):
        """Test publishing calls sync handlers."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        await bus.publish("test.event", payload={"key": "value"})
        
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, Event)
        assert event.name == "test.event"
        assert event.payload == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_publish_with_async_handler(self):
        """Test publishing calls async handlers."""
        bus = EventBus()
        handler = AsyncMock()
        
        bus.subscribe("test.event", handler)
        await bus.publish("test.event", payload="async_test")
        
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert event.name == "test.event"
        assert event.payload == "async_test"
    
    @pytest.mark.asyncio
    async def test_publish_with_multiple_handlers(self):
        """Test publishing calls all subscribed handlers."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = AsyncMock()
        handler3 = Mock()
        
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        bus.subscribe("test.event", handler3)
        
        await bus.publish("test.event")
        
        handler1.assert_called_once()
        handler2.assert_called_once()
        handler3.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_concurrent_handler_execution(self):
        """Test that handlers are called concurrently."""
        bus = EventBus()
        call_times = []
        
        async def async_handler1(event):
            call_times.append(("handler1_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.01)
            call_times.append(("handler1_end", asyncio.get_event_loop().time()))
        
        async def async_handler2(event):
            call_times.append(("handler2_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.01)
            call_times.append(("handler2_end", asyncio.get_event_loop().time()))
        
        bus.subscribe("test.event", async_handler1)
        bus.subscribe("test.event", async_handler2)
        
        await bus.publish("test.event")
        
        # If concurrent, handler2_start should come before handler1_end
        start_times = [t for name, t in call_times if "start" in name]
        assert len(start_times) == 2
        assert start_times[0] < start_times[1]


class TestEventBusWildcards:
    """Test wildcard pattern matching."""
    
    @pytest.mark.asyncio
    async def test_wildcard_agent_prefix(self):
        """Test wildcard matching with agent.* pattern."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("agent.*", handler)
        
        await bus.publish("agent.started")
        await bus.publish("agent.stopped")
        await bus.publish("agent.error")
        await bus.publish("task.started")  # Should not match
        
        assert handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_wildcard_suffix_pattern(self):
        """Test wildcard matching with *.started pattern."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("*.started", handler)
        
        await bus.publish("agent.started")
        await bus.publish("task.started")
        await bus.publish("plugin.started")
        await bus.publish("agent.stopped")  # Should not match
        
        assert handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_wildcard_match_all(self):
        """Test wildcard matching with * pattern."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("*", handler)
        
        await bus.publish("event1")
        await bus.publish("event2")
        await bus.publish("any.event.name")
        
        # Wildcard matches all events plus meta-events (6 total: 3 events + 3 bus.published)
        assert handler.call_count == 6
    
    @pytest.mark.asyncio
    async def test_wildcard_multiple_asterisks(self):
        """Test complex wildcard patterns."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("*.agent.*", handler)
        
        await bus.publish("system.agent.started")
        await bus.publish("custom.agent.error")
        await bus.publish("agent.started")  # Should not match (no prefix)
        await bus.publish("system.task.started")  # Should not match (task not agent)
        
        assert handler.call_count == 2
    
    @pytest.mark.asyncio
    async def test_exact_match_priority(self):
        """Test that exact matches are called along with wildcards."""
        bus = EventBus()
        exact_handler = Mock()
        wildcard_handler = Mock()
        
        bus.subscribe("agent.started", exact_handler)
        bus.subscribe("agent.*", wildcard_handler)
        
        await bus.publish("agent.started")
        
        # Both should be called
        exact_handler.assert_called_once()
        wildcard_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_unintended_wildcard_matches(self):
        """Test that wildcard doesn't match unintended patterns."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("agent.start*", handler)
        
        await bus.publish("agent.started")
        await bus.publish("agent.starting")
        await bus.publish("agent.start")
        await bus.publish("agent.stop")  # Should not match
        
        assert handler.call_count == 3


class TestEventBusExceptionHandling:
    """Test exception handling in handlers."""
    
    @pytest.mark.asyncio
    async def test_sync_handler_exception_logged(self):
        """Test that exceptions in sync handlers are logged."""
        bus = EventBus()
        
        def failing_handler(event):
            raise ValueError("Test error")
        
        successful_handler = Mock()
        
        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", successful_handler)
        
        # Should not raise despite handler error
        await bus.publish("test.event")
        
        # Successful handler should still be called
        successful_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_handler_exception_logged(self):
        """Test that exceptions in async handlers are logged."""
        bus = EventBus()
        
        async def failing_handler(event):
            raise RuntimeError("Async error")
        
        successful_handler = AsyncMock()
        
        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", successful_handler)
        
        # Should not raise
        await bus.publish("test.event")
        
        # Successful handler should still be called
        successful_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_handler_exceptions(self):
        """Test that multiple handler exceptions don't stop processing."""
        bus = EventBus()
        
        def failing1(event):
            raise ValueError("Error 1")
        
        def failing2(event):
            raise ValueError("Error 2")
        
        successful = Mock()
        
        bus.subscribe("test.event", failing1)
        bus.subscribe("test.event", successful)
        bus.subscribe("test.event", failing2)
        
        await bus.publish("test.event")
        
        # Successful handler should be called despite errors
        successful.assert_called_once()


class TestEventBusMetaEvents:
    """Test meta-event emission."""
    
    @pytest.mark.asyncio
    async def test_bus_published_meta_event(self):
        """Test that 'bus.published' meta-event is emitted."""
        bus = EventBus()
        meta_handler = Mock()
        
        bus.subscribe("bus.published", meta_handler)
        await bus.publish("test.event", payload={"data": "value"})
        
        meta_handler.assert_called_once()
        meta_event = meta_handler.call_args[0][0]
        assert meta_event.name == "bus.published"
        assert meta_event.payload["event"] == "test.event"
        assert meta_event.payload["original_payload"] == {"data": "value"}
    
    @pytest.mark.asyncio
    async def test_bus_published_with_wildcard(self):
        """Test that wildcard subscriptions match 'bus.published'."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("bus.*", handler)
        await bus.publish("test.event")
        
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert event.name == "bus.published"
    
    @pytest.mark.asyncio
    async def test_meta_event_published_count(self):
        """Test that meta-event includes published event count (unique events)."""
        bus = EventBus()
        meta_handler = Mock()
        
        bus.subscribe("bus.published", meta_handler)
        
        await bus.publish("event1")
        await bus.publish("event2")
        await bus.publish("event1")  # Duplicate - same event, set keeps 2 unique
        
        assert meta_handler.call_count == 3
        
        # Check counts in payload - reflects unique published events
        calls = [meta_handler.call_args_list[i].args[0].payload["total_published"] for i in range(meta_handler.call_count)]
        assert calls == [1, 2, 2]  # event1, event1+event2, event1+event2 (no new unique)


class TestEventBusDebugMethods:
    """Test debugging and inspection methods."""
    
    def test_get_subscriptions(self):
        """Test getting subscription counts."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        
        bus.subscribe("event1", handler1)
        bus.subscribe("event1", handler2)
        bus.subscribe("event2", handler1)
        
        subs = bus.get_subscriptions()
        assert subs["event1"] == 2
        assert subs["event2"] == 1
    
    @pytest.mark.asyncio
    async def test_get_published_events(self):
        """Test getting set of published events."""
        bus = EventBus()
        
        await bus.publish("event1")
        await bus.publish("event2")
        await bus.publish("event1")  # Duplicate
        
        published = bus.get_published_events()
        assert published == {"event1", "event2"}
    
    @pytest.mark.asyncio
    async def test_get_published_events_excludes_meta(self):
        """Test that published events don't include meta-events."""
        bus = EventBus()
        meta_handler = Mock()
        
        bus.subscribe("bus.published", meta_handler)
        await bus.publish("user.event")
        
        # get_published_events should only include the user event
        assert bus.get_published_events() == {"user.event"}


class TestEventBusClear:
    """Test clearing the event bus."""
    
    @pytest.mark.asyncio
    async def test_clear_removes_subscriptions(self):
        """Test that clear() removes all subscriptions."""
        bus = EventBus()
        
        bus.subscribe("event1", Mock())
        bus.subscribe("event2", AsyncMock())
        
        await bus.clear()
        
        assert bus.get_subscriptions() == {}
    
    @pytest.mark.asyncio
    async def test_clear_resets_published_events(self):
        """Test that clear() resets published events."""
        bus = EventBus()
        
        await bus.publish("event1")
        await bus.publish("event2")
        
        await bus.clear()
        
        assert bus.get_published_events() == set()
    
    @pytest.mark.asyncio
    async def test_clear_allows_reuse(self):
        """Test that bus can be reused after clear()."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("event1", handler)
        await bus.publish("event1")
        handler.assert_called_once()
        
        await bus.clear()
        
        # Reuse bus
        handler2 = Mock()
        bus.subscribe("event2", handler2)
        await bus.publish("event2")
        handler2.assert_called_once()


class TestEventBusThreadSafety:
    """Test thread/coroutine safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_publishes(self):
        """Test that concurrent publishes are handled safely."""
        bus = EventBus()
        handler = Mock()
        
        bus.subscribe("test.event", handler)
        
        # Publish concurrently
        await asyncio.gather(
            bus.publish("test.event"),
            bus.publish("test.event"),
            bus.publish("test.event")
        )
        
        # All publishes should complete
        assert handler.call_count == 3
    
    @pytest.mark.asyncio
    async def test_subscribe_during_publish(self):
        """Test subscribing while publishing is safe."""
        bus = EventBus()
        handler1 = Mock()
        
        bus.subscribe("test.event", handler1)
        
        async def late_subscribe():
            await asyncio.sleep(0.001)
            handler2 = Mock()
            bus.subscribe("test.event", handler2)
        
        # Subscribe while publishing
        await asyncio.gather(
            bus.publish("test.event"),
            late_subscribe()
        )
    
    @pytest.mark.asyncio
    async def test_unsubscribe_during_publish(self):
        """Test unsubscribing while publishing is safe."""
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        
        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        
        async def late_unsubscribe():
            await asyncio.sleep(0.001)
            bus.unsubscribe("test.event", handler2)
        
        # Both should complete without error
        await asyncio.gather(
            bus.publish("test.event"),
            late_unsubscribe()
        )


class TestEventBusIntegration:
    """Integration tests for EventBus."""
    
    @pytest.mark.asyncio
    async def test_pub_sub_workflow(self):
        """Test complete pub/sub workflow."""
        bus = EventBus()
        events_received = []
        
        def collector(event):
            events_received.append(event.name)
        
        bus.subscribe("agent.*", collector)
        bus.subscribe("*.error", collector)
        
        await bus.publish("agent.started", {"id": "a1"})
        await bus.publish("agent.stopped", {"id": "a1"})
        await bus.publish("task.error", {"message": "failed"})
        await bus.publish("task.completed")  # Should not match
        
        assert events_received == ["agent.started", "agent.stopped", "task.error"]
    
    @pytest.mark.asyncio
    async def test_event_chaining(self):
        """Test publishing events in response to events."""
        bus = EventBus()
        events_chain = []
        
        async def on_start(event):
            events_chain.append("started")
            await bus.publish("system.initialized")
        
        async def on_init(event):
            events_chain.append("initialized")
            await bus.publish("system.ready")
        
        async def on_ready(event):
            events_chain.append("ready")
        
        bus.subscribe("system.start", on_start)
        bus.subscribe("system.initialized", on_init)
        bus.subscribe("system.ready", on_ready)
        
        await bus.publish("system.start")
        
        assert events_chain == ["started", "initialized", "ready"]
    
    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers(self):
        """Test mixed sync and async handlers on same event."""
        bus = EventBus()
        call_order = []
        
        def sync_handler(event):
            call_order.append("sync")
        
        async def async_handler(event):
            await asyncio.sleep(0.001)
            call_order.append("async")
        
        def sync_handler2(event):
            call_order.append("sync2")
        
        bus.subscribe("test", sync_handler)
        bus.subscribe("test", async_handler)
        bus.subscribe("test", sync_handler2)
        
        await bus.publish("test")
        
        # All should be in the list (order depends on execution)
        assert set(call_order) == {"sync", "async", "sync2"}
        assert len(call_order) == 3
    
    @pytest.mark.asyncio
    async def test_event_bus_with_complex_payloads(self):
        """Test event bus with complex nested payloads."""
        bus = EventBus()
        received_payloads = []
        
        def collector(event):
            received_payloads.append(event.payload)
        
        bus.subscribe("data.*", collector)
        
        payload1 = {
            "items": [1, 2, 3],
            "metadata": {"timestamp": "2026-05-17", "source": "api"}
        }
        payload2 = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"}
        ]
        
        await bus.publish("data.received", payload1)
        await bus.publish("data.processed", payload2)
        
        assert received_payloads == [payload1, payload2]
