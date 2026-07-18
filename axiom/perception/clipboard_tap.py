"""Clipboard Change Tap — RFC-003 Phase 2.

Monitors the system clipboard for text changes using a SHA-256 hash-based
diff approach. Only the *hash* of the previous content is retained in memory
— the raw text is evaluated and immediately released.

**Strictly opt-in:** the tap never spawns any thread unless
``config.monitor_clipboard`` is explicitly ``True``.

Security pipeline (applied in order)
-------------------------------------
1. Deny-list: if the active window matches a password manager, **drop**.
2. ``PrivacyScrubber.scrub_text``: redact API keys, tokens, PEM blocks.
3. IntentEngine: evaluate scrubbed text for actionable patterns.
4. EventBus: emit ``perception.clipboard.change`` with scrubbed text only.

Dependency: ``pyperclip`` (optional). If unavailable the tap logs a warning
and silently does nothing.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Optional

from axiom.config import get_config
from axiom.core.events import EventBus, Event
from axiom.perception.deny_list import DenyList
from axiom.perception.scrubber import PrivacyScrubber

logger = logging.getLogger(__name__)

# Polling interval. Clipboard is cheap to hash so 1s is fine.
_POLL_INTERVAL: float = 1.0


def _read_clipboard() -> Optional[str]:
    """Read current clipboard text. Returns None if pyperclip is unavailable."""
    try:
        import pyperclip  # type: ignore[import]
        return pyperclip.paste()
    except ImportError:
        logger.warning("ClipboardTap: pyperclip not installed. Run: pip install pyperclip")
        return None
    except Exception:
        return None


class ClipboardTap:
    """Hash-based clipboard monitor that emits scrubbed change events.

    The tap retains **only** a SHA-256 hash of the last-seen clipboard
    content. The raw text is never stored as an attribute — it is read,
    hashed, scrubbed, and discarded within a single stack frame.
    """

    def __init__(self, event_bus: EventBus, intent_engine=None):
        self.event_bus = event_bus
        self.intent_engine = intent_engine

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Store only the hash — never the raw content
        self._last_hash: Optional[str] = None

    def start(self) -> bool:
        """Start the background polling thread.

        Returns:
            True if started, False if the config guard is disabled or already running.
        """
        config = get_config()
        if not getattr(config, "monitor_clipboard", False):
            logger.info("ClipboardTap: disabled (config.monitor_clipboard=False). Not starting.")
            return False

        if self._thread and self._thread.is_alive():
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="axiom-clipboard-tap",
            daemon=True,
        )
        self._thread.start()
        logger.info("ClipboardTap: started (polling every %.1fs).", _POLL_INTERVAL)
        return True

    def stop(self) -> None:
        """Signal the polling thread to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=_POLL_INTERVAL + 1)
        logger.info("ClipboardTap: stopped.")

    def _poll_loop(self) -> None:
        """Main polling loop — runs in a daemon thread."""
        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception as exc:
                logger.debug("ClipboardTap: sampling error: %s", exc)
            self._stop_event.wait(_POLL_INTERVAL)

    def _sample(self) -> None:
        """Sample the clipboard and emit an event if the content has changed.

        Security contract
        -----------------
        * Raw text is only ever held as a local variable inside this method.
        * If the active window is on the deny-list we drop *before* reading
          the clipboard to avoid even touching potentially sensitive data.
        * The raw text is scrubbed before any further processing or emission.
        """
        # Import here so the window tap is an optional dependency
        try:
            from axiom.perception.window_tap import get_active_window
            window_title, process_name = get_active_window()
        except Exception:
            window_title, process_name = "", ""

        # SECURITY GATE 1: deny-list check (drop in memory, no log of content)
        if DenyList.is_blocked(process_name=process_name, window_title=window_title):
            return

        raw_text = _read_clipboard()
        if not raw_text or not isinstance(raw_text, str):
            return

        # SECURITY GATE 2: hash-based change detection
        content_hash = hashlib.sha256(raw_text.encode("utf-8", errors="replace")).hexdigest()
        if content_hash == self._last_hash:
            return  # Content unchanged — do nothing

        self._last_hash = content_hash

        # SECURITY GATE 3: scrub secrets before any processing
        scrubbed_text = PrivacyScrubber.scrub_text(raw_text)
        # raw_text is now eligible for GC — do not reference it again

        # Route to IntentEngine for context-aware suggestions
        intent_action = None
        if self.intent_engine:
            try:
                intent_action = self.intent_engine.evaluate_clipboard(scrubbed_text)
            except Exception as exc:
                logger.debug("ClipboardTap: IntentEngine error: %s", exc)

        # Emit EventBus event with SCRUBBED text only
        self.event_bus.publish(Event(
            event_type="perception.clipboard.change",
            source="ClipboardTap",
            data={
                "text": scrubbed_text,
                "length": len(scrubbed_text),
                "intent": intent_action,
                "process_name": process_name,
            }
        ))
        logger.debug(
            "ClipboardTap: clipboard change detected (scrubbed len=%d).",
            len(scrubbed_text)
        )
