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
from axiom.gui.widgets.swarm_pill import SwarmPill
from axiom.gui.widgets.settings_dialog import SettingsDialog
from axiom.gui.widgets.scheduler_dialog import SchedulerDialog
from axiom.services.scheduler_service import BackgroundSchedulerService
from axiom.services.sys_watchdog import SystemHealthWatchdog

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
        self._active_swarm_pill: SwarmPill | None = None
        
        # Background services now run in the headless daemon

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
        
        # Budget Updater
        self._budget_timer = QTimer(self)
        self._budget_timer.timeout.connect(self._update_budget_meter)
        self._budget_timer.start(10000) # Every 10s
        # Defer the first update slightly to avoid import loops if any
        QTimer.singleShot(100, self._update_budget_meter)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_scheduler_service'):
            self._scheduler_service.start()
        if hasattr(self, '_sys_watchdog'):
            self._sys_watchdog.start()

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if hasattr(self, '_scheduler_service'):
            self._scheduler_service.stop()
        if hasattr(self, '_sys_watchdog'):
            self._sys_watchdog.stop()
        super().closeEvent(event)

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
        
        # ---- Sandbox Mode Toggle ----
        self._sandbox_btn = QPushButton("📦 Sandbox Mode: Strict (bwrap)")
        self._sandbox_btn.setObjectName("sandboxBtn")
        self._sandbox_btn.clicked.connect(self._open_sandbox_dialog)
        tb.addWidget(self._sandbox_btn)

        tb.addSeparator()

        # ---- Automation Button ----
        self._automation_btn = QPushButton("⏱️ Automation")
        self._automation_btn.setObjectName("automationBtn")
        self._automation_btn.clicked.connect(self._open_scheduler_dialog)
        tb.addWidget(self._automation_btn)
        
        tb.addSeparator()

        # ---- Security Audit Button ----
        self._audit_btn = QPushButton("🛡️ Security Log")
        self._audit_btn.setObjectName("auditBtn")
        self._audit_btn.clicked.connect(self._open_audit_dialog)
        tb.addWidget(self._audit_btn)
        
        tb.addSeparator()

        # ---- Settings Button ----
        self._settings_btn = QPushButton("⚙️ Settings")
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.clicked.connect(self._open_settings_dialog)
        tb.addWidget(self._settings_btn)

        tb.addSeparator()
        
        # ---- System Health Button ----
        self._health_btn = QPushButton("❤️ System Health")
        self._health_btn.setObjectName("healthBtn")
        self._health_btn.setStyleSheet("color: #f38ba8;")
        self._health_btn.clicked.connect(self._open_health_radar)
        tb.addWidget(self._health_btn)

        tb.addSeparator()
        
        # ---- Knowledge Graph Button ----
        self._graph_btn = QPushButton("🕸️ Knowledge Graph")
        self._graph_btn.setObjectName("graphBtn")
        self._graph_btn.setStyleSheet("color: #cba6f7;")
        self._graph_btn.clicked.connect(self._open_graph_dialog)
        tb.addWidget(self._graph_btn)
        
        # ---- Recall Timeline Button ----
        self._recall_btn = QPushButton("⏱️ Recall Timeline")
        self._recall_btn.setObjectName("recallBtn")
        self._recall_btn.setStyleSheet("color: #89b4fa;")
        self._recall_btn.clicked.connect(self._open_recall_dialog)
        tb.addWidget(self._recall_btn)

        # ---- Cyber Audit Button ----
        self._audit_btn = QPushButton("🛡️ Cyber Audit")
        self._audit_btn.setObjectName("auditBtn")
        self._audit_btn.setStyleSheet("color: #fab387;")
        self._audit_btn.clicked.connect(self._open_security_dialog)
        tb.addWidget(self._audit_btn)

        tb.addSeparator()

        # ---- Skill Library Button ----
        self._skill_btn = QPushButton("🧩 Skill Library")
        self._skill_btn.setObjectName("skillBtn")
        self._skill_btn.clicked.connect(self._open_skill_dialog)
        tb.addWidget(self._skill_btn)

        tb.addSeparator()

        # ---- Model badge ----
        self._model_label = QLabel("Model: —")
        self._model_label.setObjectName("modelLabel")
        tb.addWidget(self._model_label)
        
        tb.addSeparator()

        # ---- Daemon Status Monitor ----
        self._daemon_status_label = QLabel("🔌 Daemon: Disconnected")
        self._daemon_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #f87171;")
        tb.addWidget(self._daemon_status_label)
        
        tb.addSeparator()

        # ---- Live Budget Meter ----
        self._budget_btn = QPushButton("☁️ Claude: Budget")
        self._budget_btn.setObjectName("budgetBtn")
        self._budget_btn.setStyleSheet("font-weight: bold; border: none; padding: 2px 8px; border-radius: 4px; background: transparent; color: #cdd6f4;")
        self._budget_btn.clicked.connect(self._open_budget_dialog)
        tb.addWidget(self._budget_btn)
        
        tb.addSeparator()

        # ---- Ollama Health Monitor ----
        self._ollama_status_label = QLabel("🟡 Ollama: Checking...")
        self._ollama_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #fbbf24;")
        tb.addWidget(self._ollama_status_label)
        
        self._ollama_start_btn = QPushButton("🚀 Start Ollama")
        self._ollama_start_btn.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; border: none; padding: 4px 10px; border-radius: 4px; margin-left: 5px;")
        self._ollama_start_btn.clicked.connect(self._on_ollama_start_clicked)
        self._ollama_start_action = tb.addWidget(self._ollama_start_btn)
        self._ollama_start_action.setVisible(False)

        tb.addWidget(QWidget())  # right padding
        
        # Initialize the health monitor
        from axiom.services.ollama_monitor import OllamaHealthMonitor
        self._ollama_monitor = OllamaHealthMonitor(self)
        self._ollama_monitor.status_changed.connect(self._on_ollama_status_changed)
        QTimer.singleShot(0, self._ollama_monitor.start)

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
        bar.setObjectName("bottomBar")
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
        self._status_memory = QLabel("🧠 Memory: Active (0 Chunks)")
        self._status_model = QLabel()
        
        self.governor_btn = QPushButton("⚡ Governor: Active (60 FPS)")
        self.governor_btn.setStyleSheet("border: none; color: #f9e2af; font-weight: bold;")
        self.governor_btn.clicked.connect(self._open_governor_dialog)
        
        sb.addWidget(self._status_mode)
        sb.addWidget(self._status_memory)
        sb.addWidget(self.governor_btn)
        sb.addPermanentWidget(self._status_model)
        
        # Memory polling timer
        from PySide6.QtCore import QTimer
        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._update_memory_count)
        self._memory_timer.start(5000)

    def _update_memory_count(self) -> None:
        try:
            # We instantiate it or use it to just query count.
            # Using count() is relatively cheap
            from axiom.memory.vector_store import VectorMemoryEngine
            engine = VectorMemoryEngine()
            c = engine.count()
            self._status_memory.setText(f"🧠 Memory: Active ({c} Chunks)")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Bridge signal wiring
    # ------------------------------------------------------------------

    def _connect_bridge(self) -> None:
        """Connect bridge signals to UI slots."""
        self._bridge.token_received.connect(self._on_token)
        self._bridge.tool_status_changed.connect(self._on_tool_status)
        self._bridge.telemetry_updated.connect(self._on_telemetry)
        self._bridge.response_finished.connect(self._on_response_finished)
        self._bridge.error_occurred.connect(self._on_error)
        self._bridge.request_gui_auth.connect(self._on_request_gui_auth)
        
        # Swarm signals
        self._bridge.swarm_agent_started.connect(self._on_swarm_started)
        self._bridge.swarm_agent_token.connect(self._on_swarm_token)
        self._bridge.swarm_agent_completed.connect(self._on_swarm_completed)

        # Daemon Connection
        self._bridge.connection_status_changed.connect(self._on_daemon_connection_changed)

    @Slot(bool)
    def _on_daemon_connection_changed(self, connected: bool) -> None:
        if connected:
            self._daemon_status_label.setText("⚡ Daemon: Connected")
            self._daemon_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #10b981;")
        else:
            self._daemon_status_label.setText("🔌 Daemon: Disconnected")
            self._daemon_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #f87171;")

    # ------------------------------------------------------------------
    # Qt Slots
    # ------------------------------------------------------------------

    @Slot(str, str, dict)
    def _on_request_gui_auth(self, tool_name: str, arguments: str, ctx: dict) -> None:
        from PySide6.QtWidgets import QMessageBox
        
        msg = QMessageBox(self)
        msg.setWindowTitle("[SECURITY APPROVAL REQUIRED]")
        msg.setText(f"AXIOM requests permission to execute an external action:\n\nTool: {tool_name}\nCommand / Args: {arguments}")
        msg.setIcon(QMessageBox.Icon.Warning)
        
        allow_btn = msg.addButton("Allow Execution", QMessageBox.ButtonRole.AcceptRole)
        allow_btn.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;")
        
        deny_btn = msg.addButton("Deny Action", QMessageBox.ButtonRole.RejectRole)
        deny_btn.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;")
        
        msg.setStyleSheet("QMessageBox { background-color: #1a1a1f; color: #d4d4d8; } QLabel { color: #d4d4d8; font-family: monospace; }")
        
        msg.exec()
        
        ctx["result"]["granted"] = (msg.clickedButton() == allow_btn)
        ctx["event"].set()

    def _submit_task_from_service(self, prompt: str) -> None:
        """Called by background services to submit a task."""
        # Must be thread-safe. QTimer.singleShot executes in the main thread.
        QTimer.singleShot(0, lambda: self._on_submit_background_task(prompt))

    def _on_submit_background_task(self, prompt: str) -> None:
        self._add_bubble("user", f"[SYSTEM/BACKGROUND] {prompt}")
        self._streaming_text = ""
        self._streaming_bubble = self._add_bubble("assistant", "")
        self._active_swarm_pill = None
        self._bridge.submit_task(prompt)

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
        self._active_swarm_pill = None
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

    @Slot(str, str)
    def _on_swarm_started(self, agent_name: str, task: str) -> None:
        if not self._active_swarm_pill:
            self._active_swarm_pill = SwarmPill()
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, self._active_swarm_pill)
        self._active_swarm_pill.add_agent_task(agent_name, task)
        self._scroll_to_bottom()
        
    @Slot(str, str)
    def _on_swarm_token(self, agent_name: str, chunk: str) -> None:
        if self._active_swarm_pill:
            self._active_swarm_pill.update_agent_status(agent_name, chunk)
            self._scroll_to_bottom()
            
    @Slot(str, str)
    def _on_swarm_completed(self, agent_name: str, result: str) -> None:
        if self._active_swarm_pill:
            self._active_swarm_pill.complete_agent(agent_name, result)
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

    @Slot(bool, float)
    def _on_ollama_status_changed(self, is_online: bool, latency: float) -> None:
        if is_online:
            self._ollama_status_label.setText(f"🟢 Ollama: Online ({latency:.0f}ms)")
            self._ollama_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #10b981;")
            self._ollama_start_btn.setVisible(False)
            self._ollama_start_action.setVisible(False)
            
            # Auto-Reconnect Signal: trigger a quick background model registry refresh
            self._bridge.refresh_models()
        else:
            self._ollama_status_label.setText("🔴 Ollama: Offline")
            self._ollama_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #ef4444;")
            self._ollama_start_btn.setVisible(True)
            self._ollama_start_action.setVisible(True)
            
            # Auto-start on boot if configured
            if getattr(self, "_first_ollama_ping", True):
                from axiom.config import get_config
                if get_config().auto_ollama_start:
                    self._on_ollama_start_clicked()
                    
        self._first_ollama_ping = False

    @Slot()
    def _open_settings_dialog(self) -> None:
        from axiom.gui.widgets.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self._bridge, self)
        dlg.settings_updated.connect(self._on_settings_updated)
        dlg.exec()

    def _open_audit_dialog(self) -> None:
        from axiom.gui.widgets.audit_dialog import AuditDialog
        dialog = AuditDialog(self)
        dialog.exec()

    def _open_skill_dialog(self) -> None:
        """Open the Skill Library dialog."""
        from axiom.gui.widgets.skill_dialog import SkillManagerDialog
        dlg = SkillManagerDialog(self)
        dlg.exec()

    def _open_health_radar(self) -> None:
        """Open the System Health Radar dialog."""
        from axiom.gui.widgets.health_radar import HealthRadarDialog
        dlg = HealthRadarDialog(self)
        dlg.exec()

    def _open_graph_dialog(self) -> None:
        from axiom.gui.widgets.graph_dialog import GraphDialog
        dlg = GraphDialog(self)
        dlg.exec()
        
    def _open_recall_dialog(self) -> None:
        from axiom.gui.widgets.recall_dialog import RecallDialog
        dlg = RecallDialog(self)
        dlg.exec()
        
    def _open_security_dialog(self) -> None:
        from axiom.gui.widgets.security_dialog import SecurityDashboardDialog
        dlg = SecurityDashboardDialog(self)
        dlg.exec()
        
    def _open_governor_dialog(self) -> None:
        from axiom.gui.widgets.governor_dialog import GovernorDialog
        dlg = GovernorDialog(self)
        dlg.exec()
        
    def _open_sandbox_dialog(self) -> None:
        from axiom.gui.widgets.sandbox_dialog import SandboxManagerDialog
        dlg = SandboxManagerDialog(self)
        dlg.exec()

    @Slot()
    def _open_budget_dialog(self) -> None:
        from axiom.gui.widgets.budget_dialog import BudgetDialog
        dialog = BudgetDialog(self)
        dialog.exec()
        self._update_budget_meter()

    @Slot()
    def _update_budget_meter(self):
        try:
            from axiom.engine.budget_mgr import TokenBudgetManager
            mgr = TokenBudgetManager()
            _, _, percent = mgr.can_afford_cloud_call(0)
            
            if percent >= 90:
                self._budget_btn.setText("🔴 Claude: Capped (Local Only)")
                self._budget_btn.setStyleSheet("font-weight: bold; border: none; padding: 2px 8px; border-radius: 4px; background: transparent; color: #f38ba8;")
            elif percent >= 75:
                self._budget_btn.setText(f"🟡 Claude: {100 - int(percent)}% Budget")
                self._budget_btn.setStyleSheet("font-weight: bold; border: none; padding: 2px 8px; border-radius: 4px; background: transparent; color: #f9e2af;")
            else:
                self._budget_btn.setText(f"☁️ Claude: {100 - int(percent)}% Budget")
                self._budget_btn.setStyleSheet("font-weight: bold; border: none; padding: 2px 8px; border-radius: 4px; background: transparent; color: #a6e3a1;")
        except Exception as e:
            pass

    @Slot()
    def _on_settings_updated(self):
        import axiom.gui.app as gui_app
        from PySide6.QtWidgets import QApplication
        from axiom.config import get_config
        
        # Reload stylesheet
        gui_app._load_stylesheet(QApplication.instance())
        
        # Check model selection mode
        config = get_config()
        if config.model_selection_mode == "manual":
            self.update_model_label(f"{config.ollama_model} (Manual)")
        else:
            self.update_model_label(config.ollama_model)

    @Slot()
    def _on_ollama_start_clicked(self) -> None:
        self._ollama_status_label.setText("🟡 Starting Daemon...")
        self._ollama_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #fbbf24;")
        self._ollama_start_btn.setEnabled(False)
        self._ollama_monitor.trigger_rapid_polling()
        
        # Spawn daemon in background thread to avoid blocking UI
        import threading
        def _spawn():
            success = self._ollama_monitor.spawn_ollama_service()
            if not success:
                # Re-enable if failed
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._ollama_start_btn.setEnabled(True))
        threading.Thread(target=_spawn, daemon=True).start()

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

    @Slot()
    def _open_scheduler_dialog(self) -> None:
        if not hasattr(self, '_scheduler_service'):
            from axiom.services.scheduler_service import BackgroundSchedulerService
            from axiom.core.events import EventBus
            self._scheduler_service = BackgroundSchedulerService(event_bus=EventBus())
        dlg = SchedulerDialog(self._scheduler_service, self)
        dlg.exec()
