"""Backward-compatible re-export of the canonical EventBus.

``axiom.core.events`` is the single source of truth.  This module exists
so that existing ``from axiom.events import EventBus, Event`` imports
continue to work without changes.
"""

from axiom.core.events import EventBus, Event

__all__ = ["EventBus", "Event"]
