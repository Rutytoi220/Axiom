"""AXIOM Desktop v3.0 — Application Entry-Point.

Usage
-----
CLI shortcut:   axiom-gui
Module run:     python3 -m axiom.gui.app
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_stylesheet(app: "QApplication") -> None:  # type: ignore[name-defined]
    qss_path = Path(__file__).parent / "styles" / "themes.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        logger.debug("Loaded QSS theme from %s", qss_path)
    else:
        logger.warning("Theme file not found: %s", qss_path)


def _build_tray(app: "QApplication", window: "MainWindow") -> "QSystemTrayIcon":  # type: ignore[name-defined]
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu
    from PySide6.QtGui import QIcon, QAction
    from axiom.config import get_config, AuthMode

    tray = QSystemTrayIcon(app)
    # Use a simple text-based fallback icon (Unicode circle in a pixmap)
    from PySide6.QtGui import QPixmap, QColor, QPainter
    pix = QPixmap(32, 32)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setPen(QColor("#10b981"))
    painter.setFont(app.font())
    painter.drawText(pix.rect(), 0x84, "A")  # Qt.AlignCenter
    painter.end()
    tray.setIcon(QIcon(pix))
    tray.setToolTip("AXIOM Desktop v3.0")

    menu = QMenu()

    show_action = QAction("Show / Hide Window", menu)
    show_action.triggered.connect(lambda: (
        window.show() if not window.isVisible() else window.hide()
    ))
    menu.addAction(show_action)

    menu.addSeparator()

    def _set_mode(mode: AuthMode) -> None:
        get_config().auth_mode = mode
        window._refresh_auth_ui()

    mode_autopilot = QAction("⚡ Mode: Autopilot", menu)
    mode_autopilot.triggered.connect(lambda: _set_mode(AuthMode.AUTOPILOT))
    menu.addAction(mode_autopilot)

    mode_basic = QAction("🛡️ Mode: Basic", menu)
    mode_basic.triggered.connect(lambda: _set_mode(AuthMode.BASIC))
    menu.addAction(mode_basic)

    mode_strict = QAction("🔒 Mode: Strict", menu)
    mode_strict.triggered.connect(lambda: _set_mode(AuthMode.STRICT))
    menu.addAction(mode_strict)

    menu.addSeparator()

    quit_action = QAction("Quit AXIOM", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.show()
    return tray


def run_gui() -> None:
    """Launch the AXIOM Desktop GUI (blocking call)."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
    except ImportError:
        print(
            "[AXIOM GUI] PySide6 is not installed.\n"
            "Run: pip install PySide6 qasync\n"
            "Then restart: axiom-gui"
        )
        sys.exit(1)

    try:
        import qasync
    except ImportError:
        print(
            "[AXIOM GUI] qasync is not installed.\n"
            "Run: pip install qasync\n"
            "Then restart: axiom-gui"
        )
        sys.exit(1)

    # --- QApplication ---
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("AXIOM Desktop")
    app.setApplicationVersion("3.0")
    app.setOrganizationName("AXIOM")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    _load_stylesheet(app)

    # --- AXIOM core wiring ---
    from axiom.gui.bridge import AxiomBridge
    from axiom.gui.main_window import MainWindow
    from axiom.core.events import EventBus
    from axiom.config import get_config

    bridge = AxiomBridge()

    # Attempt to wire up the real OrchestratorAgent if available
    try:
        from axiom.api.cli import CLI
        cli_instance = CLI()
        event_bus = cli_instance.engine.event_bus
        orchestrator = cli_instance.orchestrator
        bridge.set_orchestrator(orchestrator)
        logger.info("OrchestratorAgent attached to GUI bridge.")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        logger.warning("Could not initialise OrchestratorAgent: %s — running in demo mode.", exc)
        from axiom.core.events import EventBus
        event_bus = EventBus()

    bridge.set_event_bus(event_bus)

    window = MainWindow(bridge=bridge)

    # Update model label from config
    config = get_config()
    if hasattr(config, "ollama_model") and config.ollama_model:
        window.update_model_label(config.ollama_model)

    # --- System Tray ---
    tray = _build_tray(app, window)

    # --- qasync event loop ---
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    bridge.set_event_loop(loop)

    window.show()

    with loop:
        loop.run_forever()


def main() -> None:
    """Entrypoint for the ``axiom-gui`` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_gui()


if __name__ == "__main__":
    main()
