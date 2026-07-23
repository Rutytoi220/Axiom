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


class OSWatcher:
    """Autonomous background Linux watchdog for system anomalies."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._running = False
        self._thread = None
        self._cooldowns = {"memory": 0.0, "disk": 0.0, "cpu": 0.0}
        self._cooldown_seconds = 300.0
        self._cpu_history = []
        self._cpu_window_seconds = 10

    def start(self) -> bool:
        """Start the autonomous OS watcher."""
        config = get_config()
        if not getattr(config, "proactive_kernel", False):
            logger.info("OSWatcher is DISABLED by configuration.")
            return False
            
        if self._running:
            return True
            
        logger.info("Starting OSWatcher daemon...")
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="OSWatcher")
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("OSWatcher daemon stopped.")

    def _monitor_loop(self):
        psutil.cpu_percent(interval=None)
        
        while self._running:
            time.sleep(1.0)
            now = time.time()
            
            # 1. Memory Check
            mem = psutil.virtual_memory()
            mem_percent = mem.percent
            mem_free_percent = (mem.available / mem.total) * 100
            
            if (mem_percent > 85.0 or mem_free_percent < 15.0) and (now - self._cooldowns["memory"] > self._cooldown_seconds):
                total_gb = mem.total / (1024**3)
                used_gb = (mem.total - mem.available) / (1024**3)
                details = f"RAM at {mem_percent:.1f}% ({used_gb:.1f}/{total_gb:.1f} GB)"
                self._dispatch_anomaly("high_memory", details)
                self._cooldowns["memory"] = now

            # 2. Disk Check
            try:
                disk = psutil.disk_usage("/")
                free_gb = disk.free / (1024**3)
                if free_gb < 5.0 and (now - self._cooldowns["disk"] > self._cooldown_seconds):
                    details = f"Disk space on / is critically low: {free_gb:.1f} GB remaining."
                    self._dispatch_anomaly("low_disk", details)
                    self._cooldowns["disk"] = now
            except Exception as e:
                logger.debug(f"Failed to check disk usage: {e}")

            # 3. CPU Check
            cpu = psutil.cpu_percent(interval=None)
            self._cpu_history.append(cpu)
            if len(self._cpu_history) > self._cpu_window_seconds:
                self._cpu_history.pop(0)
                
            if len(self._cpu_history) == self._cpu_window_seconds:
                avg_cpu = sum(self._cpu_history) / len(self._cpu_history)
                if avg_cpu > 90.0 and (now - self._cooldowns["cpu"] > self._cooldown_seconds):
                    details = f"CPU usage sustained at {avg_cpu:.1f}% over the last 10 seconds."
                    self._dispatch_anomaly("high_cpu", details)
                    self._cooldowns["cpu"] = now

    def _dispatch_anomaly(self, anomaly_type: str, details: str):
        from axiom.core.events import Event
        logger.warning(f"OSWatcher detected anomaly [{anomaly_type}]: {details}")
        event = Event(
            event_type="system.anomaly",
            source="OSWatcher",
            data={
                "type": anomaly_type,
                "details": details
            }
        )
        self.event_bus.publish(event)
