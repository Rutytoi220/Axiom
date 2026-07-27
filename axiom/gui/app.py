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
    from axiom.config import get_config
    from PySide6.QtCore import Qt
    config = get_config()
    theme_mode = config.theme_mode.lower()
    
    is_dark = True
    if theme_mode == "light":
        is_dark = False
    elif theme_mode == "system":
        if hasattr(app.styleHints(), 'colorScheme'):
            is_dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark

    theme_file = "themes.qss" if is_dark else "light_theme.qss"
    qss_path = Path(__file__).parent / "styles" / theme_file
    
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
    
    # Use real icon if exists
    assets_dir = Path(__file__).parent / "assets"
    if (assets_dir / "logo.svg").exists():
        tray.setIcon(QIcon(str(assets_dir / "logo.svg")))
    elif (assets_dir / "logo.png").exists():
        tray.setIcon(QIcon(str(assets_dir / "logo.png")))
    else:
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
    
    # --- Single Instance IPC ---
    from PySide6.QtNetwork import QLocalSocket, QLocalServer
    socket = QLocalSocket()
    socket.connectToServer("axiom_desktop_v3")
    if socket.waitForConnected(500):
        socket.write(b"WAKEUP")
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)

    server = QLocalServer()
    server.removeServer("axiom_desktop_v3")
    server.listen("axiom_desktop_v3")
    app._ipc_server = server  # Prevent GC

    # Wayland/Desktop grouping (Qt 6.5+ automatically appends .desktop)
    app.setDesktopFileName("axiom")
    
    # Don't quit when closing the main window (keep tray running)
    app.setQuitOnLastWindowClosed(False)
    
    # Global App Icon
    from PySide6.QtGui import QIcon
    assets_dir = Path(__file__).parent / "assets"
    if (assets_dir / "logo.svg").exists():
        app.setWindowIcon(QIcon(str(assets_dir / "logo.svg")))
    elif (assets_dir / "logo.png").exists():
        app.setWindowIcon(QIcon(str(assets_dir / "logo.png")))
        
    _load_stylesheet(app)

    # --- AXIOM core wiring ---
    from axiom.gui.bridge import AxiomBridge
    from axiom.gui.main_window import MainWindow
    from axiom.config import get_config

    bridge = AxiomBridge()

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

    def _on_ipc_connection() -> None:
        sock = server.nextPendingConnection()
        def on_ready_read():
            data = sock.readAll().data()
            if b"WAKEUP" in data:
                window.show()
                window.raise_()
                window.activateWindow()
            sock.disconnectFromServer()
        sock.readyRead.connect(on_ready_read)
        # Handle case where data is already available
        if sock.bytesAvailable():
            on_ready_read()

    server.newConnection.connect(_on_ipc_connection)

    # Start IPC Client Connection
    bridge.initialize_client()

    with loop:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    """Entrypoint for the ``axiom-gui`` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_gui()


if __name__ == "__main__":
    main()
