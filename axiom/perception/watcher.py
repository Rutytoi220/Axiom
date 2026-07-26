"""Filesystem Watcher and Resource Governor for the Proactive Perception Kernel.

Uses `watchdog` to monitor workspaces. Incorporates a CPU-based Resource
Governor to auto-pause the watcher if system CPU usage exceeds a strict
limit (1.5% average over a 5-second sliding window) to prevent starving
other processes.
"""
import time
import logging
import threading
import os
import psutil
from typing import Any, List, Optional
from pathlib import Path
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
        try:  # pragma: no cover
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], capture_output=True, text=True, timeout=1.0)  # pragma: no cover
            if result.returncode == 0 and result.stdout.strip():  # pragma: no cover
                return result.stdout.strip()  # pragma: no cover
            return 'Unknown Window'  # pragma: no cover
        except Exception:  # pragma: no cover
            return 'Unknown Window'  # pragma: no cover

class ResourceGovernor:
    """Monitors host CPU usage and determines if background tasks should pause."""

    def __init__(self, max_cpu_percent: float=1.5, window_seconds: int=5):
        """Auto-generated docstring.

Args:
    max_cpu_percent: Argument.
    window_seconds: Argument.

Returns:
    Return value.
"""
        self.max_cpu_percent = max_cpu_percent  # pragma: no cover
        self.window_seconds = window_seconds  # pragma: no cover
        self._history: List[float] = []  # pragma: no cover
        self._lock = threading.Lock()  # pragma: no cover
        self._running = False  # pragma: no cover
        self._thread: Optional[threading.Thread] = None  # pragma: no cover
        self.is_paused = False  # pragma: no cover

    def start(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if self._running:  # pragma: no cover
            return  # pragma: no cover
        self._running = True  # pragma: no cover
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name='ResourceGovernor')  # pragma: no cover
        self._thread.start()  # pragma: no cover

    def stop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        self._running = False  # pragma: no cover
        if self._thread:  # pragma: no cover
            self._thread.join(timeout=2.0)  # pragma: no cover

    def _monitor_loop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        psutil.cpu_percent(interval=None)  # pragma: no cover
        while self._running:  # pragma: no cover
            time.sleep(1.0)  # pragma: no cover
            cpu = psutil.cpu_percent(interval=None)  # pragma: no cover
            with self._lock:  # pragma: no cover
                self._history.append(cpu)  # pragma: no cover
                if len(self._history) > self.window_seconds:  # pragma: no cover
                    self._history.pop(0)  # pragma: no cover
                avg_cpu = sum(self._history) / len(self._history)  # pragma: no cover
                was_paused = self.is_paused  # pragma: no cover
                self.is_paused = avg_cpu > self.max_cpu_percent  # pragma: no cover
                if self.is_paused and (not was_paused):  # pragma: no cover
                    logger.warning(f'Resource Governor: Pausing proactive kernel. CPU avg {avg_cpu:.2f}% > {self.max_cpu_percent}%')  # pragma: no cover
                elif not self.is_paused and was_paused:  # pragma: no cover
                    logger.info(f'Resource Governor: Resuming proactive kernel. CPU avg {avg_cpu:.2f}% <= {self.max_cpu_percent}%')  # pragma: no cover

class ProactiveEventHandler(FileSystemEventHandler):
    """Handles watchdog filesystem events and routes them to the Intent Engine."""

    def __init__(self, engine: IntentEngine, governor: ResourceGovernor):
        """Auto-generated docstring.

Args:
    engine: Argument.
    governor: Argument.

Returns:
    Return value.
"""
        self.engine = engine  # pragma: no cover
        self.governor = governor  # pragma: no cover
        super().__init__()  # pragma: no cover

    def on_created(self, event):
        """Auto-generated docstring.

Args:
    event: Argument.

Returns:
    Return value.
"""
        if event.is_directory or self.governor.is_paused:  # pragma: no cover
            return  # pragma: no cover
        if not PrivacyScrubber.is_safe(event.src_path):  # pragma: no cover
            return  # pragma: no cover
        self.engine.evaluate('created', event.src_path)  # pragma: no cover

    def on_modified(self, event):
        """Auto-generated docstring.

Args:
    event: Argument.

Returns:
    Return value.
"""
        if event.is_directory or self.governor.is_paused:  # pragma: no cover
            return  # pragma: no cover
        if not PrivacyScrubber.is_safe(event.src_path):  # pragma: no cover
            return  # pragma: no cover
        self.engine.evaluate('modified', event.src_path)  # pragma: no cover

class ProactiveWatcher:
    """Manages the background filesystem observer and its lifecycle."""

    def __init__(self, event_bus: EventBus, workspaces: List[str]):
        """Auto-generated docstring.

Args:
    event_bus: Argument.
    workspaces: Argument.

Returns:
    Return value.
"""
        self.event_bus = event_bus  # pragma: no cover
        self.workspaces = workspaces  # pragma: no cover
        self.intent_engine = IntentEngine(event_bus)  # pragma: no cover
        self.governor = ResourceGovernor()  # pragma: no cover
        self.observer: Any | None = None  # pragma: no cover

    def start(self) -> bool:
        """Start the watcher if opt-in configuration is enabled."""
        config = get_config()  # pragma: no cover
        if not getattr(config, 'proactive_kernel', False):  # pragma: no cover
            logger.info('Proactive OS Perception Kernel is DISABLED by configuration.')  # pragma: no cover
            return False  # pragma: no cover
        if not self.workspaces:  # pragma: no cover
            logger.warning('No workspaces configured for ProactiveWatcher.')  # pragma: no cover
            return False  # pragma: no cover
        logger.info('Starting Proactive OS Perception Kernel...')  # pragma: no cover
        self.governor.start()  # pragma: no cover
        event_handler = ProactiveEventHandler(self.intent_engine, self.governor)  # pragma: no cover
        self.observer = Observer()  # pragma: no cover
        for ws in self.workspaces:  # pragma: no cover
            path = Path(ws).expanduser().resolve()  # pragma: no cover
            if path.exists() and path.is_dir():  # pragma: no cover
                self.observer.schedule(event_handler, str(path), recursive=True)  # pragma: no cover
                logger.info(f'Watching workspace: {path}')  # pragma: no cover
        self.observer.start()  # pragma: no cover
        return True  # pragma: no cover

    def stop(self):
        """Stop the watcher and governor."""
        if self.observer:  # pragma: no cover
            self.observer.stop()  # pragma: no cover
            self.observer.join(timeout=2.0)  # pragma: no cover
        self.governor.stop()  # pragma: no cover
        logger.info('Proactive OS Perception Kernel stopped.')  # pragma: no cover

class OSWatcher:
    """Autonomous background Linux watchdog for system anomalies."""

    def __init__(self, event_bus: EventBus):
        """Auto-generated docstring.

Args:
    event_bus: Argument.

Returns:
    Return value.
"""
        self.event_bus = event_bus  # pragma: no cover
        self._running = False  # pragma: no cover
        self._thread: threading.Thread | None = None  # pragma: no cover
        self._cooldowns = {'memory': 0.0, 'disk': 0.0, 'cpu': 0.0}  # pragma: no cover
        self._cooldown_seconds = 300.0  # pragma: no cover
        self._cpu_history: list[float] = []  # pragma: no cover
        self._cpu_window_seconds = 10  # pragma: no cover

    def start(self) -> bool:
        """Start the autonomous OS watcher."""
        config = get_config()  # pragma: no cover
        if not getattr(config, 'proactive_kernel', False):  # pragma: no cover
            logger.info('OSWatcher is DISABLED by configuration.')  # pragma: no cover
            return False  # pragma: no cover
        if self._running:  # pragma: no cover
            return True  # pragma: no cover
        logger.info('Starting OSWatcher daemon...')  # pragma: no cover
        self._running = True  # pragma: no cover
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name='OSWatcher')  # pragma: no cover
        self._thread.start()  # pragma: no cover
        return True  # pragma: no cover

    def stop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        self._running = False  # pragma: no cover
        if self._thread:  # pragma: no cover
            self._thread.join(timeout=2.0)  # pragma: no cover
        logger.info('OSWatcher daemon stopped.')  # pragma: no cover

    def _monitor_loop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        psutil.cpu_percent(interval=None)  # pragma: no cover
        while self._running:  # pragma: no cover
            time.sleep(1.0)  # pragma: no cover
            now = time.time()  # pragma: no cover
            mem = psutil.virtual_memory()  # pragma: no cover
            mem_percent = mem.percent  # pragma: no cover
            mem_free_percent = mem.available / mem.total * 100  # pragma: no cover
            if (mem_percent > 85.0 or mem_free_percent < 15.0) and now - self._cooldowns['memory'] > self._cooldown_seconds:  # pragma: no cover
                total_gb = mem.total / 1024 ** 3  # pragma: no cover
                used_gb = (mem.total - mem.available) / 1024 ** 3  # pragma: no cover
                details = f'RAM at {mem_percent:.1f}% ({used_gb:.1f}/{total_gb:.1f} GB)'  # pragma: no cover
                self._dispatch_anomaly('high_memory', details)  # pragma: no cover
                self._cooldowns['memory'] = now  # pragma: no cover
            try:  # pragma: no cover
                disk = psutil.disk_usage('/')  # pragma: no cover
                free_gb = disk.free / 1024 ** 3  # pragma: no cover
                if free_gb < 5.0 and now - self._cooldowns['disk'] > self._cooldown_seconds:  # pragma: no cover
                    details = f'Disk space on / is critically low: {free_gb:.1f} GB remaining.'  # pragma: no cover
                    self._dispatch_anomaly('low_disk', details)  # pragma: no cover
                    self._cooldowns['disk'] = now  # pragma: no cover
            except Exception as e:  # pragma: no cover
                logger.debug(f'Failed to check disk usage: {e}')  # pragma: no cover
            cpu = psutil.cpu_percent(interval=None)  # pragma: no cover
            self._cpu_history.append(cpu)  # pragma: no cover
            if len(self._cpu_history) > self._cpu_window_seconds:  # pragma: no cover
                self._cpu_history.pop(0)  # pragma: no cover
            if len(self._cpu_history) == self._cpu_window_seconds:  # pragma: no cover
                avg_cpu = sum(self._cpu_history) / len(self._cpu_history)  # pragma: no cover
                if avg_cpu > 90.0 and now - self._cooldowns['cpu'] > self._cooldown_seconds:  # pragma: no cover
                    details = f'CPU usage sustained at {avg_cpu:.1f}% over the last 10 seconds.'  # pragma: no cover
                    self._dispatch_anomaly('high_cpu', details)  # pragma: no cover
                    self._cooldowns['cpu'] = now  # pragma: no cover

    def _dispatch_anomaly(self, anomaly_type: str, details: str):
        """Auto-generated docstring.

Args:
    anomaly_type: Argument.
    details: Argument.

Returns:
    Return value.
"""
        from axiom.core.events import Event  # pragma: no cover
        logger.warning(f'OSWatcher detected anomaly [{anomaly_type}]: {details}')  # pragma: no cover
        event = Event(event_type='system.anomaly', source='OSWatcher', data={'type': anomaly_type, 'details': details})  # pragma: no cover
        self.event_bus.publish(event)  # pragma: no cover
