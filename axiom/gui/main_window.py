"""AXIOM Desktop v6.0 LTS — Main Application Window.

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
    QSystemTrayIcon,
    QMenu,
    QApplication,
)

from axiom.config import get_config, AuthMode
from axiom.gui.widgets.chat_bubble import MessageBubble, ToolPill
from axiom.gui.widgets.swarm_pill import SwarmPill
from axiom.gui.widgets.settings_dialog import SettingsDialog
from axiom.gui.widgets.scheduler_ui import TemporalSchedulerDialog
from axiom.services.scheduler import TemporalService
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
    """AXIOM Desktop v6.0 LTS main application window."""

    def __init__(self, bridge: "AxiomBridge", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._streaming_bubble: MessageBubble | None = None
        self._streaming_text: str = ""
        self._active_swarm_pill: SwarmPill | None = None
        
        # Background services now run in the headless daemon
        self._temporal_service = TemporalService(event_bus=self._bridge._event_bus if hasattr(self._bridge, '_event_bus') else None)

        self.setWindowTitle("AXIOM Desktop v6.0 LTS")
        self.setMinimumSize(400, 640)
        self.resize(1280, 800)

        self._build_toolbar()
        self._build_central_widget()
        self._build_expert_dock()
        self._build_synapse_dock()
        self._build_sidebar()
        self._build_bottom_bar()
        self._build_status_bar()
        self._connect_bridge()
        self._refresh_auth_ui()
        self._init_audio()
        
        # Initial Welcome Message
        self._add_bubble("assistant", "⚡ AXIOM Desktop v6.0 LTS Online — Select a mode above or type a prompt below to begin.")
        
        self._init_tray()
        self._init_hotkey()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, '_temporal_service'):
            self._temporal_service.start()
        if hasattr(self, '_sys_watchdog'):
            self._sys_watchdog.start()

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if event.spontaneous():
            event.ignore()
            self.hide()
            logger.info("Window hidden to system tray.")
        else:
            super().closeEvent(event)
            
    def force_quit(self) -> None:
        """Actually shut down the application."""
        if hasattr(self, '_temporal_service'):
            self._temporal_service.stop()
        if hasattr(self, '_sys_watchdog'):
            self._sys_watchdog.stop()
        if hasattr(self, '_wake_daemon') and self._wake_daemon:
            self._wake_daemon.stop()
        if hasattr(self, '_hotkey_service'):
            self._hotkey_service.stop()
            
        logger.info("AXIOM shutting down gracefully.")
        QApplication.quit()

    def _init_audio(self) -> None:
        from axiom.gui.config_manager import get_ui_config_manager
        self._voice_mode = get_ui_config_manager().load().voice_mode
        self._tts = None
        self._stt = None
        self._recorder = None
        self._wake_daemon = None
        
        # Initialize TTS
        try:
            from axiom.audio.tts import TextToSpeechEngine
            self._tts = TextToSpeechEngine.instance()
        except Exception as e:
            logger.error(f"TTS init failed: {e}")
            
        # Initialize STT/WakeWord
        try:
            from axiom.audio.stt import WhisperTranscriber, AudioRecorder, WakeWordDaemon
            self._stt = WhisperTranscriber.instance()
            self._recorder = AudioRecorder()
            
            if self._voice_mode == "wake_word":
                self._wake_daemon = WakeWordDaemon(self)
                self._wake_daemon.wake_word_detected.connect(self._on_wake_word)
                self._wake_daemon.start()
        except Exception as e:
            logger.error(f"STT init failed: {e}")

    def _init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        # Using a default Qt icon for the tray
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        
        toggle_action = QAction("Show/Hide AXIOM", self)
        toggle_action.triggered.connect(self._toggle_visibility)
        tray_menu.addAction(toggle_action)
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        tray_menu.addAction(settings_action)
        
        quit_action = QAction("Quit AXIOM", self)
        quit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
    def _init_hotkey(self) -> None:
        try:
            from axiom.services.hotkey_service import GlobalHotkeyService
            self._hotkey_service = GlobalHotkeyService()
            self._hotkey_service.signaler.toggle_requested.connect(self._toggle_visibility)
            self._hotkey_service.signaler.context_summoned.connect(self._on_context_summoned)
            self._hotkey_service.signaler.vision_summoned.connect(self._on_vision_summoned)
            self._hotkey_service.start()
        except ImportError:
            logger.error("pynput not found. Global hotkey disabled.")
            
    @Slot()
    def _toggle_visibility(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show()
            self.activateWindow()
            self.raise_()
            # Try to focus chat input
            if hasattr(self, '_input'):
                self._input.setFocus()
                
    @Slot()
    def _on_context_summoned(self) -> None:
        """Fetch clipboard, inject into prompt, and summon."""
        from axiom.services.clipboard_service import ClipboardService
        clipboard_text = ClipboardService.get_text()
        
        if clipboard_text:
            injection = f"\n```\n{clipboard_text}\n```\n"
            self._input.setText(injection)
            
            # Move cursor to the beginning
            cursor = self._input.textCursor()
            cursor.setPosition(0)
            self._input.setTextCursor(cursor)
            
        self.show()
        self.activateWindow()
        self.raise_()
        if hasattr(self, '_input'):
            self._input.setFocus()
            
    @Slot()
    def _on_vision_summoned(self) -> None:
        """Capture screen, preview it, and summon."""
        from axiom.services.vision_service import VisionService
        import os
        from PySide6.QtGui import QPixmap
        
        path = VisionService.capture_screen()
        if path and os.path.exists(path):
            self._current_attachment = path
            pixmap = QPixmap(path)
            scaled = pixmap.scaledToHeight(100, Qt.TransformationMode.SmoothTransformation)
            self._attachment_preview.setPixmap(scaled)
            self._attachment_preview.show()
            
        self.show()
        self.activateWindow()
        self.raise_()
        if hasattr(self, '_input'):
            self._input.setFocus()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(6)
        
        scroll.setWidget(container)
        tb.addWidget(scroll)
        
        def _add_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
            h_layout.addWidget(sep)

        # AXIOM brand label
        brand = QLabel("  AXIOM")
        brand.setStyleSheet("font-weight:800; font-size:15px; color:#10b981; letter-spacing:0.06em;")
        h_layout.addWidget(brand)

        spacer1 = QWidget()
        spacer1.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer1.setStyleSheet("background: transparent;")
        h_layout.addWidget(spacer1)

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

        h_layout.addWidget(auth_frame)

        spacer2 = QWidget()
        spacer2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer2.setStyleSheet("background: transparent;")
        h_layout.addWidget(spacer2)

        # ---- Expert Mode Toggle ----
        self._expert_btn = QPushButton("⚙️ Expert Mode: OFF")
        self._expert_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._expert_btn.setObjectName("expertToggleBtn")
        self._expert_btn.setCheckable(True)
        self._expert_btn.clicked.connect(self._toggle_expert_dock)
        h_layout.addWidget(self._expert_btn)
        
        # ---- Master Kernel Supervisor Toggle ----
        self._kernel_btn = QPushButton("🧠 AXIOM Kernel v5.0")
        self._kernel_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._kernel_btn.setObjectName("kernelBtn")
        self._kernel_btn.setStyleSheet("""
            background-color: #89b4fa;
            color: #11111b;
            font-weight: bold;
            border-radius: 4px;
            padding: 5px 15px;
        """)
        self._kernel_btn.clicked.connect(self._open_kernel_dialog)
        h_layout.addWidget(self._kernel_btn)

        _add_sep()
        
        # ---- System Hub Button ----
        self._hub_btn = QPushButton("⚙️ System Hub")
        self._hub_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._hub_btn.setObjectName("hubBtn")
        self._hub_btn.setStyleSheet("""
            background-color: #313244;
            color: #cdd6f4;
            font-weight: bold;
            border-radius: 4px;
            padding: 5px 15px;
        """)
        self._hub_btn.clicked.connect(self._open_system_hub_dialog)
        h_layout.addWidget(self._hub_btn)
        
        # ---- Plugin Hub Button ----
        self._plugin_btn = QPushButton("🔌 Plugin Hub")
        self._plugin_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._plugin_btn.setObjectName("pluginBtn")
        self._plugin_btn.setStyleSheet("""
            background-color: #18181b;
            border: 1px solid #2ecc71;
            color: #2ecc71;
            font-weight: bold;
            border-radius: 4px;
            padding: 5px 15px;
        """)
        self._plugin_btn.clicked.connect(self._open_plugin_dialog)
        h_layout.addWidget(self._plugin_btn)

        # ---- Temporal Engine Button ----
        self._temporal_btn = QPushButton("📅 Temporal Engine")
        self._temporal_btn.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self._temporal_btn.setObjectName("temporalBtn")
        self._temporal_btn.setStyleSheet("""
            background-color: #fab387;
            color: #11111b;
            font-weight: bold;
            border-radius: 4px;
            padding: 5px 15px;
        """)
        self._temporal_btn.clicked.connect(self._open_temporal_dialog)
        h_layout.addWidget(self._temporal_btn)

        _add_sep()

        # ---- Model badge ----
        self._model_label = QLabel("Model: —")
        self._model_label.setObjectName("modelLabel")
        h_layout.addWidget(self._model_label)
        
        _add_sep()



        # ---- Ollama Health Monitor ----
        self._ollama_status_label = QLabel("🟡 Ollama: Checking...")
        self._ollama_status_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #fbbf24;")
        h_layout.addWidget(self._ollama_status_label)
        
        self._ollama_start_btn = QPushButton("🚀 Start Ollama")
        self._ollama_start_btn.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; border: none; padding: 4px 10px; border-radius: 4px; margin-left: 5px;")
        self._ollama_start_btn.clicked.connect(self._on_ollama_start_clicked)
        
        self._ollama_start_action = QWidget()
        btn_layout = QHBoxLayout(self._ollama_start_action)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self._ollama_start_btn)
        h_layout.addWidget(self._ollama_start_action)
        self._ollama_start_action.setVisible(False)

        h_layout.addWidget(QWidget())  # right padding
        
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

    def _build_sidebar(self) -> None:
        from axiom.gui.widgets.sidebar import SessionSidebar
        self._sidebar = SessionSidebar(self._bridge, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._sidebar)
        
        # Load sessions shortly after boot
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, self._sidebar.load_sessions)

    def _build_synapse_dock(self) -> None:
        """Dock for Synapse Visualizer."""
        self._synapse_dock = QDockWidget("Synapse Visualizer", self)
        self._synapse_dock.setObjectName("synapseDock")
        self._synapse_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self._synapse_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self._synapse_dock.setMinimumWidth(320)
        self._synapse_graph = SynapseGraph(self._synapse_dock)
        self._synapse_dock.setWidget(self._synapse_graph)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._synapse_dock)

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
        self._swarm_status = QLabel("Compute: Local")
        self._swarm_status.setStyleSheet("color:#6c7086; font-size:11px; font-weight:600;")
        for w in (self._tele_model, self._tele_mode, self._tele_cpu, self._tele_ram, self._swarm_status):
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
        from axiom.gui.widgets.swarm_hud import SwarmHUD
        
        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(0,0,0,0)
        vlayout.setSpacing(0)
        
        self._swarm_hud = SwarmHUD()
        vlayout.addWidget(self._swarm_hud)
        
        bar = QWidget()
        bar.setObjectName("bottomBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 10, 16, 10)
        bar_layout.setSpacing(10)
        
        from axiom.gui.config_manager import get_ui_config_manager
        voice_mode = get_ui_config_manager().load().voice_mode

        self._mic_btn = None
        if voice_mode == "push_to_talk":
            self._mic_btn = QPushButton("🎤")
            self._mic_btn.setFixedSize(48, 48)
            self._mic_btn.setObjectName("micBtn")
            self._mic_btn.setStyleSheet("background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; font-size: 18px;")
            self._mic_btn.setCheckable(True)
            self._mic_btn.clicked.connect(self._on_mic_toggled)
            bar_layout.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._input_container = QWidget()
        self._input_layout = QVBoxLayout(self._input_container)
        self._input_layout.setContentsMargins(0, 0, 0, 0)
        self._input_layout.setSpacing(5)

        self._attachment_preview = QLabel()
        self._attachment_preview.hide()
        self._input_layout.addWidget(self._attachment_preview)

        self._input = ChatInputEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Ask AXIOM anything… (Enter to send, Shift+Enter for new line)")
        self._input.setMaximumHeight(130)
        self._input.setMinimumHeight(60)
        self._input_layout.addWidget(self._input)
        
        bar_layout.addWidget(self._input_container)

        send_btn = QPushButton("Send ↑")
        send_btn.setObjectName("sendBtn")
        send_btn.setFixedSize(90, 48)
        send_btn.clicked.connect(self._on_send)
        bar_layout.addWidget(send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Connect the custom signal
        self._input.send_requested.connect(self._on_send)

        # Slot bar into the main layout below central widget
        main_layout = self.centralWidget().layout()
        main_layout.addWidget(container)
        main_layout.setStretch(0, 9)
        main_layout.setStretch(1, 0)

    def _build_status_bar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._status_mode = QLabel()
        self._status_memory = QLabel("🧠 Memory: Active (0 Chunks)")
        self._status_axiomfs = QLabel("AxiomFS: Offline")
        self._status_axiomfs.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self._status_model = QLabel()
        
        self.governor_btn = QPushButton("⚡ Governor: Active (60 FPS)")
        self.governor_btn.setStyleSheet("border: none; color: #f9e2af; font-weight: bold;")
        self.governor_btn.setCheckable(True)
        self.governor_btn.setChecked(False)
        self.governor_btn.setText("⚡ Governor: Inactive")
        self.governor_btn.setStyleSheet("border: none; color: #a6adc8; font-weight: bold;")
        self.governor_btn.clicked.connect(self._toggle_strict_mode)

        self._thermal_label = QLabel("🌡️ Thermal: Normal (64°C)")
        self._thermal_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        
        self.voice_btn = QPushButton("🔊 Voice: Active")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setChecked(True)
        self.voice_btn.setStyleSheet("border: none; color: #89b4fa; font-weight: bold;")
        self.voice_btn.clicked.connect(self._toggle_voice)

        self.pager_btn = QPushButton("🧠 Pager: L1")
        self.pager_btn.setStyleSheet("border: none; color: #89b4fa; font-weight: bold;")
        self.pager_btn.clicked.connect(self._open_infrastructure_dialog)

        self.cloud_btn = QPushButton("☁️ Cloud Burst: Ready")
        self.cloud_btn.setStyleSheet("border: none; color: #a6e3a1; font-weight: bold;")
        self.cloud_btn.clicked.connect(self._open_infrastructure_dialog)

        self.hardware_btn = QPushButton("🔌 Hardware I/O")
        self.hardware_btn.setStyleSheet("border: none; color: #fab387; font-weight: bold;")
        self.hardware_btn.clicked.connect(self._open_hardware_dialog)

        self.power_label = QLabel("🔋 Power: Max Perf")
        self.power_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding-right: 10px;")

        self.singularity_btn = QPushButton("🌌 Singularity")
        self.singularity_btn.setStyleSheet("border: none; color: #cba6f7; font-weight: bold;")
        self.singularity_btn.clicked.connect(self._open_singularity_dialog)

        self._status_updates = QLabel("[ Updates: Checking... ]")
        self._status_updates.setStyleSheet("font-weight: 600; color: #fab387; padding-right: 10px;")

        sb.addWidget(self._status_mode)
        
        # Daemon Connection Status
        self._status_daemon = QLabel("🔌 Daemon: Disconnected")
        self._status_daemon.setStyleSheet("color: #f87171; font-weight: bold; padding-left: 5px; padding-right: 15px;")
        sb.addWidget(self._status_daemon)
        
        # Intermediate / Advanced Widgets
        sb.addWidget(self.power_label)
        sb.addWidget(self._thermal_label)
        sb.addWidget(self.governor_btn)
        
        # Developer / Cloud Widgets
        sb.addPermanentWidget(self.cloud_btn)
        sb.addPermanentWidget(self.hardware_btn)
        sb.addPermanentWidget(self.pager_btn)
        sb.addPermanentWidget(self.singularity_btn)
        
        sb.addPermanentWidget(self._status_updates)
        sb.addPermanentWidget(self._status_model)

        # Wire Profile Switcher
        from axiom.services.profile_service import ProfileService, ProfileLevel
        ps = ProfileService.instance()
        ps.profile_changed.connect(self._apply_profile)
        self._apply_profile(ps.get_profile())

        
        # Check for updates in background
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, self._check_updates_async)
        
        # Memory polling timer
        self._memory_timer = QTimer(self)
        self._memory_timer.timeout.connect(self._update_memory_count)
        self._memory_timer.start(5000)

    def _check_updates_async(self):
        import asyncio
        from axiom.updater.manager import UpdateManager
        
        async def _check():
            mgr = UpdateManager()
            res = await mgr.check_for_updates()
            if res.get("update_available"):
                self._status_updates.setText(f"[ Updates: {res['latest_version']} Available ]")
                self._status_updates.setStyleSheet("font-weight: 600; color: #f38ba8; padding-right: 10px;")
                # Prompt user on main thread
                from PySide6.QtCore import QMetaObject, Q_ARG, Qt
                QMetaObject.invokeMethod(self, "_prompt_update", Qt.ConnectionType.QueuedConnection, Q_ARG(str, res['latest_version']))
            else:
                self._status_updates.setText("[ Updates: Up-to-Date ]")
                self._status_updates.setStyleSheet("font-weight: 600; color: #a6e3a1; padding-right: 10px;")
                
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_check(), loop)
        else:
            asyncio.run(_check())
            
    @Slot(str)
    def _prompt_update(self, latest_version: str) -> None:
        from PySide6.QtWidgets import QMessageBox
        import subprocess
        import sys
        import os
        
        reply = QMessageBox.question(
            self,
            "Update Available",
            f"Version {latest_version} is available. Update now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Launch update script detached
            script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "update.sh")
            if os.path.exists(script_path):
                subprocess.Popen(["bash", script_path], start_new_session=True)
                sys.exit(0)
            else:
                QMessageBox.warning(self, "Error", f"Update script not found at {script_path}")

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

    @Slot(object)
    def _apply_profile(self, level) -> None:
        """Dynamically toggle visibility of HUD elements based on current profile."""
        from axiom.services.profile_service import ProfileLevel
        
        # Intermediate / Advanced Widgets
        show_advanced = level in (ProfileLevel.ADVANCED, ProfileLevel.DEVELOPER)
        self.power_label.setVisible(show_advanced)
        self._thermal_label.setVisible(show_advanced)
        self.governor_btn.setVisible(show_advanced)
        
        # Developer / Cloud Widgets
        show_developer = level == ProfileLevel.DEVELOPER
        self.cloud_btn.setVisible(show_developer)
        self.hardware_btn.setVisible(show_developer)
        self.pager_btn.setVisible(show_developer)
        self.singularity_btn.setVisible(show_developer)
        
        # Developer extra log toggles
        if self._dock.isVisible() and not show_developer:
            self._dock.hide()

    # ------------------------------------------------------------------
    # Bridge signal wiring
    # ------------------------------------------------------------------

    def _connect_bridge(self) -> None:
        """Connect bridge signals to UI slots."""
        # Daemon bridge bindings
        self._bridge.token_received.connect(self._on_token)
        self._bridge.response_finished.connect(self._on_response_finished)
        self._bridge.telemetry_updated.connect(self._on_telemetry)
        self._bridge.error_occurred.connect(self._on_error)
        self._bridge.tool_status_changed.connect(self._on_tool_status)
        self._bridge.request_gui_auth.connect(self._on_request_gui_auth)
        self._bridge.swarm_status_changed.connect(self._on_swarm_status_changed)
        
        # Swarm signals
        self._bridge.swarm_agent_started.connect(self._on_swarm_started)
        self._bridge.swarm_agent_token.connect(self._on_swarm_token)
        self._bridge.swarm_agent_completed.connect(self._on_swarm_completed)
        self._bridge.synapse_event.connect(self._synapse_graph.handle_telemetry)
        self._bridge.axiomfs_status.connect(self._on_axiomfs_status)
        self._bridge.governor_approval_requested.connect(self._on_approval_requested)

        # Daemon Connection
        self._bridge.connection_status_changed.connect(self._on_daemon_connection_changed)

    @Slot(str)
    @Slot(str)
    def _on_axiomfs_status(self, status: str) -> None:
        self._status_axiomfs.setText(f"AxiomFS: {status}")

    def _on_daemon_connection_changed(self, state: str) -> None:
        if state == 'connected':
            self._status_daemon.setText("⚡ Daemon: Connected")
            self._status_daemon.setStyleSheet("color: #10b981; font-weight: bold; padding-left: 5px; padding-right: 15px;")
        elif state == 'connecting':
            self._status_daemon.setText("⏳ Daemon: Starting...")
            self._status_daemon.setStyleSheet("color: #f59e0b; font-weight: bold; padding-left: 5px; padding-right: 15px;")
        else:
            self._status_daemon.setText("🔌 Daemon: Disconnected")
            self._status_daemon.setStyleSheet("color: #f87171; font-weight: bold; padding-left: 5px; padding-right: 15px;")

    # ------------------------------------------------------------------
    # Qt Slots
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_swarm_status_changed(self, payload: dict) -> None:
        active = payload.get("active", False)
        endpoint = payload.get("endpoint", "")
        if active:
            self._swarm_status.setText(f"Swarm Compute: Active [{endpoint}]")
            self._swarm_status.setStyleSheet("color: #74c7ec; font-size:11px; font-weight: bold; background-color: rgba(116, 199, 236, 0.1); border-radius: 4px; padding: 2px 4px;")
            if self._dock.isVisible():
                self._expert_log.append(f"[SWARM] Offloading inference to {endpoint}")
        else:
            self._swarm_status.setText("Compute: Local")
            self._swarm_status.setStyleSheet("color: #6c7086; font-size:11px; font-weight:600;")
            if self._dock.isVisible():
                self._expert_log.append("[SWARM] Resumed local inference")

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
        display_text = text
        has_attachment = hasattr(self, '_current_attachment') and self._current_attachment
        
        if not text and not has_attachment:
            return
            
        if has_attachment:
            import base64
            try:
                with open(self._current_attachment, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                text += f"\n\n![screenshot](data:image/png;base64,{b64})"
                display_text = f"{display_text}\n\n*[Attached Screen Capture]*" if display_text else "*[Attached Screen Capture]*"
            except Exception as e:
                logger.error(f"Failed to read attachment: {e}")
            
            self._attachment_preview.hide()
            self._current_attachment = None
            
        self._input.clear()
        self._add_bubble("user", display_text.strip())
        
        # Start a new streaming assistant bubble
        self._streaming_text = ""
        self._streaming_bubble = self._add_bubble("assistant", "")
        self._active_swarm_pill = None
        self._bridge.submit_task(text)
        
    @Slot()
    def _on_mic_toggled(self) -> None:
        if not self._mic_btn or not self._recorder or not self._stt:
            return
            
        if self._mic_btn.isChecked():
            self._mic_btn.setStyleSheet("background-color: #ef4444; color: white; border: 1px solid #ef4444; border-radius: 8px; font-size: 18px;")
            self._input.setPlaceholderText("Listening...")
            self._recorder.start_recording()
        else:
            self._mic_btn.setStyleSheet("background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; font-size: 18px;")
            self._input.setPlaceholderText("Transcribing...")
            audio_data = self._recorder.stop_recording()
            
            # Process in background to avoid blocking UI
            import asyncio
            async def _transcribe():
                text = await self._stt.transcribe(audio_data)
                # Ensure UI update happens on main thread
                from PySide6.QtCore import QMetaObject, Q_ARG, Qt
                QMetaObject.invokeMethod(self, "_on_transcription_complete", Qt.ConnectionType.QueuedConnection, Q_ARG(str, text))
            
            asyncio.run_coroutine_threadsafe(_transcribe(), self._bridge._loop)

    @Slot(str)
    def _on_transcription_complete(self, text: str) -> None:
        self._input.setPlaceholderText("Ask AXIOM anything… (Enter to send, Shift+Enter for new line)")
        if text:
            current = self._input.toPlainText()
            self._input.setPlainText((current + " " + text).strip())

    @Slot()
    def _on_wake_word(self) -> None:
        self._add_bubble("user", "[Wake Word Detected] Listening...")
        # A full implementation would trigger a timed recording or VAD here.
        # For Phase 6.0, we just log detection for now.
        pass

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
        if hasattr(self, '_swarm_hud'):
            self._swarm_hud.add_pill(agent_name, task)
        
    @Slot(str, str)
    def _on_swarm_token(self, agent_name: str, chunk: str) -> None:
        if hasattr(self, '_swarm_hud'):
            self._swarm_hud.update_pill(agent_name, chunk)
            
    @Slot(str, str)
    def _on_swarm_completed(self, agent_name: str, result: str) -> None:
        if hasattr(self, '_swarm_hud'):
            self._swarm_hud.remove_pill(agent_name)

    @Slot(dict)
    def _on_telemetry(self, data: dict) -> None:
        model = data.get("model", "—")
        mode = data.get("auth_mode", "BASIC")
        cpu = data.get("cpu", 0.0)
        ram = data.get("ram", 0.0)
        
        # New Hardware Sensors
        cpu_temp = data.get("cpu_temp", -1.0)
        gpu_temp = data.get("gpu_temp", -1.0)
        vram = data.get("vram", -1.0)

        self._tele_model.setText(f"Model: {model}")
        self._tele_mode.setText(f"Mode: {mode}")
        self._tele_cpu.setText(f"CPU: {cpu:.0f}%")
        self._tele_ram.setText(f"RAM: {ram:.0f}%")
        self._model_label.setText(f"Model: {model}")

        # Update Thermal Label
        max_temp = max(cpu_temp, gpu_temp)
        if max_temp > 90:
            self._thermal_label.setText(f"🌡️ Thermal: Critical ({max_temp:.0f}°C)")
            self._thermal_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        elif max_temp > 75:
            self._thermal_label.setText(f"🌡️ Thermal: High ({max_temp:.0f}°C)")
            self._thermal_label.setStyleSheet("color: #f9e2af; font-weight: bold;")
        elif max_temp > 0:
            self._thermal_label.setText(f"🌡️ Thermal: Normal ({max_temp:.0f}°C)")
            self._thermal_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            self._thermal_label.setText("🌡️ Thermal: N/A")
            self._thermal_label.setStyleSheet("color: #6c7086; font-weight: bold;")

        # Update Power / VRAM Label
        if vram >= 0:
            self.power_label.setText(f"🔋 VRAM: {vram:.0f}%")
            if vram > 90:
                self.power_label.setStyleSheet("color: #f38ba8; font-weight: bold; padding-right: 10px;")
            else:
                self.power_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding-right: 10px;")
        else:
            self.power_label.setText("🔋 Power: Max Perf")
            self.power_label.setStyleSheet("color: #a6e3a1; font-weight: bold; padding-right: 10px;")

        if self._dock.isVisible():
            self._expert_log.append(
                f"[TELEMETRY] model={model} mode={mode} cpu={cpu:.0f}% ram={ram:.0f}% vram={vram:.0f}%"
            )

    @Slot(str)
    def _on_response_finished(self, text: str) -> None:
        # Finalize any streaming bubble
        if self._streaming_bubble and not self._streaming_text:
            self._streaming_bubble.set_text(html.escape(text))
        self._streaming_bubble = None
        self._streaming_text = ""
        self._scroll_to_bottom()
        
        if hasattr(self, '_tts') and self._tts:
            import asyncio
            asyncio.run_coroutine_threadsafe(self._tts.speak(text), self._bridge._loop)

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
    def _open_plugin_dialog(self) -> None:
        """Open the Plugin Hub dialog."""
        from axiom.gui.widgets.plugin_manager import PluginManagerDialog
        dlg = PluginManagerDialog(self._bridge, self)
        dlg.exec()

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
        
    def _toggle_strict_mode(self) -> None:
        is_strict = self.governor_btn.isChecked()
        if is_strict:
            self.governor_btn.setText("⚡ Governor: Active")
            self.governor_btn.setStyleSheet("border: none; color: #f9e2af; font-weight: bold;")
        else:
            self.governor_btn.setText("⚡ Governor: Inactive")
            self.governor_btn.setStyleSheet("border: none; color: #a6adc8; font-weight: bold;")
        self._bridge.set_strict_mode(is_strict)

    @Slot(str, dict)
    def _on_approval_requested(self, tool_name: str, arguments: dict) -> None:
        from axiom.gui.widgets.governor_dialog import ExecutionGateDialog
        dlg = ExecutionGateDialog(tool_name, arguments, self)
        approved = dlg.exec_() == QDialog.Accepted
        self._bridge.send_approval_response(tool_name, approved)

    def _open_governor_dialog(self) -> None:
        dlg.exec()
        
    def _open_kernel_dialog(self) -> None:
        from axiom.gui.widgets.kernel_dialog import KernelControlCenterDialog
        dlg = KernelControlCenterDialog(self)
        dlg.exec()
        
    def _open_sandbox_dialog(self) -> None:
        from axiom.gui.widgets.sandbox_dialog import SandboxManagerDialog
        dlg = SandboxManagerDialog(self)
        dlg.exec()
        
    def _open_fs_dialog(self) -> None:
        from axiom.gui.widgets.fs_dialog import AxiomFSDialog
        dlg = AxiomFSDialog(self)
        dlg.exec()
        
    def _open_vm_dialog(self) -> None:
        from axiom.gui.widgets.vm_dialog import VMManagerDialog
        dlg = VMManagerDialog(self)
        dlg.exec()
        
    def _toggle_voice(self, checked: bool) -> None:
        if checked:
            self.voice_btn.setText("🔊 Voice: Active")
            self.voice_btn.setStyleSheet("border: none; color: #89b4fa; font-weight: bold;")
        else:
            self.voice_btn.setText("🔇 Voice: Muted")
            self.voice_btn.setStyleSheet("border: none; color: #6c7086; font-weight: bold;")
        # Send toggle to voice daemon via IPC or local instance
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

    def _open_temporal_dialog(self) -> None:
        from axiom.gui.widgets.scheduler_ui import TemporalSchedulerDialog
        dlg = TemporalSchedulerDialog(self)
        dlg.exec()

    def _open_iot_dialog(self) -> None:
        """Open the IoT/Physical World dialog."""
        from axiom.gui.widgets.iot_dialog import IoTControlDialog
        dlg = IoTControlDialog(self)
        dlg.exec()

    def _open_firewall_dialog(self) -> None:
        """Open the eBPF Firewall dialog."""
        from axiom.gui.widgets.firewall_dialog import FirewallControlDialog
        dlg = FirewallControlDialog(self)
        dlg.exec()

    def _open_infrastructure_dialog(self) -> None:
        """Open the Infrastructure Topology dialog."""
        from axiom.gui.widgets.infrastructure_dialog import InfrastructureTopologyDialog
        dlg = InfrastructureTopologyDialog(self)
        dlg.exec()

    def _open_hardware_dialog(self) -> None:
        """Open the Hardware I/O Matrix dialog."""
        from axiom.gui.widgets.hardware_dialog import HardwareMatrixDialog
        dlg = HardwareMatrixDialog(self)
        dlg.exec()

    def _open_singularity_dialog(self) -> None:
        """Open the Singularity Control dialog."""
        from axiom.gui.widgets.singularity_dialog import SingularityControlDialog
        dlg = SingularityControlDialog(self)
        dlg.exec()

    def _open_telemetry_dialog(self) -> None:
        """Open the Telemetry Trace observer dialog."""
        from axiom.gui.widgets.telemetry_dialog import TelemetryDialog
        dlg = TelemetryDialog(self)
        dlg.exec()

    def _open_system_hub_dialog(self) -> None:
        """Open the unified System Hub dialog."""
        from axiom.gui.widgets.system_hub_dialog import SystemHubDialog
        dlg = SystemHubDialog(self)
        dlg.exec()
