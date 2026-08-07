import logging
import threading
from PySide6.QtCore import QObject, Signal
from pynput import keyboard

logger = logging.getLogger(__name__)

class HotkeySignaler(QObject):
    """QObject to bridge pynput events to the main Qt thread safely."""
    toggle_requested = Signal()

class GlobalHotkeyService:
    """Listens for a global hotkey and emits a Qt Signal."""

    def __init__(self, hotkey: str = '<ctrl>+<alt>+<space>'):
        self.hotkey = hotkey
        self.signaler = HotkeySignaler()
        self._listener = None
        self._running = False

    def start(self):
        """Starts the global hotkey listener in a background thread."""
        if self._running:
            return

        self._running = True
        
        def on_activate():
            logger.info("Global hotkey activated.")
            # Emit signal to notify Qt main thread safely
            self.signaler.toggle_requested.emit()

        def _run_listener():
            logger.info(f"Starting global hotkey listener for: {self.hotkey}")
            try:
                self._listener = keyboard.GlobalHotKeys({
                    self.hotkey: on_activate
                })
                self._listener.start()
                self._listener.join()
            except Exception as e:
                logger.error(f"Failed to start hotkey listener: {e}")

        # Start in a daemon thread so it doesn't block PySide6 teardown
        thread = threading.Thread(target=_run_listener, daemon=True)
        thread.start()

    def stop(self):
        """Stops the global hotkey listener."""
        self._running = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.error(f"Error stopping hotkey listener: {e}")
            self._listener = None
        logger.info("Global hotkey listener stopped.")
