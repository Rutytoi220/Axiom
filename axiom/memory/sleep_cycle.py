"""Sleep Cycle Daemon for AXIOM.

Monitors EventBus activity and triggers memory compaction when idle.
"""

import time
import threading
import logging
import asyncio
import json
from typing import Any, Optional

from axiom.core.events import EventBus
from axiom.core.async_bridge import run_sync
from axiom.memory.compactor import MemoryCompactor

logger = logging.getLogger(__name__)

class SleepCycleDaemon:
    """Monitors activity and triggers maintenance sweeps when idle."""
    
    def __init__(self, bus: EventBus, memory_store: Any, llm: Optional[Any] = None, idle_threshold_minutes: float = 15.0):
        self._bus = bus
        self._memory_store = memory_store
        self._llm = llm
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
        """Execute the memory compaction sweep and episodic consolidation."""
        logger.info("System idle threshold reached. Triggering Sleep Cycle maintenance...")
        try:
            self._run_consolidation()
        except Exception as e:
            logger.error(f"Sleep Cycle consolidation failed: {e}", exc_info=True)

        try:
            db = self._memory_store.store._conn() if hasattr(self._memory_store, "store") else self._memory_store._conn()
            compactor = MemoryCompactor(db)
            
            # Since we are in a sync thread, use the async bridge
            result = run_sync(compactor.run_compaction())
            logger.info(f"Sleep Cycle compaction complete. Scanned: {result['scanned']}, Merged: {result['merged']}, Deleted: {result['deleted']}")
        except Exception as e:
            logger.error(f"Sleep Cycle compaction failed: {e}", exc_info=True)

    def _run_consolidation(self) -> None:
        """Compress the active conversation into a dense episodic memory and rotate the context window."""
        history = self._memory_store.get_conversation_history(limit=50)
        
        # Only consolidate if there's enough substance
        if len(history) < 4:
            return
            
        logger.info(f"Consolidating episodic memory for conversation ({len(history)} messages)...")
        
        # Prepare context for the summarizer
        transcript = []
        for msg in reversed(history): # get_conversation_history returns descending by default
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript.append(f"{role.upper()}: {content}")
            
        prompt = (
            "Summarize the following conversation into a tight JSON object with two keys:\n"
            "1. 'key_facts': A list of objective facts, tasks, or information discussed.\n"
            "2. 'user_preferences': Any preferences, habits, or stylistic choices the user revealed.\n\n"
            "Conversation:\n" + "\n".join(transcript) + "\n\n"
            "Respond ONLY with valid JSON."
        )
        
        if not self._llm:
            logger.warning("No LLM available for episodic consolidation.")
            return
            
        try:
            # We assume self._llm is an OllamaClient or similar with a generate or chat method
            # For this background task, we can use a small/fast model if the LLM allows overriding,
            # but for now we just use standard chat.
            messages = [{"role": "user", "content": prompt}]
            
            # If the client supports chat natively (e.g. OllamaClient)
            response = None
            if hasattr(self._llm, "chat_with_tools"):
                response_msg = self._llm.chat_with_tools(messages, [], timeout=60.0)
                response = response_msg.get("content", "") if isinstance(response_msg, dict) else str(response_msg)
            elif hasattr(self._llm, "chat"):
                # fallback generic interface
                response = self._llm.chat(messages, timeout=60.0)
                
            if response:
                # Clean markdown blocks if present
                if response.startswith("```json"):
                    response = response.replace("```json", "", 1)
                if response.endswith("```"):
                    response = response[:-3]
                response = response.strip()
                
                # Validate JSON
                summary_data = json.loads(response)
                
                # Push into semantic store
                summary_id = f"episodic_{int(time.time())}"
                self._memory_store.set(
                    key=summary_id, 
                    value=summary_data, 
                    tags=["episodic_summary"]
                )
                logger.info(f"Episodic memory '{summary_id}' consolidated successfully.")
                
                # Rotate active conversation to clear the active context window
                self._memory_store.create_conversation("Continued Session")
                logger.info("Rotated to new conversation 'Continued Session' to clear context window.")
                
        except Exception as e:
            logger.error(f"Failed to generate episodic summary: {e}", exc_info=True)
