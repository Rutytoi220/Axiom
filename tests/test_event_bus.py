"""Test suite for EventBus pub/sub system."""

import pytest
from unittest.mock import Mock

from axiom.core.events import EventBus, Event


class TestEventDataclass:
    """Test Event dataclass."""

    def test_event_creation_with_minimal_fields(self):
        event = Event(event_type="test.event", source="test")
        assert event.event_type == "test.event"
        assert event.source == "test"
        assert event.data == {}

    def test_event_creation_with_data(self):
        payload = {"key": "value", "number": 42}
        event = Event(event_type="test.event", source="test", data=payload)
        assert event.event_type == "test.event"
        assert event.data == payload

    def test_event_to_dict(self):
        event = Event(event_type="test", source="src", data={"d": 1})
        d = event.to_dict()
        assert d["event_type"] == "test"
        assert d["source"] == "src"
        assert d["data"] == {"d": 1}
        assert "event_id" in d
        assert "timestamp" in d


class TestEventBusInitialization:
    def test_bus_initialization(self):
        bus = EventBus()
        assert bus.get_subscriptions() == {}
        assert bus.get_published_events() == set()

    def test_multiple_bus_instances_isolated(self):
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is not bus2
        assert bus1.get_subscriptions() is not bus2.get_subscriptions()


class TestEventBusSubscribe:
    def test_subscribe_single_handler(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        assert "test.event" in bus.get_subscriptions()
        assert bus.get_subscriptions()["test.event"] == 1

    def test_subscribe_multiple_handlers_same_event(self):
        bus = EventBus()
        bus.subscribe("test.event", Mock())
        bus.subscribe("test.event", Mock())
        bus.subscribe("test.event", Mock())
        assert bus.get_subscriptions()["test.event"] == 3

    def test_subscribe_same_handler_multiple_events(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("event1", handler)
        bus.subscribe("event2", handler)
        bus.subscribe("event3", handler)
        assert bus.get_subscriptions()["event1"] == 1
        assert bus.get_subscriptions()["event2"] == 1
        assert bus.get_subscriptions()["event3"] == 1

    def test_subscribe_with_wildcard_pattern(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("agent.*", handler)
        bus.subscribe("*.started", handler)
        bus.subscribe("*", handler)
        assert "agent.*" in bus.get_subscriptions()
        assert "*.started" in bus.get_subscriptions()
        assert "*" in bus.get_subscriptions()

    def test_subscribe_duplicate_handler_allowed(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        bus.subscribe("test.event", handler)
        assert bus.get_subscriptions()["test.event"] == 2


class TestEventBusUnsubscribe:
    def test_unsubscribe_existing_handler(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        assert "test.event" not in bus.get_subscriptions()

    def test_unsubscribe_nonexistent_handler(self):
        bus = EventBus()
        handler1 = Mock()
        handler2 = Mock()
        bus.subscribe("test.event", handler1)
        bus.unsubscribe("test.event", handler2)
        assert bus.get_subscriptions()["test.event"] == 1

    def test_unsubscribe_from_nonexistent_event(self):
        bus = EventBus()
        handler = Mock()
        # Should not raise
        bus.unsubscribe("nonexistent.event", handler)

    def test_unsubscribe_one_handler_multiple_remain(self):
        bus = EventBus()
        h1, h2, h3 = Mock(), Mock(), Mock()
        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)
        bus.subscribe("test.event", h3)
        bus.unsubscribe("test.event", h2)
        assert bus.get_subscriptions()["test.event"] == 2


class TestEventBusPublishBasic:
    def test_publish_to_no_subscribers(self):
        bus = EventBus()
        bus.publish(Event(event_type="test.event", source="test"))
        assert "test.event" in bus.get_published_events()

    def test_publish_calls_handler(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        bus.publish(Event(event_type="test.event", source="test", data={"key": "value"}))
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, Event)
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}

    def test_publish_calls_multiple_handlers(self):
        bus = EventBus()
        h1, h2, h3 = Mock(), Mock(), Mock()
        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)
        bus.subscribe("test.event", h3)
        bus.publish(Event(event_type="test.event", source="test"))
        h1.assert_called_once()
        h2.assert_called_once()
        h3.assert_called_once()


class TestEventBusWildcards:
    def test_wildcard_agent_prefix(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("agent.*", handler)
        bus.publish(Event(event_type="agent.started", source="test"))
        bus.publish(Event(event_type="agent.stopped", source="test"))
        bus.publish(Event(event_type="agent.error", source="test"))
        bus.publish(Event(event_type="task.started", source="test"))  # should not match
        assert handler.call_count == 3

    def test_wildcard_suffix_pattern(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("*.started", handler)
        bus.publish(Event(event_type="agent.started", source="test"))
        bus.publish(Event(event_type="task.started", source="test"))
        bus.publish(Event(event_type="plugin.started", source="test"))
        bus.publish(Event(event_type="agent.stopped", source="test"))  # should not match
        assert handler.call_count == 3

    def test_wildcard_match_all(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("*", handler)
        bus.publish(Event(event_type="event1", source="test"))
        bus.publish(Event(event_type="event2", source="test"))
        bus.publish(Event(event_type="any.event.name", source="test"))
        # Wildcard matches all events plus meta-events (bus.published for each)
        assert handler.call_count == 6

    def test_exact_match_priority(self):
        bus = EventBus()
        exact_handler = Mock()
        wildcard_handler = Mock()
        bus.subscribe("agent.started", exact_handler)
        bus.subscribe("agent.*", wildcard_handler)
        bus.publish(Event(event_type="agent.started", source="test"))
        exact_handler.assert_called_once()
        wildcard_handler.assert_called_once()

    def test_no_unintended_wildcard_matches(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("agent.start*", handler)
        bus.publish(Event(event_type="agent.started", source="test"))
        bus.publish(Event(event_type="agent.starting", source="test"))
        bus.publish(Event(event_type="agent.start", source="test"))
        bus.publish(Event(event_type="agent.stop", source="test"))  # should not match
        assert handler.call_count == 3


class TestEventBusExceptionHandling:
    def test_sync_handler_exception_logged(self):
        bus = EventBus()

        def failing_handler(event):
            raise ValueError("Test error")

        successful_handler = Mock()
        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", successful_handler)
        # Should not raise
        bus.publish(Event(event_type="test.event", source="test"))
        successful_handler.assert_called_once()

    def test_multiple_handler_exceptions(self):
        bus = EventBus()

        def failing1(event):
            raise ValueError("Error 1")

        def failing2(event):
            raise ValueError("Error 2")

        successful = Mock()
        bus.subscribe("test.event", failing1)
        bus.subscribe("test.event", successful)
        bus.subscribe("test.event", failing2)
        bus.publish(Event(event_type="test.event", source="test"))
        successful.assert_called_once()


class TestEventBusMetaEvents:
    def test_bus_published_meta_event(self):
        bus = EventBus()
        meta_handler = Mock()
        bus.subscribe("bus.published", meta_handler)
        bus.publish(Event(event_type="test.event", source="test", data={"data": "value"}))
        meta_handler.assert_called_once()
        meta_event = meta_handler.call_args[0][0]
        assert meta_event.event_type == "bus.published"
        assert meta_event.data["event"] == "test.event"
        assert meta_event.data["original_payload"] == {"data": "value"}

    def test_bus_published_with_wildcard(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("bus.*", handler)
        bus.publish(Event(event_type="test.event", source="test"))
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert event.event_type == "bus.published"

    def test_meta_event_no_infinite_recursion(self):
        bus = EventBus()
        # A handler that publishes on every event — should not recurse
        def re_publisher(event):
            bus.publish(Event(event_type="derived.event", source="test"))

        bus.subscribe("test.event", re_publisher)
        bus.subscribe("derived.event", Mock())
        # Should complete without RecursionError
        bus.publish(Event(event_type="test.event", source="test"))


class TestEventBusDebugMethods:
    def test_get_subscriptions(self):
        bus = EventBus()
        bus.subscribe("event1", Mock())
        bus.subscribe("event1", Mock())
        bus.subscribe("event2", Mock())
        subs = bus.get_subscriptions()
        assert subs["event1"] == 2
        assert subs["event2"] == 1

    def test_get_published_events(self):
        bus = EventBus()
        bus.publish(Event(event_type="event1", source="test"))
        bus.publish(Event(event_type="event2", source="test"))
        bus.publish(Event(event_type="event1", source="test"))  # duplicate
        published = bus.get_published_events()
        assert published == {"event1", "event2"}

    def test_subscribers_method(self):
        bus = EventBus()
        h1, h2 = Mock(), Mock()
        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)
        subs = bus.subscribers("test.event")
        assert len(subs) == 2
        assert h1 in subs
        assert h2 in subs


class TestEventBusClear:
    def test_clear_removes_subscriptions(self):
        bus = EventBus()
        bus.subscribe("event1", Mock())
        bus.subscribe("event2", Mock())
        bus.clear()
        assert bus.get_subscriptions() == {}

    def test_clear_resets_published_events(self):
        bus = EventBus()
        bus.publish(Event(event_type="event1", source="test"))
        bus.publish(Event(event_type="event2", source="test"))
        bus.clear()
        assert bus.get_published_events() == set()

    def test_clear_allows_reuse(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("event1", handler)
        bus.publish(Event(event_type="event1", source="test"))
        handler.assert_called_once()
        bus.clear()
        handler2 = Mock()
        bus.subscribe("event2", handler2)
        bus.publish(Event(event_type="event2", source="test"))
        handler2.assert_called_once()


class TestEventBusIntegration:
    def test_pub_sub_workflow(self):
        bus = EventBus()
        events_received = []

        def collector(event):
            events_received.append(event.event_type)

        bus.subscribe("agent.*", collector)
        bus.subscribe("*.error", collector)
        bus.publish(Event(event_type="agent.started", source="test", data={"id": "a1"}))
        bus.publish(Event(event_type="agent.stopped", source="test", data={"id": "a1"}))
        bus.publish(Event(event_type="task.error", source="test", data={"message": "failed"}))
        bus.publish(Event(event_type="task.completed", source="test"))  # should not match
        assert events_received == ["agent.started", "agent.stopped", "task.error"]

    def test_event_chaining(self):
        bus = EventBus()
        events_chain = []

        def on_start(event):
            events_chain.append("started")
            bus.publish(Event(event_type="system.initialized", source="test"))

        def on_init(event):
            events_chain.append("initialized")
            bus.publish(Event(event_type="system.ready", source="test"))

        def on_ready(event):
            events_chain.append("ready")

        bus.subscribe("system.start", on_start)
        bus.subscribe("system.initialized", on_init)
        bus.subscribe("system.ready", on_ready)
        bus.publish(Event(event_type="system.start", source="test"))
        assert events_chain == ["started", "initialized", "ready"]

    def test_event_bus_with_complex_payloads(self):
        bus = EventBus()
        received_payloads = []

        def collector(event):
            received_payloads.append(event.data)

        bus.subscribe("data.*", collector)
        payload1 = {"items": [1, 2, 3], "metadata": {"timestamp": "2026-05-17"}}
        payload2 = [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]
        bus.publish(Event(event_type="data.received", source="test", data=payload1))
        bus.publish(Event(event_type="data.processed", source="test", data=payload2))
        assert received_payloads == [payload1, payload2]

    def test_publish_sync_convenience(self):
        bus = EventBus()
        handler = Mock()
        bus.subscribe("test.event", handler)
        bus.publish_sync("test.event", {"key": "value"})
        handler.assert_called_once()
        event = handler.call_args[0][0]
        assert isinstance(event, Event)
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}
