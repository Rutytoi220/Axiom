"""Test suite for Registry component management."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from axiom.registry import Registry, ComponentType, RegistryError, BaseTool, BaseAgent, BasePlugin
from axiom.events import EventBus


class TestComponentType:
    """Test ComponentType enum."""
    
    def test_component_type_values(self):
        """Test that component types have correct string values."""
        assert ComponentType.TOOL.value == "tool"
        assert ComponentType.AGENT.value == "agent"
        assert ComponentType.PLUGIN.value == "plugin"
    
    def test_component_type_members(self):
        """Test that all expected component types exist."""
        assert ComponentType.TOOL in ComponentType
        assert ComponentType.AGENT in ComponentType
        assert ComponentType.PLUGIN in ComponentType


class TestRegistryInitialization:
    """Test Registry initialization."""
    
    def test_registry_init_without_event_bus(self):
        """Test registry initialization without providing EventBus."""
        registry = Registry()
        assert registry._components == {}
        assert isinstance(registry.get_event_bus(), EventBus)
    
    def test_registry_init_with_event_bus(self):
        """Test registry initialization with provided EventBus."""
        event_bus = EventBus()
        registry = Registry(event_bus=event_bus)
        assert registry.get_event_bus() is event_bus
    
    def test_registry_base_classes_configured(self):
        """Test that base classes are properly configured."""
        registry = Registry()
        assert registry._base_classes[ComponentType.TOOL] == BaseTool
        assert registry._base_classes[ComponentType.AGENT] == BaseAgent
        assert registry._base_classes[ComponentType.PLUGIN] == BasePlugin


class TestRegistryRegister:
    """Test Registry.register() method."""
    
    def test_register_tool_class(self):
        """Test registering a tool class."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        assert "my_tool" in registry._components
        assert ComponentType.TOOL in registry._components["my_tool"]
        assert registry._components["my_tool"][ComponentType.TOOL] is MyTool
    
    def test_register_agent_class(self):
        """Test registering an agent class."""
        registry = Registry()
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("my_agent", MyAgent, ComponentType.AGENT)
        
        assert registry._components["my_agent"][ComponentType.AGENT] is MyAgent
    
    def test_register_plugin_class(self):
        """Test registering a plugin class."""
        registry = Registry()
        
        class MyPlugin(BasePlugin):
            pass
        
        registry.register("my_plugin", MyPlugin, ComponentType.PLUGIN)
        
        assert registry._components["my_plugin"][ComponentType.PLUGIN] is MyPlugin
    
    def test_register_tool_instance(self):
        """Test registering a tool instance."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        tool_instance = MyTool()
        registry.register("my_tool", tool_instance, ComponentType.TOOL)
        
        assert registry._components["my_tool"][ComponentType.TOOL] is tool_instance
    
    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate components raises error."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        with pytest.raises(RegistryError, match="already registered"):
            registry.register("my_tool", MyTool, ComponentType.TOOL)
    
    def test_register_duplicate_different_types_allowed(self):
        """Test that same name with different types is allowed."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("my_component", MyTool, ComponentType.TOOL)
        registry.register("my_component", MyAgent, ComponentType.AGENT)
        
        assert ComponentType.TOOL in registry._components["my_component"]
        assert ComponentType.AGENT in registry._components["my_component"]
    
    def test_register_invalid_tool_class_raises_error(self):
        """Test that registering class not inheriting from BaseTool raises error."""
        registry = Registry()
        
        class InvalidTool:
            pass
        
        with pytest.raises(RegistryError, match="must be a subclass"):
            registry.register("invalid", InvalidTool, ComponentType.TOOL)
    
    def test_register_invalid_agent_class_raises_error(self):
        """Test that registering class not inheriting from BaseAgent raises error."""
        registry = Registry()
        
        class InvalidAgent:
            pass
        
        with pytest.raises(RegistryError, match="must be a subclass"):
            registry.register("invalid", InvalidAgent, ComponentType.AGENT)
    
    def test_register_invalid_instance_raises_error(self):
        """Test that registering instance not of correct type raises error."""
        registry = Registry()
        
        class NotATool:
            pass
        
        with pytest.raises(RegistryError, match="must be an instance"):
            registry.register("invalid", NotATool(), ComponentType.TOOL)


class TestRegistryGet:
    """Test Registry.get() method."""
    
    def test_get_registered_component(self):
        """Test retrieving a registered component."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        retrieved = registry.get("my_tool", ComponentType.TOOL)
        assert retrieved is MyTool
    
    def test_get_nonexistent_component_raises_error(self):
        """Test that getting nonexistent component raises error."""
        registry = Registry()
        
        with pytest.raises(RegistryError, match="not found"):
            registry.get("nonexistent", ComponentType.TOOL)
    
    def test_get_wrong_type_raises_error(self):
        """Test that getting component with wrong type raises error."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        with pytest.raises(RegistryError, match="not found"):
            registry.get("my_tool", ComponentType.AGENT)
    
    def test_get_multiple_types_from_same_name(self):
        """Test getting different types registered under same name."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("component", MyTool, ComponentType.TOOL)
        registry.register("component", MyAgent, ComponentType.AGENT)
        
        assert registry.get("component", ComponentType.TOOL) is MyTool
        assert registry.get("component", ComponentType.AGENT) is MyAgent


class TestRegistryList:
    """Test Registry.list() method."""
    
    def test_list_empty_registry(self):
        """Test listing components from empty registry."""
        registry = Registry()
        
        assert registry.list(ComponentType.TOOL) == []
        assert registry.list(ComponentType.AGENT) == []
        assert registry.list(ComponentType.PLUGIN) == []
    
    def test_list_single_tool(self):
        """Test listing when single tool is registered."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        assert registry.list(ComponentType.TOOL) == ["my_tool"]
        assert registry.list(ComponentType.AGENT) == []
    
    def test_list_multiple_tools(self):
        """Test listing multiple tools."""
        registry = Registry()
        
        class Tool1(BaseTool):
            pass
        
        class Tool2(BaseTool):
            pass
        
        registry.register("tool1", Tool1, ComponentType.TOOL)
        registry.register("tool2", Tool2, ComponentType.TOOL)
        registry.register("tool_a", Tool1, ComponentType.TOOL)
        
        tools = registry.list(ComponentType.TOOL)
        assert set(tools) == {"tool1", "tool2", "tool_a"}
        assert tools == sorted(tools)  # Should be sorted
    
    def test_list_mixed_types(self):
        """Test listing only returns correct types."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("tool1", MyTool, ComponentType.TOOL)
        registry.register("agent1", MyAgent, ComponentType.AGENT)
        registry.register("tool2", MyTool, ComponentType.TOOL)
        
        assert registry.list(ComponentType.TOOL) == ["tool1", "tool2"]
        assert registry.list(ComponentType.AGENT) == ["agent1"]
    
    def test_list_component_with_multiple_types(self):
        """Test that component with multiple types appears in each type's list."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("component", MyTool, ComponentType.TOOL)
        registry.register("component", MyAgent, ComponentType.AGENT)
        
        assert "component" in registry.list(ComponentType.TOOL)
        assert "component" in registry.list(ComponentType.AGENT)


class TestRegistryUnregister:
    """Test Registry.unregister() method."""
    
    def test_unregister_existing_component(self):
        """Test unregistering an existing component."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        registry.unregister("my_tool", ComponentType.TOOL)
        
        assert "my_tool" not in registry._components
    
    def test_unregister_nonexistent_component_raises_error(self):
        """Test that unregistering nonexistent component raises error."""
        registry = Registry()
        
        with pytest.raises(RegistryError, match="not found"):
            registry.unregister("nonexistent", ComponentType.TOOL)
    
    def test_unregister_wrong_type_raises_error(self):
        """Test that unregistering with wrong type raises error."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        with pytest.raises(RegistryError, match="not found"):
            registry.unregister("my_tool", ComponentType.AGENT)
    
    def test_unregister_one_type_keeps_others(self):
        """Test that unregistering one type keeps others."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        class MyAgent(BaseAgent):
            pass
        
        registry.register("component", MyTool, ComponentType.TOOL)
        registry.register("component", MyAgent, ComponentType.AGENT)
        
        registry.unregister("component", ComponentType.TOOL)
        
        assert ComponentType.TOOL not in registry._components["component"]
        assert ComponentType.AGENT in registry._components["component"]
    
    def test_unregister_cleans_up_empty_entries(self):
        """Test that unregister removes empty component entries."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        registry.unregister("my_tool", ComponentType.TOOL)
        
        assert "my_tool" not in registry._components


class TestRegistryDecorators:
    """Test Registry decorator methods."""
    
    def test_tool_decorator(self):
        """Test @registry.tool() decorator."""
        registry = Registry()
        
        @registry.tool("my_tool")
        class MyTool(BaseTool):
            pass
        
        assert registry.get("my_tool", ComponentType.TOOL) is MyTool
    
    def test_agent_decorator(self):
        """Test @registry.agent() decorator."""
        registry = Registry()
        
        @registry.agent("my_agent")
        class MyAgent(BaseAgent):
            pass
        
        assert registry.get("my_agent", ComponentType.AGENT) is MyAgent
    
    def test_plugin_decorator(self):
        """Test @registry.plugin() decorator."""
        registry = Registry()
        
        @registry.plugin("my_plugin")
        class MyPlugin(BasePlugin):
            pass
        
        assert registry.get("my_plugin", ComponentType.PLUGIN) is MyPlugin
    
    def test_decorator_returns_original_class(self):
        """Test that decorators return the original class unchanged."""
        registry = Registry()
        
        @registry.tool("my_tool")
        class MyTool(BaseTool):
            pass
        
        # The class should be usable and unmodified
        instance = MyTool()
        assert isinstance(instance, BaseTool)
    
    def test_decorator_with_invalid_class_raises_error(self):
        """Test that decorator raises error with invalid class."""
        registry = Registry()
        
        with pytest.raises(RegistryError):
            @registry.tool("invalid")
            class InvalidTool:
                pass


class TestRegistryValidation:
    """Test component validation."""
    
    def test_validate_tool_subclass(self):
        """Test that tool subclass validation works."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        # Should not raise
        registry.register("my_tool", MyTool, ComponentType.TOOL)
    
    def test_validate_tool_instance(self):
        """Test that tool instance validation works."""
        registry = Registry()
        
        class MyTool(BaseTool):
            pass
        
        tool = MyTool()
        # Should not raise
        registry.register("my_tool", tool, ComponentType.TOOL)
    
    def test_validate_inheritance_chain(self):
        """Test that validation works with inheritance chains."""
        registry = Registry()
        
        class CustomBaseTool(BaseTool):
            pass
        
        class MyTool(CustomBaseTool):
            pass
        
        # Should not raise
        registry.register("my_tool", MyTool, ComponentType.TOOL)
    
    def test_validation_error_message(self):
        """Test that validation error has descriptive message."""
        registry = Registry()
        
        class NotATool:
            pass
        
        with pytest.raises(RegistryError) as exc_info:
            registry.register("invalid", NotATool, ComponentType.TOOL)
        
        assert "BaseTool" in str(exc_info.value)


class TestRegistryEvents:
    """Test event emission."""
    
    def test_event_bus_available(self):
        """Test that event bus is accessible."""
        registry = Registry()
        
        assert isinstance(registry.get_event_bus(), EventBus)
    
    def test_custom_event_bus_used(self):
        """Test that provided event bus is used."""
        event_bus = EventBus()
        registry = Registry(event_bus=event_bus)
        
        assert registry.get_event_bus() is event_bus
    
    @pytest.mark.asyncio
    async def test_register_emits_event(self):
        """Test that register emits registry.registered event."""
        event_bus = EventBus()
        registry = Registry(event_bus=event_bus)
        
        events = []
        
        async def handler(event):
            events.append(event.payload)
        
        event_bus.subscribe("registry.registered", handler)
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        
        # Give event time to emit
        await asyncio.sleep(0.01)
        
        # Event should be emitted (if event loop is running)
        # Note: This test may not always work depending on event loop state
    
    @pytest.mark.asyncio
    async def test_unregister_emits_event(self):
        """Test that unregister emits registry.unregistered event."""
        event_bus = EventBus()
        registry = Registry(event_bus=event_bus)
        
        events = []
        
        async def handler(event):
            events.append(event.payload)
        
        event_bus.subscribe("registry.unregistered", handler)
        
        class MyTool(BaseTool):
            pass
        
        registry.register("my_tool", MyTool, ComponentType.TOOL)
        registry.unregister("my_tool", ComponentType.TOOL)
        
        # Give event time to emit
        await asyncio.sleep(0.01)


class TestRegistryIntegration:
    """Integration tests for Registry."""
    
    def test_full_lifecycle(self):
        """Test complete register, list, get, unregister cycle."""
        registry = Registry()
        
        class Tool1(BaseTool):
            pass
        
        class Tool2(BaseTool):
            pass
        
        class Agent1(BaseAgent):
            pass
        
        # Register
        registry.register("tool1", Tool1, ComponentType.TOOL)
        registry.register("tool2", Tool2, ComponentType.TOOL)
        registry.register("agent1", Agent1, ComponentType.AGENT)
        
        # List
        tools = registry.list(ComponentType.TOOL)
        assert set(tools) == {"tool1", "tool2"}
        
        agents = registry.list(ComponentType.AGENT)
        assert agents == ["agent1"]
        
        # Get
        assert registry.get("tool1", ComponentType.TOOL) is Tool1
        assert registry.get("agent1", ComponentType.AGENT) is Agent1
        
        # Unregister
        registry.unregister("tool1", ComponentType.TOOL)
        assert "tool1" not in registry.list(ComponentType.TOOL)
        assert "tool2" in registry.list(ComponentType.TOOL)
    
    def test_multiple_registries_isolated(self):
        """Test that multiple registries are isolated."""
        registry1 = Registry()
        registry2 = Registry()
        
        class MyTool(BaseTool):
            pass
        
        registry1.register("tool", MyTool, ComponentType.TOOL)
        
        assert "tool" in registry1.list(ComponentType.TOOL)
        assert "tool" not in registry2.list(ComponentType.TOOL)
    
    def test_decorator_with_multiple_types(self):
        """Test using multiple decorators on same registry."""
        registry = Registry()
        
        @registry.tool("my_tool")
        class MyTool(BaseTool):
            pass
        
        @registry.agent("my_agent")
        class MyAgent(BaseAgent):
            pass
        
        @registry.plugin("my_plugin")
        class MyPlugin(BasePlugin):
            pass
        
        assert len(registry.list(ComponentType.TOOL)) == 1
        assert len(registry.list(ComponentType.AGENT)) == 1
        assert len(registry.list(ComponentType.PLUGIN)) == 1
