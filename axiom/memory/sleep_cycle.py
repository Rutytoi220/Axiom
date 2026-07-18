"""Sleep Cycle Daemon for AXIOM.

Monitors EventBus activity and triggers memory compaction when idle.
"""

import time
import threading
import logging
import asyncio
from typing import Any

from axiom.core.events import EventBus
from axiom.core.async_bridge import run_sync
from axiom.memory.compactor import MemoryCompactor

logger = logging.getLogger(__name__)

class SleepCycleDaemon:
    """Monitors activity and triggers maintenance sweeps when idle."""
    
    def __init__(self, bus: EventBus, memory_store: Any, idle_threshold_minutes: float = 15.0):
        self._bus = bus
        self._memory_store = memory_store
        self._idle_threshold = idle_threshold_minutes * 60
        self._last_activity_time = time.time()
        self._is_running = False
        self._thread: threading.Thread | None = None
        self._last_compaction_time = 0.0
        
        # Subscribe to all events to track activity
        if hasattr(self._bus, "subscribe"):
            self._bus.subscribe("*", self._on_event)
            
    def _on_event(self, event: Any) -> None:
        """Update last activity time on any event."""
        self._last_activity_time = time.time()
        
    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._is_running:
            return
            
        self._is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="SleepCycleDaemon")
        self._thread.start()
        logger.info(f"SleepCycleDaemon started (idle threshold: {self._idle_threshold}s)")
        
    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            
    def _monitor_loop(self) -> None:
        """Check for idle periods and trigger compaction."""
        while self._is_running:
            time.sleep(60)  # Check every minute
            
            now = time.time()
            idle_duration = now - self._last_activity_time
            time_since_compaction = now - self._last_compaction_time
            
            # If idle long enough, and haven't compacted during this specific idle period
            if idle_duration > self._idle_threshold and time_since_compaction > self._idle_threshold:
                self._run_maintenance()
                self._last_compaction_time = time.time()
                
    def _run_maintenance(self) -> None:
        """Execute the memory compaction sweep."""
        logger.info("System idle threshold reached. Triggering Sleep Cycle memory compaction...")
        try:
            db = self._memory_store.store._conn() if hasattr(self._memory_store, "store") else self._memory_store._conn()
            compactor = MemoryCompactor(db)
            
            # Since we are in a sync thread, use the async bridge
            result = run_sync(compactor.run_compaction())
            logger.info(f"Sleep Cycle complete. Scanned: {result['scanned']}, Merged: {result['merged']}, Deleted: {result['deleted']}")
        except Exception as e:
            logger.error(f"Sleep Cycle compaction failed: {e}", exc_info=True)
