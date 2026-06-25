"""Registry for managing named objects and components."""

import asyncio
import inspect
import logging
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from axiom.events import EventBus

logger = logging.getLogger(__name__)
_DEBUG_LOG = "/run/media/rutytoi/fast af/ChienGPT/.cursor/debug-e94045.log"


class ComponentType(Enum):
    """Enumeration of component types in the registry."""

    TOOL = "tool"
    AGENT = "agent"
    PLUGIN = "plugin"


class RegistryError(Exception):
    """Raised when a registry operation fails."""

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
    """Registry for tools, agents, plugins, and legacy named objects."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._store: Dict[str, Any] = {}
        self._components: Dict[str, Dict[ComponentType, Any]] = {}
        self._event_bus = event_bus or EventBus()
        self._lock = threading.RLock()
        self._base_classes = {
            ComponentType.TOOL: BaseTool,
            ComponentType.AGENT: BaseAgent,
            ComponentType.PLUGIN: BasePlugin,
        }
        # #region agent log
        import json as _json
        import time as _time

        try:
            with open(_DEBUG_LOG, "a", encoding="utf-8") as _f:
                _f.write(
                    _json.dumps(
                        {
                            "sessionId": "e94045",
                            "hypothesisId": "B",
                            "location": "registry.py:Registry.__init__",
                            "message": "registry_capabilities",
                            "data": {"has_base_classes": True, "module": __name__},
                            "timestamp": int(_time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

    def register(self, name: str, component: Any, component_type: Optional[ComponentType] = None) -> None:
        if not name:
            raise RegistryError("Name cannot be empty")
        if component_type is None:
            with self._lock:
                if name in self._store:
                    raise RegistryError(f"Name '{name}' is already registered")
                self._store[name] = component
            return
        self._validate_component(component, component_type)
        with self._lock:
            if name in self._components and component_type in self._components[name]:
                raise RegistryError(
                    f"Component '{name}' of type {component_type.value} already registered"
                )
            self._components.setdefault(name, {})[component_type] = component
        self._emit_event(
            "registry.registered",
            {"name": name, "type": component_type.value, "component": component},
        )

    def get(self, name: str, component_type: Optional[ComponentType] = None) -> Any:
        with self._lock:
            if component_type is None:
                return self._store.get(name)
            if name not in self._components or component_type not in self._components[name]:
                raise RegistryError(f"Component '{name}' of type {component_type.value} not found")
            return self._components[name][component_type]

    def get_or_raise(self, name: str) -> Any:
        with self._lock:
            if name not in self._store:
                raise RegistryError(f"Name '{name}' is not registered")
            return self._store[name]

    def list(self, component_type: Optional[ComponentType] = None) -> List[str]:
        with self._lock:
            if component_type is None:
                return sorted(self._store.keys())
            return sorted(name for name, types in self._components.items() if component_type in types)

    def unregister(self, name: str, component_type: Optional[ComponentType] = None):
        if component_type is None:
            if name not in self._store:
                return False
            del self._store[name]
            self._components.pop(name, None)
            return True
        if name not in self._components or component_type not in self._components[name]:
            raise RegistryError(f"Component '{name}' of type {component_type.value} not found")
        component = self._components[name][component_type]
        del self._components[name][component_type]
        if not self._components[name]:
            del self._components[name]
        self._emit_event(
            "registry.unregistered",
            {"name": name, "type": component_type.value, "component": component},
        )

    def tool(self, name: str) -> Callable:
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.TOOL)
            return cls

        return decorator

    def agent(self, name: str) -> Callable:
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.AGENT)
            return cls

        return decorator

    def plugin(self, name: str) -> Callable:
        def decorator(cls: Type) -> Type:
            self.register(name, cls, ComponentType.PLUGIN)
            return cls

        return decorator

    def _validate_component(self, component: Any, component_type: ComponentType) -> None:
        base_class = self._base_classes.get(component_type)
        if base_class is None:
            return
        if inspect.isclass(component):
            if not issubclass(component, base_class):
                raise RegistryError(
                    f"Component must be a subclass of {base_class.__name__}, "
                    f"got {component.__name__}"
                )
        elif not isinstance(component, base_class):
            raise RegistryError(
                f"Component must be an instance of {base_class.__name__}, "
                f"got {type(component).__name__}"
            )

    def _emit_event(self, event_name: str, payload: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._event_bus.publish(event_name, payload))
        except RuntimeError:
            try:
                asyncio.run(self._event_bus.publish(event_name, payload))
            except RuntimeError:
                logger.debug("No event loop available for %s", event_name)

    def get_event_bus(self) -> EventBus:
        return self._event_bus

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._store

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
