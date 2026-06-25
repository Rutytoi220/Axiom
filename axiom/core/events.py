"""Event system for AXIOM - core pub/sub mechanism."""

from typing import Any, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Event:
    """Base event class for all system events."""
    
    event_type: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "data": self.data,
            "metadata": self.metadata,
        }


class EventBus:
    """Central event pub/sub system."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        self._event_history.append(event)
        
        # Maintain history size
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notify subscribers
        handlers = self._subscribers.get(event.event_type, [])
        handlers.extend(self._subscribers.get("*", []))  # Wildcard subscribers
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Log error but don't crash
                error_event = Event(
                    event_type="error.handler",
                    source="EventBus",
                    data={"error": str(e), "failed_handler": handler.__name__}
                )
                # Prevent infinite recursion
                if "error.handler" not in self._subscribers:
                    continue
    
    def get_history(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """Get event history."""
        if event_type:
            return [e for e in self._event_history if e.event_type == event_type][-limit:]
        return self._event_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
