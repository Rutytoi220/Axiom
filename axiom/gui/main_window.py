"""AXIOM Desktop v3.0 — Main Application Window.

Implements the modular layout:
  - Toolbar (model badge, auth mode selector, expert toggle)
  - Central chat viewport with streaming message bubbles
  - Collapsible right dock: System Telemetry & Expert Logs
  - Bottom control bar: multiline input + send button
  - Status bar: active model + mode badge
"""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize, Slot, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from axiom.config import get_config, AuthMode
from axiom.gui.widgets.chat_bubble import MessageBubble, ToolPill

if TYPE_CHECKING:
    from axiom.gui.bridge import AxiomBridge

logger = logging.getLogger(__name__)

_AUTH_LABELS = {
    AuthMode.BASIC: "🛡️ BASIC",
    AuthMode.AUTOPILOT: "⚡ AUTOPILOT",
    AuthMode.STRICT: "🔒 STRICT",
}
_AUTH_COLORS = {
    AuthMode.BASIC: "#f59e0b",
    AuthMode.AUTOPILOT: "#10b981",
    AuthMode.STRICT: "#ef4444",
}

class ChatInputEdit(QTextEdit):
    """Custom input edit that sends on Enter and adds a newline on Shift+Enter."""
    
    send_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter: normal newline
                super().keyPressEvent(event)
            else:
                # Enter: send message
                self.send_requested.emit()
                event.accept()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    """AXIOM Desktop v3.0 main application window."""

    def __init__(self, bridge: "AxiomBridge", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._streaming_bubble: MessageBubble | None = None
        self._streaming_text: str = ""

        self.setWindowTitle("AXIOM Desktop v3.0")
        self.setMinimumSize(900, 640)
        self.resize(1280, 800)

        self._build_toolbar()
        self._build_central_widget()
        self._build_expert_dock()
        self._build_bottom_bar()
        self._build_status_bar()
        self._connect_bridge()
        self._refresh_auth_ui()
        
        # Initial Welcome Message
        self._add_bubble("assistant", "⚡ AXIOM Desktop v3.0 Online — Select a mode above or type a prompt below to begin.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        # AXIOM brand label
        brand = QLabel("  AXIOM")
        brand.setStyleSheet("font-weight:800; font-size:15px; color:#10b981; letter-spacing:0.06em;")
        tb.addWidget(brand)

        spacer1 = QWidget()
        spacer1.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer1.setStyleSheet("background: transparent;")
        tb.addWidget(spacer1)

        # ---- Auth Mode Buttons ----
        auth_frame = QFrame()
        auth_layout = QHBoxLayout(auth_frame)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        auth_layout.setSpacing(4)

        self._auth_group = QButtonGroup(self)
        self._auth_group.setExclusive(True)

        self._btn_basic = QPushButton("🛡️ BASIC")
        self._btn_basic.setObjectName("authBasicBtn")
        self._btn_basic.setCheckable(True)

        self._btn_autopilot = QPushButton("⚡ AUTOPILOT")
        self._btn_autopilot.setObjectName("authAutopilotBtn")
        self._btn_autopilot.setCheckable(True)

        self._btn_strict = QPushButton("🔒 STRICT")
        self._btn_strict.setObjectName("authStrictBtn")
        self._btn_strict.setCheckable(True)

        for btn in (self._btn_basic, self._btn_autopilot, self._btn_strict):
            self._auth_group.addButton(btn)
            auth_layout.addWidget(btn)

        self._btn_basic.clicked.connect(lambda: self._set_auth_mode(AuthMode.BASIC))
        self._btn_autopilot.clicked.connect(lambda: self._set_auth_mode(AuthMode.AUTOPILOT))
        self._btn_strict.clicked.connect(lambda: self._set_auth_mode(AuthMode.STRICT))

        tb.addWidget(auth_frame)

        tb.addSeparator()

        # ---- Expert Mode Toggle ----
        self._expert_btn = QPushButton("⚙️ Expert Mode: OFF")
        self._expert_btn.setObjectName("expertToggleBtn")
        self._expert_btn.setCheckable(True)
        self._expert_btn.clicked.connect(self._toggle_expert_dock)
        tb.addWidget(self._expert_btn)

        tb.addSeparator()

        # ---- Model badge ----
        self._model_label = QLabel("Model: —")
        self._model_label.setObjectName("modelLabel")
        tb.addWidget(self._model_label)

        tb.addWidget(QWidget())  # right padding

    def _build_central_widget(self) -> None:
        """Scrollable chat viewport with message bubbles."""
        container = QWidget()
        self.setCentralWidget(container)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(24, 20, 24, 20)
        self._chat_layout.setSpacing(12)
        self._chat_layout.addStretch()  # pushes bubbles to bottom

        self._scroll.setWidget(self._chat_container)
        outer.addWidget(self._scroll)

    def _build_expert_dock(self) -> None:
        """Hidden right dock panel for system telemetry & expert logs."""
        self._dock = QDockWidget("System Telemetry & Swarm Logs", self)
        self._dock.setObjectName("expertDock")
        self._dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self._dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self._dock.setMinimumWidth(320)
        self._dock.hide()
        self._dock.visibilityChanged.connect(self._on_dock_visibility_changed)

        dock_inner = QWidget()
        dock_layout = QVBoxLayout(dock_inner)
        dock_layout.setContentsMargins(12, 8, 12, 8)
        dock_layout.setSpacing(8)

        # Telemetry badges row
        tele_row = QHBoxLayout()
        self._tele_model = QLabel("Model: —")
        self._tele_model.setStyleSheet("color:#10b981; font-size:11px; font-weight:600;")
        self._tele_mode = QLabel("Mode: BASIC")
        self._tele_mode.setStyleSheet("color:#f59e0b; font-size:11px; font-weight:600;")
        self._tele_cpu = QLabel("CPU: —")
        self._tele_cpu.setStyleSheet("color:#a0a0b0; font-size:11px;")
        self._tele_ram = QLabel("RAM: —")
        self._tele_ram.setStyleSheet("color:#a0a0b0; font-size:11px;")
        for w in (self._tele_model, self._tele_mode, self._tele_cpu, self._tele_ram):
            tele_row.addWidget(w)
        tele_row.addStretch()
        dock_layout.addLayout(tele_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2e2e36;")
        dock_layout.addWidget(sep)

        # Live log text area
        self._expert_log = QTextEdit()
        self._expert_log.setObjectName("expertLog")
        self._expert_log.setReadOnly(True)
        self._expert_log.setPlaceholderText("EventBus stream and tool logs appear here…")
        dock_layout.addWidget(self._expert_log)

        self._dock.setWidget(dock_inner)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)

    def _build_bottom_bar(self) -> None:
        """Bottom control bar: multiline input + send button."""
        bar = QWidget()
        bar.setStyleSheet("background:#1a1a1f; border-top:1px solid #2e2e36;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)

        self._input = ChatInputEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Ask AXIOM anything… (Enter to send, Shift+Enter for new line)")
        self._input.setMaximumHeight(130)
        self._input.setMinimumHeight(60)
        bar_layout.addWidget(self._input)

        send_btn = QPushButton("Send ↑")
        send_btn.setObjectName("sendBtn")
        send_btn.setFixedSize(90, 48)
        send_btn.clicked.connect(self._on_send)
        bar_layout.addWidget(send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Connect the custom signal
        self._input.send_requested.connect(self._on_send)

        # Slot bar into the main layout below central widget
        main_layout = self.centralWidget().layout()
        main_layout.addWidget(bar)
        main_layout.setStretch(0, 9)
        main_layout.setStretch(1, 0)

    def _build_status_bar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._status_mode = QLabel()
        self._status_model = QLabel()
        sb.addWidget(self._status_mode)
        sb.addPermanentWidget(self._status_model)

    # ------------------------------------------------------------------
    # Bridge signal wiring
    # ------------------------------------------------------------------

    def _connect_bridge(self) -> None:
        self._bridge.token_received.connect(self._on_token)
        self._bridge.tool_status_changed.connect(self._on_tool_status)
        self._bridge.telemetry_updated.connect(self._on_telemetry)
        self._bridge.response_finished.connect(self._on_response_finished)
        self._bridge.error_occurred.connect(self._on_error)

    # ------------------------------------------------------------------
    # Qt Slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._add_bubble("user", text)
        # Start a new streaming assistant bubble
        self._streaming_text = ""
        self._streaming_bubble = self._add_bubble("assistant", "")
        self._bridge.submit_task(text)

    @Slot(str)
    def _on_token(self, token: str) -> None:
        if self._streaming_bubble:
            self._streaming_text += token
            self._streaming_bubble.set_text(html.escape(self._streaming_text))
            self._scroll_to_bottom()

    @Slot(str, str)
    def _on_tool_status(self, tool_id: str, status: str) -> None:
        pill = ToolPill(tool_id, status)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, pill)
        if self._dock.isVisible():
            self._expert_log.append(f"[TOOL] {tool_id}: {status}")
        self._scroll_to_bottom()

    @Slot(dict)
    def _on_telemetry(self, data: dict) -> None:
        model = data.get("model", "—")
        mode = data.get("auth_mode", "BASIC")
        cpu = data.get("cpu", 0)
        ram = data.get("ram", 0)

        self._tele_model.setText(f"Model: {model}")
        self._tele_mode.setText(f"Mode: {mode}")
        self._tele_cpu.setText(f"CPU: {cpu:.0f}%")
        self._tele_ram.setText(f"RAM: {ram:.0f}%")
        self._model_label.setText(f"Model: {model}")

        if self._dock.isVisible():
            self._expert_log.append(
                f"[TELEMETRY] model={model} mode={mode} cpu={cpu:.0f}% ram={ram:.0f}%"
            )

    @Slot(str)
    def _on_response_finished(self, text: str) -> None:
        # Finalize any streaming bubble
        if self._streaming_bubble and not self._streaming_text:
            self._streaming_bubble.set_text(html.escape(text))
        self._streaming_bubble = None
        self._streaming_text = ""
        self._scroll_to_bottom()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        if self._streaming_bubble:
            self._streaming_bubble.deleteLater()
            self._streaming_bubble = None
            self._streaming_text = ""
        self._add_bubble("tool", f"⚠️ {message}")
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # Auth mode
    # ------------------------------------------------------------------

    def _set_auth_mode(self, mode: AuthMode) -> None:
        get_config().auth_mode = mode
        self._refresh_auth_ui()

    def _refresh_auth_ui(self) -> None:
        mode = get_config().auth_mode
        {
            AuthMode.BASIC: self._btn_basic,
            AuthMode.AUTOPILOT: self._btn_autopilot,
            AuthMode.STRICT: self._btn_strict,
        }[mode].setChecked(True)

        color = _AUTH_COLORS[mode]
        label = _AUTH_LABELS[mode]
        self._status_mode.setText(f"Mode: {label}")
        self._status_mode.setStyleSheet(f"color:{color}; font-weight:600;")
        self._tele_mode.setText(f"Mode: {mode.name}")
        self._tele_mode.setStyleSheet(f"color:{color}; font-size:11px; font-weight:600;")

    # ------------------------------------------------------------------
    # Expert dock
    # ------------------------------------------------------------------

    def _toggle_expert_dock(self, checked: bool) -> None:
        self._dock.setVisible(checked)
        self._expert_btn.setText(f"⚙️ Expert Mode: {'ON' if checked else 'OFF'}")

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        self._expert_btn.setChecked(visible)
        self._expert_btn.setText(f"⚙️ Expert Mode: {'ON' if visible else 'OFF'}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_bubble(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, html.escape(text))  # type: ignore[arg-type]
        # Insert before the trailing stretch
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def update_model_label(self, model: str) -> None:
        self._model_label.setText(f"Model: {model}")
        self._status_model.setText(model)
        self._tele_model.setText(f"Model: {model}")
