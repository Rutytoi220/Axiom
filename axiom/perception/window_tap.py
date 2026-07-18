"""Active Window Focus Tap — RFC-003 Phase 2.

Polls the currently focused window every 2 seconds and emits
``perception.window.focus`` events on the EventBus when the active
application changes.

**Strictly opt-in:** the tap never spawns any thread unless
``config.monitor_window_focus`` is explicitly ``True``.

Cross-platform strategy
-----------------------
* Linux  — ``xdotool getactivewindow getwindowname`` / ``/proc/<pid>/comm``
* macOS  — ``AppKit.NSWorkspace`` (if pyobjc is installed)
* Windows — ``win32gui.GetForegroundWindow`` (if pywin32 is installed)

All three paths degrade gracefully: if the native library is unavailable
the tap logs a one-time warning and returns ``("unknown", "unknown")``
rather than raising.
"""

from __future__ import annotations

import hashlib
import logging
import platform
import subprocess
import threading
import time
from typing import Optional, Tuple

from axiom.config import get_config
from axiom.core.events import EventBus, Event
from axiom.perception.deny_list import DenyList

logger = logging.getLogger(__name__)

# Sampling interval in seconds
_POLL_INTERVAL: float = 2.0


def _get_active_window_linux() -> Tuple[str, str]:
    """Return (window_title, process_name) on Linux via xdotool.

    Falls back to ("unknown", "unknown") if xdotool is not installed.
    """
    try:
        win_id = subprocess.check_output(
            ["xdotool", "getactivewindow"],
            timeout=1, stderr=subprocess.DEVNULL
        ).decode().strip()
        title = subprocess.check_output(
            ["xdotool", "getwindowname", win_id],
            timeout=1, stderr=subprocess.DEVNULL
        ).decode().strip()
        pid = subprocess.check_output(
            ["xdotool", "getwindowpid", win_id],
            timeout=1, stderr=subprocess.DEVNULL
        ).decode().strip()
        try:
            with open(f"/proc/{pid}/comm") as fh:
                process_name = fh.read().strip()
        except (FileNotFoundError, ValueError):
            process_name = "unknown"
        return title, process_name
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown", "unknown"
    except Exception:
        return "unknown", "unknown"


def _get_active_window_macos() -> Tuple[str, str]:
    """Return (window_title, process_name) on macOS via AppKit."""
    try:
        from AppKit import NSWorkspace  # type: ignore[import]
        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.activeApplication()
        process_name = active_app.get("NSApplicationName", "unknown")
        title = active_app.get("NSApplicationName", "unknown")  # Full title needs Accessibility API
        return title, process_name
    except ImportError:
        logger.warning("WindowFocusTap: AppKit not available on macOS. Install pyobjc.")
        return "unknown", "unknown"
    except Exception:
        return "unknown", "unknown"


def _get_active_window_windows() -> Tuple[str, str]:
    """Return (window_title, process_name) on Windows via win32gui."""
    try:
        import win32gui  # type: ignore[import]
        import win32process  # type: ignore[import]
        import psutil
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = psutil.Process(pid).name()
        return title, process_name
    except ImportError:
        logger.warning("WindowFocusTap: pywin32 not available. Install pywin32.")
        return "unknown", "unknown"
    except Exception:
        return "unknown", "unknown"


def get_active_window() -> Tuple[str, str]:
    """Cross-platform active-window sampler.

    Returns:
        ``(window_title, process_name)`` tuple.
    """
    os_name = platform.system()
    if os_name == "Linux":
        return _get_active_window_linux()
    elif os_name == "Darwin":
        return _get_active_window_macos()
    elif os_name == "Windows":
        return _get_active_window_windows()
    return "unknown", "unknown"


class WindowFocusTap:
    """Monitors active window focus and emits context-change events.

    Attributes:
        event_bus: The AXIOM EventBus to publish events onto.
    """

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_hash: Optional[str] = None

    def start(self) -> bool:
        """Start the background polling thread.

        Returns:
            True if the tap was started, False if the config guard is disabled
            or the tap is already running.
        """
        config = get_config()
        if not getattr(config, "monitor_window_focus", False):
            logger.info("WindowFocusTap: disabled (config.monitor_window_focus=False). Not starting.")
            return False

        if self._thread and self._thread.is_alive():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="axiom-window-tap",
            daemon=True,
        )
        self._thread.start()
        logger.info("WindowFocusTap: started (polling every %.1fs).", _POLL_INTERVAL)
        return True

    def stop(self) -> None:
        """Signal the polling thread to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=_POLL_INTERVAL + 1)
        logger.info("WindowFocusTap: stopped.")

    def _poll_loop(self) -> None:
        """Main polling loop — runs in a daemon thread."""
        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception as exc:
                logger.debug("WindowFocusTap: sampling error: %s", exc)
            self._stop_event.wait(_POLL_INTERVAL)

    def _sample(self) -> None:
        """Sample the active window and emit an event if it changed."""
        window_title, process_name = get_active_window()

        # ---------- SECURITY: deny-list check (in-memory drop) ----------
        if DenyList.is_blocked(process_name=process_name, window_title=window_title):
            return  # Event irrecoverably dropped — no log of the content

        # Only emit when the active window actually changes
        fingerprint = hashlib.sha256(
            f"{window_title}|{process_name}".encode()
        ).hexdigest()
        if fingerprint == self._last_hash:
            return

        self._last_hash = fingerprint
        self.event_bus.publish(Event(
            event_type="perception.window.focus",
            source="WindowFocusTap",
            data={
                "window_title": window_title,
                "process_name": process_name,
            }
        ))
        logger.debug(
            "WindowFocusTap: focus change → process=%s title=%r",
            process_name, window_title[:80]
        )
