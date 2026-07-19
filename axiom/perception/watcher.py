"""Filesystem Watcher and Resource Governor for the Proactive Perception Kernel.

Uses `watchdog` to monitor workspaces. Incorporates a CPU-based Resource
Governor to auto-pause the watcher if system CPU usage exceeds a strict
limit (1.5% average over a 5-second sliding window) to prevent starving
other processes.
"""

import time
import logging
import threading
from pathlib import Path
from typing import List, Optional
import psutil

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from axiom.core.events import EventBus
from axiom.perception.scrubber import PrivacyScrubber
from axiom.perception.intent_engine import IntentEngine
from axiom.config import get_config

import subprocess

logger = logging.getLogger(__name__)

class ActiveWindowContext:
    """Extracts active window metadata cross-platform using lightweight wrappers."""
    
    @staticmethod
    def get_active_window_title() -> str:
        """Fetch the active window title safely."""
        try:
            # Fallback to xdotool on Linux
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                timeout=1.0
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return "Unknown Window"
        except Exception:
            return "Unknown Window"


class ResourceGovernor:
    """Monitors host CPU usage and determines if background tasks should pause."""
    
    def __init__(self, max_cpu_percent: float = 1.5, window_seconds: int = 5):
        self.max_cpu_percent = max_cpu_percent
        self.window_seconds = window_seconds
        self._history: List[float] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.is_paused = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ResourceGovernor")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _monitor_loop(self):
        # Initialize psutil cpu percent
        psutil.cpu_percent(interval=None)
        
        while self._running:
            time.sleep(1.0)
            cpu = psutil.cpu_percent(interval=None)
            
            with self._lock:
                self._history.append(cpu)
                if len(self._history) > self.window_seconds:
                    self._history.pop(0)
                    
                avg_cpu = sum(self._history) / len(self._history)
                
                was_paused = self.is_paused
                self.is_paused = avg_cpu > self.max_cpu_percent
                
                if self.is_paused and not was_paused:
                    logger.warning(f"Resource Governor: Pausing proactive kernel. CPU avg {avg_cpu:.2f}% > {self.max_cpu_percent}%")
                elif not self.is_paused and was_paused:
                    logger.info(f"Resource Governor: Resuming proactive kernel. CPU avg {avg_cpu:.2f}% <= {self.max_cpu_percent}%")


class ProactiveEventHandler(FileSystemEventHandler):
    """Handles watchdog filesystem events and routes them to the Intent Engine."""

    def __init__(self, engine: IntentEngine, governor: ResourceGovernor):
        self.engine = engine
        self.governor = governor
        super().__init__()

    def on_created(self, event):
        if event.is_directory or self.governor.is_paused:
            return
        if not PrivacyScrubber.is_safe(event.src_path):
            return
        self.engine.evaluate("created", event.src_path)

    def on_modified(self, event):
        if event.is_directory or self.governor.is_paused:
            return
        if not PrivacyScrubber.is_safe(event.src_path):
            return
        self.engine.evaluate("modified", event.src_path)


class ProactiveWatcher:
    """Manages the background filesystem observer and its lifecycle."""
    
    def __init__(self, event_bus: EventBus, workspaces: List[str]):
        self.event_bus = event_bus
        self.workspaces = workspaces
        self.intent_engine = IntentEngine(event_bus)
        self.governor = ResourceGovernor()
        self.observer = None

    def start(self) -> bool:
        """Start the watcher if opt-in configuration is enabled."""
        config = get_config()
        if not getattr(config, "proactive_kernel", False):
            logger.info("Proactive OS Perception Kernel is DISABLED by configuration.")
            return False
            
        if not self.workspaces:
            logger.warning("No workspaces configured for ProactiveWatcher.")
            return False

        logger.info("Starting Proactive OS Perception Kernel...")
        self.governor.start()
        
        event_handler = ProactiveEventHandler(self.intent_engine, self.governor)
        self.observer = Observer()
        
        for ws in self.workspaces:
            path = Path(ws).expanduser().resolve()
            if path.exists() and path.is_dir():
                self.observer.schedule(event_handler, str(path), recursive=True)
                logger.info(f"Watching workspace: {path}")
            
        self.observer.start()
        return True

    def stop(self):
        """Stop the watcher and governor."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2.0)
        self.governor.stop()
        logger.info("Proactive OS Perception Kernel stopped.")
