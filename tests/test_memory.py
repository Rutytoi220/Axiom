"""Test suite for AXIOM memory system."""

import asyncio
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from axiom.memory import MemoryStore


@pytest.fixture
async def memory_store():
    """Create a temporary memory store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        store = MemoryStore(db_path=str(db_path))
        await store.initialize()
        yield store
        await store.close()


class TestMemoryStoreBasic:
    """Test basic memory operations."""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test storing and retrieving values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store a value
            await store.set("test_key", "test_value")
            
            # Retrieve the value
            value = await store.get("test_key")
            assert value == "test_value"
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_set_and_get_complex_types(self):
        """Test storing and retrieving complex Python types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store complex types
            data = {
                "name": "test",
                "numbers": [1, 2, 3],
                "nested": {"key": "value"},
                "bool": True,
                "null": None
            }
            
            await store.set("complex", data)
            result = await store.get("complex")
            
            assert result == data
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting non-existent keys returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            result = await store.get("nonexistent")
            assert result is None
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_delete_key(self):
        """Test deleting keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store and delete
            await store.set("to_delete", "value")
            deleted = await store.delete("to_delete")
            assert deleted is True
            
            # Verify it's gone
            value = await store.get("to_delete")
            assert value is None
            
            # Delete non-existent returns False
            deleted = await store.delete("nonexistent")
            assert deleted is False
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_update_value(self):
        """Test updating existing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Set initial value
            await store.set("key", "value1")
            assert await store.get("key") == "value1"
            
            # Update value
            await store.set("key", "value2")
            assert await store.get("key") == "value2"
            
            await store.close()


class TestMemoryStoreWithTTL:
    """Test TTL (time-to-live) functionality."""
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test setting values with TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Set with long TTL
            await store.set("long_ttl", "value", ttl=3600)
            value = await store.get("long_ttl")
            assert value == "value"
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Test that TTL causes values to expire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Set with very short TTL (1 second)
            await store.set("short_ttl", "value", ttl=1)
            assert await store.get("short_ttl") == "value"
            
            # Wait for expiry
            await asyncio.sleep(1.1)
            
            # Should now be expired
            value = await store.get("short_ttl")
            assert value is None
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_expire_ttl_cleanup(self):
        """Test the expire_ttl cleanup method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Set multiple values with different TTLs
            await store.set("short1", "value1", ttl=1)
            await store.set("short2", "value2", ttl=1)
            await store.set("long", "value3", ttl=3600)
            
            # Wait for short ones to expire
            await asyncio.sleep(1.1)
            
            # Expire TTL
            expired_count = await store.expire_ttl()
            
            # Should have expired 2 items
            assert expired_count == 2
            
            # Long TTL should still exist
            assert await store.get("long") == "value3"
            
            # Short ones should not
            assert await store.get("short1") is None
            assert await store.get("short2") is None
            
            await store.close()


class TestMemoryStoreWithTags:
    """Test tag-based searching."""
    
    @pytest.mark.asyncio
    async def test_set_with_tags(self):
        """Test setting values with tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            tags = ["important", "config", "system"]
            await store.set("config_key", {"setting": "value"}, tags=tags)
            
            result = await store.get("config_key")
            assert result == {"setting": "value"}
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_search_by_tags(self):
        """Test searching memories by tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store multiple values with different tags
            await store.set("item1", "value1", tags=["tag1", "tag2"])
            await store.set("item2", "value2", tags=["tag2", "tag3"])
            await store.set("item3", "value3", tags=["tag1", "tag3"])
            await store.set("item4", "value4", tags=["other"])
            
            # Search for items with tag1
            results = await store.search(["tag1"])
            assert len(results) == 2
            keys = [r["key"] for r in results]
            assert "item1" in keys
            assert "item3" in keys
            
            # Search for items with tag2
            results = await store.search(["tag2"])
            assert len(results) == 2
            
            # Search for items with non-existent tag
            results = await store.search(["nonexistent"])
            assert len(results) == 0
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_search_with_multiple_tags(self):
        """Test searching with multiple tags (AND logic)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store items with various tag combinations
            await store.set("item1", "value1", tags=["database", "cache", "redis"])
            await store.set("item2", "value2", tags=["database", "cache", "sql"])
            await store.set("item3", "value3", tags=["cache", "redis"])
            await store.set("item4", "value4", tags=["database", "sql"])
            
            # Search for items with both "database" and "cache"
            results = await store.search(["database", "cache"])
            assert len(results) == 2
            keys = [r["key"] for r in results]
            assert "item1" in keys
            assert "item2" in keys
            
            await store.close()


class TestEventLogging:
    """Test event logging functionality."""
    
    @pytest.mark.asyncio
    async def test_log_event(self):
        """Test logging events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Log an event
            event_id = await store.log_event(
                event_name="test.event",
                payload={"action": "test", "status": "success"},
                source="test_source"
            )
            
            assert event_id > 0
            
            # Retrieve the event
            events = await store.get_events(event_name="test.event")
            assert len(events) >= 1
            
            event = events[0]
            assert event["event_name"] == "test.event"
            assert event["payload"]["action"] == "test"
            assert event["source"] == "test_source"
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_log_event_without_payload(self):
        """Test logging events without payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            event_id = await store.log_event("simple.event", source="test")
            assert event_id > 0
            
            events = await store.get_events(event_name="simple.event")
            assert len(events) >= 1
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_get_events_filtering(self):
        """Test filtering events by name and source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Log multiple events
            await store.log_event("event.a", source="source1")
            await store.log_event("event.b", source="source1")
            await store.log_event("event.a", source="source2")
            
            # Filter by event name
            events = await store.get_events(event_name="event.a")
            assert len(events) >= 2
            
            # Filter by source
            events = await store.get_events(source="source1")
            assert len(events) >= 2
            
            # Filter by both
            events = await store.get_events(event_name="event.a", source="source1")
            assert len(events) >= 1
            
            await store.close()


class TestToolCallLogging:
    """Test tool call logging."""
    
    @pytest.mark.asyncio
    async def test_create_session_and_log_tool_call(self):
        """Test creating sessions and logging tool calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Create a session
            session_id = await store.create_agent_session(
                agent_name="test_agent",
                task="test task"
            )
            assert session_id > 0
            
            # Log a tool call
            tool_call_id = await store.log_tool_call(
                session_id=session_id,
                tool_name="shell",
                params={"command": "echo hello"},
                result={"stdout": "hello\n", "returncode": 0},
                duration_ms=50,
                success=True
            )
            assert tool_call_id > 0
            
            # Retrieve tool calls
            calls = await store.get_session_tool_calls(session_id)
            assert len(calls) == 1
            
            call = calls[0]
            assert call["tool_name"] == "shell"
            assert call["params"]["command"] == "echo hello"
            assert call["duration_ms"] == 50
            assert call["success"] is True
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_complete_agent_session(self):
        """Test completing agent sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Create and complete a session
            session_id = await store.create_agent_session(
                agent_name="orchestrator",
                task="complex task"
            )
            
            result = {"output": "task completed", "status": "success"}
            await store.complete_agent_session(
                session_id=session_id,
                result=result,
                success=True
            )
            
            # Session was completed successfully
            # (Direct verification would require additional query method)
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_log_failed_tool_call(self):
        """Test logging failed tool calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            session_id = await store.create_agent_session(
                agent_name="test_agent",
                task="test"
            )
            
            # Log a failed tool call
            tool_call_id = await store.log_tool_call(
                session_id=session_id,
                tool_name="shell",
                params={"command": "false"},
                result={"returncode": 1},
                duration_ms=25,
                success=False,
                error_message="Command returned non-zero exit code"
            )
            assert tool_call_id > 0
            
            calls = await store.get_session_tool_calls(session_id)
            assert len(calls) == 1
            
            call = calls[0]
            assert call["success"] is False
            assert "non-zero" in call["error_message"]
            
            await store.close()


class TestConcurrentAccess:
    """Test concurrent access to memory store."""
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(self):
        """Test concurrent write operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Perform concurrent writes
            tasks = []
            for i in range(10):
                tasks.append(store.set(f"key_{i}", f"value_{i}"))
            
            await asyncio.gather(*tasks)
            
            # Verify all were written
            for i in range(10):
                value = await store.get(f"key_{i}")
                assert value == f"value_{i}"
            
            await store.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Test concurrent read and write operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Pre-populate
            for i in range(5):
                await store.set(f"existing_{i}", f"value_{i}")
            
            # Mix reads and writes
            async def read_and_write(index):
                await store.set(f"new_{index}", f"new_value_{index}")
                value = await store.get(f"existing_{index % 5}")
                return value
            
            tasks = [read_and_write(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # All operations should complete
            assert len(results) == 10
            
            await store.close()


class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_operation_without_initialization(self):
        """Test that operations fail gracefully without initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            
            # Try to use without initialization
            with pytest.raises(RuntimeError):
                await store.set("key", "value")
    
    @pytest.mark.asyncio
    async def test_search_with_empty_tags(self):
        """Test search with empty tag list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store items
            await store.set("key1", "value1", tags=["tag1"])
            
            # Search with empty tags
            results = await store.search([])
            assert len(results) == 0
            
            await store.close()


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = MemoryStore(db_path=str(db_path))
            await store.initialize()
            
            # Store configuration
            config = {"api_url": "http://localhost:8000", "timeout": 30}
            await store.set("app_config", config, tags=["config", "system"])
            
            # Log an event
            await store.log_event("app.started", payload={"version": "1.0"}, source="main")
            
            # Create a session
            session_id = await store.create_agent_session("orchestrator", "process_data")
            
            # Log tool calls
            await store.log_tool_call(
                session_id=session_id,
                tool_name="fetch",
                params={"url": "http://localhost:8000/data"},
                result={"status": 200, "data": [1, 2, 3]},
                duration_ms=100,
                success=True
            )
            
            await store.log_tool_call(
                session_id=session_id,
                tool_name="process",
                params={"data": [1, 2, 3]},
                result={"processed": 3},
                duration_ms=50,
                success=True
            )
            
            # Complete session
            await store.complete_agent_session(
                session_id=session_id,
                result={"items_processed": 3},
                success=True
            )
            
            # Verify all data
            assert await store.get("app_config") == config
            
            events = await store.get_events(event_name="app.started")
            assert len(events) >= 1
            
            tool_calls = await store.get_session_tool_calls(session_id)
            assert len(tool_calls) == 2
            
            await store.close()
