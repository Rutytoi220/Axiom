"""Test suite for AXIOM core components."""

import pytest
from axiom.core import Engine, Event, EventBus, Registry, ExecutionContext
from axiom.memory import MemoryManager
from axiom.tools import ShellTool, FileTool
from axiom.agents import OrchestratorAgent


class TestEngine:
    """Test the AXIOM Engine."""

    def test_engine_init(self):
        """Test engine initialization."""
        engine = Engine()
        assert not engine.is_running()

        engine.initialize()
        assert engine.is_running()

        engine.shutdown()
        assert not engine.is_running()

    def test_engine_context(self):
        """Test execution context."""
        engine = Engine()
        engine.initialize()

        context = engine.create_context("test input")
        assert context is not None
        assert context.user_input == "test input"


class TestEventBus:
    """Test the event bus."""

    def test_subscribe_publish(self):
        """Test pub/sub functionality."""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe("test.event", handler)

        event = Event(event_type="test.event", source="test")
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].event_type == "test.event"

    def test_event_history(self):
        """Test event history."""
        bus = EventBus()

        for i in range(5):
            event = Event(event_type="test.event", source="test", data={"num": i})
            bus.publish(event)

        history = bus.get_history("test.event")
        assert len(history) == 5


class TestRegistry:
    """Test the registry system."""

    def test_tool_registry(self):
        """Test tool registration."""
        registry = Registry()
        tool = ShellTool()

        # Use the core Registry API (register_tool)
        registry.register_tool("shell", tool)

        retrieved = registry.get_tool("shell")
        assert retrieved is not None

        tools = registry.list_tools()
        assert len(tools) > 0


class TestMemoryManager:
    """Test memory management."""

    def test_conversation_creation(self, tmp_path):
        """Test conversation creation."""
        db_path = str(tmp_path / "test.db")
        memory = MemoryManager(db_path)

        conv_id = memory.create_conversation("Test")
        assert conv_id is not None
        assert memory.get_conversation() == conv_id

    def test_message_storage(self, tmp_path):
        """Test message storage."""
        db_path = str(tmp_path / "test.db")
        memory = MemoryManager(db_path)

        memory.create_conversation("Test")
        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi there!")

        history = memory.get_conversation_history()
        assert len(history) == 2


class TestTools:
    """Test tool system."""

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test tool execution."""
        tool = ShellTool()
        result = await tool.execute({"command": "echo test"})

        assert result.success
        assert "test" in result.output["stdout"]

    def test_tool_info(self):
        """Test tool info retrieval."""
        tool = FileTool(".")
        assert tool.name == "file"
        assert len(tool.schema["properties"]) > 0


class TestAgents:
    """Test agent system."""

    @pytest.mark.asyncio
    async def test_orchestrator_agent(self):
        """Test orchestrator agent."""
        agent = OrchestratorAgent()
        result = await agent.run("test input")

        assert result.success is True
        assert result.output is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
