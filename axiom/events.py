"""Event bus for managing event subscriptions and publishing."""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Callable, Dict, List, Set

logger = logging.getLogger(__name__)
_DEBUG_LOG = "/run/media/rutytoi/fast af/ChienGPT/.cursor/debug-e94045.log"


@dataclass
class Event:
    """Represents an event with metadata."""

    name: str
    payload: Any = None

    def __repr__(self) -> str:
        return f"Event(name='{self.name}', payload={self.payload})"


class EventBus:
    """Asyncio-native pub/sub event bus with sync compatibility helpers."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._published_events: Set[str] = set()
        self._sync_log: List[dict] = []

    def subscribe(self, event_name: str, handler: Callable) -> None:
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler).__name__}")
        self._subscriptions.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler: Callable) -> bool:
        if event_name not in self._subscriptions:
            removed = False
        else:
            try:
                self._subscriptions[event_name].remove(handler)
                removed = True
                if not self._subscriptions[event_name]:
                    del self._subscriptions[event_name]
            except ValueError:
                removed = False
        # #region agent log
        try:
            with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
                import json

                f.write(
                    json.dumps(
                        {
                            "sessionId": "e94045",
                            "hypothesisId": "D",
                            "location": "events.py:EventBus.unsubscribe",
                            "message": "unsubscribe_result",
                            "data": {
                                "removed": removed,
                                "publish_is_coroutine": inspect.iscoroutinefunction(self.publish),
                                "return_value": removed,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        return removed

    async def publish(self, event_name: str, payload: Any = None) -> None:
        async with self._lock:
            event = Event(name=event_name, payload=payload)
            self._published_events.add(event_name)
            handlers = list(self._matching_handlers(event_name))
        if handlers:
            await self._invoke_handlers(handlers, event)
        await self._emit_meta_event(event_name, payload)

    def publish_sync(self, event_name: str, data: Any = None) -> dict:
        entry = {"event": event_name, "data": data, "timestamp": time.time()}
        self._sync_log.append(entry)
        self._published_events.add(event_name)
        event = Event(name=event_name, payload=data)
        for handler in self._matching_handlers(event_name):
            try:
                if len(inspect.signature(handler).parameters) >= 2:
                    handler(event_name, data)
                else:
                    handler(event)
            except (TypeError, ValueError):
                handler(event)
            except Exception as exc:
                logger.error("Sync handler error: %s", exc, exc_info=True)
        return entry

    def log(self) -> list:
        return self._sync_log.copy()

    def clear_log(self) -> None:
        self._sync_log.clear()

    async def clear(self) -> None:
        async with self._lock:
            self._subscriptions.clear()
            self._published_events.clear()
        self._sync_log.clear()

    def get_subscriptions(self) -> Dict[str, int]:
        return {pattern: len(handlers) for pattern, handlers in self._subscriptions.items()}

    def get_published_events(self) -> Set[str]:
        return self._published_events.copy()

    def subscribers(self, event_name: str) -> list:
        return list(self._subscriptions.get(event_name, []))

    def _matching_handlers(self, event_name: str) -> List[Callable]:
        matching: List[Callable] = []
        for pattern, handlers in self._subscriptions.items():
            if pattern == event_name:
                matching.extend(handlers)
            elif "*" in pattern and fnmatch(event_name, pattern):
                matching.extend(handlers)
        return matching

    async def _invoke_handlers(self, handlers: List[Callable], event: Event) -> None:
        tasks = []
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                tasks.append(handler(event))
            else:
                tasks.append(asyncio.to_thread(handler, event))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error("Handler error: %s", result, exc_info=result)

    async def _emit_meta_event(self, event_name: str, payload: Any) -> None:
        meta_handlers = self._matching_handlers("bus.published")
        if not meta_handlers:
            return
        meta_event = Event(
            name="bus.published",
            payload={
                "event": event_name,
                "original_payload": payload,
                "total_published": len(self._published_events),
            },
        )
        await self._invoke_handlers(meta_handlers, meta_event)
