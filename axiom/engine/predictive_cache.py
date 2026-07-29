"""Predictive Caching Pipeline.

Anticipates user actions by monitoring filesystem changes and pre-computing
LLM responses for the 3 most likely next questions in the background.
If the user asks a matching question, the cached answer is returned with 0ms TTFT.
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from axiom.core.events import EventBus, Event

logger = logging.getLogger(__name__)

# Basic in-memory cache to simulate Redis/SQLite
PREDICTIVE_CACHE: Dict[str, Tuple[str, float]] = {}
CACHE_TTL = 3600  # 1 hour


class DirectoryWatchdog(FileSystemEventHandler):
    """Listens for file opens/modifications in the active workspace."""

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        
        # Debounce multiple modification events
        self.event_bus.publish_sync(
            "workspace.file.modified", 
            {"filepath": event.src_path}
        )
        
    def on_opened(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
            
        self.event_bus.publish_sync(
            "workspace.file.opened", 
            {"filepath": event.src_path}
        )


class PredictiveComputeService:
    """Spawns background agents to pre-compute responses based on file activity."""
    
    def __init__(self, event_bus: EventBus, workspace_path: str):
        self.event_bus = event_bus
        self.workspace_path = workspace_path
        self._observer = None
        
        # Hook into EventBus
        self.event_bus.subscribe("workspace.file.opened", self._on_file_activity)
        self.event_bus.subscribe("workspace.file.modified", self._on_file_activity)

    def start(self):
        """Start the watchdog observer."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("PredictiveComputeService: 'watchdog' package not installed. FS monitoring disabled.")
            return

        self._observer = Observer()
        handler = DirectoryWatchdog(self.event_bus)
        
        if Path(self.workspace_path).exists():
            self._observer.schedule(handler, self.workspace_path, recursive=True)
            self._observer.start()
            logger.info(f"PredictiveComputeService: Watching {self.workspace_path} for pre-compute triggers.")
        else:
            logger.error(f"PredictiveComputeService: Workspace {self.workspace_path} does not exist.")

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def _on_file_activity(self, event: Event):
        filepath = event.data.get("filepath")
        if not filepath:
            return
            
        logger.info(f"PredictiveComputeService: Detected activity on {filepath}. Spawning ResearchAgent...")
        
        # Spawn a background task (fire and forget) to pre-compute
        loop = asyncio.get_event_loop()
        loop.create_task(self._precompute_file_context(filepath))
        
    async def _precompute_file_context(self, filepath: str):
        """Mock the generation of 3 likely questions and their answers."""
        # In production, this spawns a low-priority ResearchAgent targeting Ollama
        logger.debug(f"PredictiveComputeService: [Pre-Compute Worker] Reading {filepath}...")
        await asyncio.sleep(0.5) # Simulate IO
        
        # Predict questions based on file content (mock)
        questions = [
            f"What does {Path(filepath).name} do?",
            f"Can you explain the main classes in {Path(filepath).name}?",
            f"Find any security vulnerabilities in {Path(filepath).name}."
        ]
        
        logger.debug(f"PredictiveComputeService: [Pre-Compute Worker] Pre-computing {len(questions)} answers...")
        await asyncio.sleep(2.0) # Simulate LLM inference
        
        # Cache the answers
        now = time.time()
        for q in questions:
            answer = f"[PRE-COMPUTED (0ms TTFT)] The file {Path(filepath).name} is a core component. Everything looks structurally sound."
            PREDICTIVE_CACHE[q] = (answer, now)
            
        logger.info(f"PredictiveComputeService: Successfully cached 3 predictive responses for {Path(filepath).name}")

    def query_cache(self, user_prompt: str) -> Optional[str]:
        """Check if the user's prompt matches a pre-computed cache entry."""
        if user_prompt in PREDICTIVE_CACHE:
            answer, timestamp = PREDICTIVE_CACHE[user_prompt]
            if time.time() - timestamp < CACHE_TTL:
                logger.info(f"PredictiveComputeService: ⚡ CACHE HIT (0ms TTFT) for '{user_prompt}'")
                return answer
        return None
