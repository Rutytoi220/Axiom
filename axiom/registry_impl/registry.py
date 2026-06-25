"""Component registry for AXIOM - manages tools, agents, and plugins."""

import asyncio
import logging
import inspect
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Type
from axiom.events import EventBus

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Enumeration of component types in the registry."""
    TOOL = "tool"
    AGENT = "agent"
    PLUGIN = "plugin"


class RegistryError(Exception):
    """Exception raised by Registry operations."""
    pass


class BaseTool:
    """Base class for tools."""
    pass


class BaseAgent:
    """Base class for agents."""
    pass


class BasePlugin:
    """Base class for plugins."""
    pass


class Registry:
    """
    Registry for storing and managing tools, agents, and plugins.
    
    Supports registration by name and type, with validation and event emission.
    Provides decorator-based registration for convenience.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize the registry.
        
        Args:
            event_bus: Optional EventBus for emitting registration events.
                      If not provided, a new EventBus is created.
        """
        self._components: Dict[str, Dict[ComponentType, Any]] = {}
        self._event_bus = event_bus or EventBus()
        self._base_classes = {
            ComponentType.TOOL: BaseTool,
            ComponentType.AGENT: BaseAgent,
            ComponentType.PLUGIN: BasePlugin,
        }
    
    def register(self, name: str, component: Any, component_type: ComponentType) -> None:
        """
        Register a component in the registry.
        
        Args:
            name: Unique name for the component
            component: The component instance or class to register
            component_type: Type of component (TOOL, AGENT, or PLUGIN)
        
        Raises:
            RegistryError: If component already exists or validation fails
        """
        # Validate component type
        self._validate_component(component, component_type)
        
        # Check for duplicates
        if name in self._components and component_type in self._components[name]:
            raise RegistryError(
                f"Component '{name}' of type {component_type.value} already registered"
            )
        
        # Store component
        if name not in self._components:
            self._components[name] = {}
        
        self._components[name][component_type] = component
        
        # Emit event asynchronously
        self._emit_event(
            "registry.registered",
            {"name": name, "type": component_type.value, "component": component}
        )
        
        logger.info(f"Registered {component_type.value} '{name}'")
    
    def get(self, name: str, component_type: ComponentType) -> Any:
        """
        Get a component from the registry.
        
        Args:
            name: Name of the component
            component_type: Type of component to retrieve
        
        Returns:
            The registered component
        
        Raises:
            RegistryError: If component not found
        """
        if name not in self._components or component_type not in self._components[name]:
            raise RegistryError(
                f"Component '{name}' of type {component_type.value} not found"
            )
        return self._components[name][component_type]
    
    def list(self, component_type: ComponentType) -> List[str]:
        """
        List all registered components of a given type.
        
        Args:
            component_type: Type of components to list
        
        Returns:
            List of component names
        """
        result = []
        for name, types in self._components.items():
            if component_type in types:
                result.append(name)
        return sorted(result)
    
    def unregister(self, name: str, component_type: ComponentType) -> None:
        """
        Unregister a component from the registry.
        
        Args:
            name: Name of the component
            component_type: Type of component to unregister
        
        Raises:
            RegistryError: If component not found
        """
        if name not in self._components or component_type not in self._components[name]:
            raise RegistryError(
                f"Component '{name}' of type {component_type.value} not found"
            )
        
        # Get component before deletion for event payload
        component = self._components[name][component_type]
        
        # Delete component
        del self._components[name][component_type]
        
        # Clean up empty entries
        if not self._components[name]:
            del self._components[name]
        
        # Emit event asynchronously
        self._emit_event(
            "registry.unregistered",
            {"name": name, "type": component_type.value, "component": component}
        )
        
        logger.info(f"Unregistered {component_type.value} '{name}'")
    
    def tool(self, name: str) -> Callable:
        """
        Decorator to register a tool.
        
        Usage:
            @registry.tool("my_tool")
            class MyTool(BaseTool):
                pass
        
        Args:
            name: Name to register the tool under
        
        Returns:
            Decorator function
        """
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.TOOL)
            return cls
        return decorator
    
    def agent(self, name: str) -> Callable:
        """
        Decorator to register an agent.
        
        Usage:
            @registry.agent("my_agent")
            class MyAgent(BaseAgent):
                pass
        
        Args:
            name: Name to register the agent under
        
        Returns:
            Decorator function
        """
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.AGENT)
            return cls
        return decorator
    
    def plugin(self, name: str) -> Callable:
        """
        Decorator to register a plugin.
        
        Usage:
            @registry.plugin("my_plugin")
            class MyPlugin(BasePlugin):
                pass
        
        Args:
            name: Name to register the plugin under
        
        Returns:
            Decorator function
        """
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.PLUGIN)
            return cls
        return decorator
    
    def _validate_component(self, component: Any, component_type: ComponentType) -> None:
        """
        Validate that component implements the correct base class.
        
        Args:
            component: Component to validate
            component_type: Expected type of component
        
        Raises:
            RegistryError: If validation fails
        """
        base_class = self._base_classes.get(component_type)
        if base_class is None:
            return
        
        # Check if component is a class or instance
        is_class = inspect.isclass(component)
        
        if is_class:
            # If it's a class, check if it's a subclass
            if not issubclass(component, base_class):
                raise RegistryError(
                    f"Component must be a subclass of {base_class.__name__}, "
                    f"got {component.__name__}"
                )
        else:
            # If it's an instance, check if it's an instance of the base class
            if not isinstance(component, base_class):
                raise RegistryError(
                    f"Component must be an instance of {base_class.__name__}, "
                    f"got {type(component).__name__}"
                )
    
    def _emit_event(self, event_name: str, payload: Any) -> None:
        """
        Emit an event via the EventBus.
        
        Handles the case where there may or may not be a running event loop.
        
        Args:
            event_name: Name of the event to emit
            payload: Event payload
        """
        try:
            loop = asyncio.get_running_loop()
            # If we have a running loop, schedule the publish as a task
            loop.create_task(self._event_bus.publish(event_name, payload))
        except RuntimeError:
            # No running loop - try to get the default loop
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # Loop exists but not running - just log that we can't emit
                    logger.debug(f"No running event loop, cannot emit {event_name}")
                    return
                loop.create_task(self._event_bus.publish(event_name, payload))
            except RuntimeError:
                # No loop at all - just log
                logger.debug(f"No event loop available, cannot emit {event_name}")
    
    def get_event_bus(self) -> EventBus:
        """
        Get the EventBus instance used by this registry.
        
        Returns:
            The EventBus instance
        """
        return self._event_bus
