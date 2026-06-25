"""Event bus for AXIOM - asyncio-native pub/sub system."""

import asyncio
import logging
import inspect
from dataclasses import dataclass
from typing import Dict, List, Callable, Any, Optional, Set
from fnmatch import fnmatch

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents an event with metadata."""
    name: str
    payload: Any = None
    
    def __repr__(self) -> str:
        return f"Event(name='{self.name}', payload={self.payload})"


class EventBus:
    """
    Asyncio-native pub/sub event bus with wildcard support.
    
    Features:
    - Subscribe handlers to events (sync and async)
    - Publish events with concurrent handler execution
    - Wildcard subscriptions (e.g., "agent.*")
    - Meta-events for debugging/logging
    - Thread-safe for coroutine-based concurrency
    """
    
    def __init__(self):
        """Initialize the event bus with empty subscriptions."""
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._published_events: Set[str] = set()
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event.
        
        Args:
            event_name: Event name to subscribe to. Supports wildcards (e.g., "agent.*")
            handler: Callable (sync or async) to invoke when event is published.
                    Handler will receive Event object as argument.
        
        Multiple handlers can subscribe to the same event.
        Wildcards use fnmatch patterns.
        """
        if event_name not in self._subscriptions:
            self._subscriptions[event_name] = []
        
        self._subscriptions[event_name].append(handler)
        logger.debug(f"Subscribed {handler.__name__ if hasattr(handler, '__name__') else handler} to '{event_name}'")
    
    def unsubscribe(self, event_name: str, handler: Callable) -> bool:
        """
        Unsubscribe a handler from an event.
        
        Args:
            event_name: Event name to unsubscribe from
            handler: Handler to remove
        
        Returns:
            True if handler was removed, False if not found
        """
        if event_name not in self._subscriptions:
            return False
        
        try:
            self._subscriptions[event_name].remove(handler)
            logger.debug(f"Unsubscribed {handler.__name__ if hasattr(handler, '__name__') else handler} from '{event_name}'")
            
            # Clean up empty subscription lists
            if not self._subscriptions[event_name]:
                del self._subscriptions[event_name]
            
            return True
        except ValueError:
            return False
    
    async def publish(self, event_name: str, payload: Any = None) -> None:
        """
        Publish an event and invoke all matching handlers concurrently.
        
        Handlers are matched by exact name or wildcard pattern.
        After calling handlers, emits "bus.published" meta-event.
        
        Args:
            event_name: Name of the event to publish
            payload: Payload to pass to handlers
        
        Raises:
            Any exceptions from handlers are logged but not propagated.
        """
        async with self._lock:
            event = Event(name=event_name, payload=payload)
            self._published_events.add(event_name)
            
            # Collect matching handlers
            matching_handlers = await self._get_matching_handlers(event_name)
            
            if matching_handlers:
                logger.debug(f"Publishing '{event_name}' to {len(matching_handlers)} handler(s)")
                
                # Call all handlers concurrently
                await self._invoke_handlers(matching_handlers, event)
            else:
                logger.debug(f"Published '{event_name}' with no subscribers")
        
        # Emit meta-event after publishing (outside lock to avoid deadlock)
        await self._emit_meta_event(event_name, payload)
    
    async def _get_matching_handlers(self, event_name: str) -> List[Callable]:
        """
        Get all handlers that match the event name.
        
        Matches both exact names and wildcard patterns.
        
        Args:
            event_name: Event name to match
        
        Returns:
            List of matching handlers
        """
        matching = []
        
        for pattern, handlers in self._subscriptions.items():
            # Exact match
            if pattern == event_name:
                matching.extend(handlers)
            # Wildcard match
            elif '*' in pattern and fnmatch(event_name, pattern):
                matching.extend(handlers)
        
        return matching
    
    async def _invoke_handlers(self, handlers: List[Callable], event: Event) -> None:
        """
        Invoke all handlers concurrently.
        
        Handles both sync and async functions.
        Exceptions are logged but don't stop other handlers.
        
        Args:
            handlers: List of handlers to invoke
            event: Event to pass to handlers
        """
        tasks = []
        
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    # Async handler - create task
                    tasks.append(self._call_async_handler(handler, event))
                else:
                    # Sync handler - wrap in coroutine
                    tasks.append(self._call_sync_handler(handler, event))
            except Exception as e:
                logger.error(f"Error preparing handler {handler.__name__}: {e}", exc_info=True)
        
        if tasks:
            # Execute all handlers concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions
            for result, handler in zip(results, handlers):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error in handler {handler.__name__ if hasattr(handler, '__name__') else handler}: {result}",
                        exc_info=result
                    )
    
    async def _call_async_handler(self, handler: Callable, event: Event) -> None:
        """Call an async handler with the event."""
        await handler(event)
    
    async def _call_sync_handler(self, handler: Callable, event: Event) -> None:
        """Call a sync handler with the event."""
        handler(event)
    
    async def _emit_meta_event(self, event_name: str, payload: Any) -> None:
        """
        Emit a meta-event for debugging/logging.
        
        Emits "bus.published" with metadata about the published event.
        Uses separate lock handling to avoid recursion issues.
        
        Args:
            event_name: Name of the published event
            payload: Payload of the published event
        """
        meta_payload = {
            "event": event_name,
            "original_payload": payload,
            "total_published": len(self._published_events)
        }
        
        # Get meta-event handlers without using lock (already held)
        meta_handlers = []
        
        for pattern, handlers in self._subscriptions.items():
            if pattern == "bus.published":
                meta_handlers.extend(handlers)
            elif '*' in pattern and fnmatch("bus.published", pattern):
                meta_handlers.extend(handlers)
        
        if meta_handlers:
            meta_event = Event(name="bus.published", payload=meta_payload)
            await self._invoke_handlers(meta_handlers, meta_event)
    
    def get_subscriptions(self) -> Dict[str, int]:
        """
        Get subscription counts for debugging.
        
        Returns:
            Dict mapping event patterns to handler counts
        """
        return {pattern: len(handlers) for pattern, handlers in self._subscriptions.items()}
    
    def get_published_events(self) -> Set[str]:
        """
        Get set of all published event names.
        
        Returns:
            Set of event names that have been published
        """
        return self._published_events.copy()
    
    async def clear(self) -> None:
        """Clear all subscriptions and reset state."""
        async with self._lock:
            self._subscriptions.clear()
            self._published_events.clear()
        logger.debug("Event bus cleared")
