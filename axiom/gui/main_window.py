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
import os
from typing import TYPE_CHECKING
from PySide6.QtCore import Qt, QSize, Slot, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QButtonGroup, QDockWidget, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QStatusBar, QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QApplication, QSplitter, QFileDialog
from axiom.config import get_config, AuthMode
from axiom.core.shortcuts import SHORTCUTS
from axiom.gui.styles.theme_manager import get_theme_manager
from axiom.gui.widgets.swarm_pill import SwarmPill
from axiom.gui.widgets.settings_dialog import SettingsDialog
from axiom.gui.widgets.hub_dialog import AxiomHubDialog
from axiom.gui.widgets.scheduler_ui import TemporalSchedulerDialog
from axiom.services.scheduler import TemporalService
from axiom.services.sys_watchdog import SystemHealthWatchdog
from axiom.gui.widgets.synapse_graph import SynapseGraph
from axiom.memory.projects import ProjectManager
from axiom.gui.windows.project_dialog import ProjectDialog
if TYPE_CHECKING:
    from axiom.gui.bridge import AxiomBridge
logger = logging.getLogger(__name__)
_AUTH_LABELS = {AuthMode.BASIC: '🛡️ BASIC', AuthMode.AUTOPILOT: '⚡ AUTOPILOT', AuthMode.STRICT: '🔒 STRICT'}
_AUTH_COLORS = {AuthMode.BASIC: '#f59e0b', AuthMode.AUTOPILOT: '#10b981', AuthMode.STRICT: '#ef4444'}

class ChatInputEdit(QTextEdit):
    """Custom input edit that sends on Enter and adds a newline on Shift+Enter."""
    send_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                event.accept()
        else:
            super().keyPressEvent(event)

from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QComboBox, QLineEdit
import subprocess

class SettingsDrawer(QFrame):
    """Sleek dark-mode settings/swarm sidebar."""

    model_changed = Signal(str)
    connect_requested = Signal(str)   # emits the host string
    disconnect_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(0)
        self.setMinimumWidth(0)
        self.setStyleSheet("SettingsDrawer { background-color: #1A1A1A; border-left: 1px solid #333333; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # ── Title ──────────────────────────────────────────────────────── #
        title = QLabel("Settings")
        title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # ── Model Settings ─────────────────────────────────────────────── #
        model_label = QLabel("\U0001f9e0 Model Settings")
        model_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #2A2A2A;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #2A2A2A;
                color: #FFFFFF;
                selection-background-color: #3A3A3A;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(self.model_combo)
        self._populate_models()
        self.model_combo.currentTextChanged.connect(self.model_changed)

        # ── Swarm Nodes ────────────────────────────────────────────────── #
        node_label = QLabel("\U0001f310 Swarm Nodes")
        node_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0.5px; margin-top: 10px;")
        layout.addWidget(node_label)

        # Status indicator
        self._status_label = QLabel("● Disconnected")
        self._status_label.setStyleSheet("color: #ef4444; font-size: 12px;")
        layout.addWidget(self._status_label)

        node_layout = QHBoxLayout()
        node_layout.setSpacing(6)
        self.node_input = QLineEdit()
        self.node_input.setPlaceholderText("192.168.x.x:8000")
        self.node_input.setStyleSheet("""
            QLineEdit {
                background-color: #2A2A2A;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #10b981; }
        """)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self._btn_idle_style = "QPushButton { background-color: #10b981; color: #FFFFFF; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 12px; } QPushButton:hover { background-color: #059669; }"
        self._btn_connecting_style = "QPushButton { background-color: #f59e0b; color: #FFFFFF; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 12px; }"
        self._btn_connected_style = "QPushButton { background-color: #3b82f6; color: #FFFFFF; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 12px; } QPushButton:hover { background-color: #2563eb; }"
        self.connect_btn.setStyleSheet(self._btn_idle_style)
        self.connect_btn.clicked.connect(self._on_connect_clicked)

        node_layout.addWidget(self.node_input, 1)
        node_layout.addWidget(self.connect_btn)
        layout.addLayout(node_layout)

        # Node list — shows connected node
        self._node_list_label = QLabel("")
        self._node_list_label.setStyleSheet("color: #6b7280; font-size: 11px; font-style: italic;")
        self._node_list_label.setWordWrap(True)
        layout.addWidget(self._node_list_label)

        layout.addStretch()

        # ── Audio / TTS Controls ─────────────────────────────────────────── #
        audio_label = QLabel("🔉 Audio")
        audio_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0.5px;")
        layout.addWidget(audio_label)

        self._tts_toggle_btn = QPushButton("🔊  Voice Responses: ON")
        self._tts_toggle_btn.setCheckable(True)
        self._tts_toggle_btn.setChecked(True)
        self._tts_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._tts_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 600;
                text-align: left;
            }
            QPushButton:!checked {
                background-color: #374151;
                color: #9CA3AF;
            }
        """)
        self._tts_toggle_btn.toggled.connect(self._on_tts_toggled)
        layout.addWidget(self._tts_toggle_btn)

        # ── Animation ────────────────────────────────────────────────────── #
        self.anim = QPropertyAnimation(self, b"maximumWidth")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self._connected = False

    def _on_tts_toggled(self, checked: bool):
        label = "🔊  Voice Responses: ON" if checked else "🔇  Voice Responses: OFF"
        self._tts_toggle_btn.setText(label)
    
    @property
    def tts_enabled(self) -> bool:
        """Whether TTS voice responses are currently enabled."""
        return self._tts_toggle_btn.isChecked()

    # ── Private helpers ────────────────────────────────────────────────── #
    def _populate_models(self):
        """Fetch installed Ollama models and populate the dropdown."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("Auto-Select")
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                for line in lines[1:]:  # skip header row
                    parts = line.split()
                    if parts:
                        self.model_combo.addItem(parts[0])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # Ollama not installed / timed out — silently skip
        except Exception as e:
            logger.warning(f"SettingsDrawer: could not fetch ollama models: {e}")
        finally:
            self.model_combo.blockSignals(False)

    def _on_connect_clicked(self):
        if self._connected:
            self.disconnect_requested.emit()
        else:
            host = self.node_input.text().strip()
            if host:
                self.connect_btn.setText("Connecting…")
                self.connect_btn.setEnabled(False)
                self.connect_btn.setStyleSheet(self._btn_connecting_style)
                self.connect_requested.emit(host)

    # ── Public slots called by MainWindow ─────────────────────────────── #
    def on_swarm_connected(self):
        self._connected = True
        self._status_label.setText("● Connected")
        self._status_label.setStyleSheet("color: #10b981; font-size: 12px;")
        host = self.node_input.text().strip()
        self._node_list_label.setText(f"Node: {host}")
        self.connect_btn.setText("Disconnect")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setStyleSheet(self._btn_connected_style)

    def on_swarm_disconnected(self):
        self._connected = False
        self._status_label.setText("● Disconnected")
        self._status_label.setStyleSheet("color: #ef4444; font-size: 12px;")
        self._node_list_label.setText("")
        self.connect_btn.setText("Connect")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setStyleSheet(self._btn_idle_style)

    def on_swarm_error(self, msg: str):
        self._connected = False
        self._status_label.setText(f"● Error: {msg[:40]}")
        self._status_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self.connect_btn.setText("Retry")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setStyleSheet(self._btn_idle_style)

    # ── Toggle animation ──────────────────────────────────────────────── #
    def toggle(self):
        if self.maximumWidth() == 0:
            self._populate_models()   # refresh models each open
            self.anim.setStartValue(0)
            self.anim.setEndValue(300)
            self.anim.start()
        else:
            self.anim.setStartValue(self.width())
            self.anim.setEndValue(0)
            self.anim.start()

class MainWindow(QMainWindow):
    """AXIOM Desktop v6.0 LTS main application window."""

    def __init__(self, bridge: 'AxiomBridge', parent: QWidget | None=None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._streaming_bubble = None
        self._streaming_text = ''
        self.setWindowTitle('AXIOM Pro — Sovereign AI')
        self.setMinimumSize(800, 600)
        self.resize(1000, 750)
        self._theme_manager = get_theme_manager()
        
        self._project_manager = ProjectManager()
        self._current_project_id = "general"
        self._current_chat_id = None
        # Ensure the default project directory exists on first run
        if not any(p["id"] == "general" for p in self._project_manager.get_projects()):
            self._project_manager.create_project(
                title="General",
                context_text="",
                project_id="general"
            )

        from axiom.gui.widgets.modern_chat import ModernChatDisplay
        from axiom.gui.widgets.modern_sidebar import ModernSidebar

        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.sidebar = ModernSidebar(self)
        self.sidebar.new_chat_requested.connect(self._on_new_chat)
        self.sidebar.new_project_requested.connect(self._on_new_project_requested)
        self.sidebar.conversation_selected.connect(self._on_conversation_selected)
        self.sidebar.mode_changed.connect(self._on_mode_changed)
        self.sidebar.settings_btn.clicked.connect(self._show_settings)
        self.sidebar.hub_btn.clicked.connect(self._show_hub)
        self.splitter.addWidget(self.sidebar)

        self._chat_display = ModernChatDisplay(self)
        self._chat_display.input_bar.attach_btn.clicked.connect(self._on_attach_file)
        self.splitter.addWidget(self._chat_display)
        
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([280, 800])
        
        main_layout.addWidget(self.splitter, 1)
        
        self.settings_drawer = SettingsDrawer(self)
        main_layout.addWidget(self.settings_drawer)
        self._chat_display.settings_btn.clicked.connect(self.settings_drawer.toggle)

        # ── Swarm Client ──────────────────────────────────────────────── #
        from axiom.gui.swarm_client import SwarmClient
        self._swarm = SwarmClient(self)
        self._swarm.connected.connect(self.settings_drawer.on_swarm_connected)
        self._swarm.connected.connect(lambda: self._chat_display.add_bubble('assistant', '🌐 Swarm Node connected — prompts will be routed remotely.'))
        self._swarm.disconnected.connect(self.settings_drawer.on_swarm_disconnected)
        self._swarm.disconnected.connect(lambda: self._chat_display.add_bubble('assistant', '🔌 Swarm Node disconnected — falling back to local engine.'))
        self._swarm.connection_error.connect(self.settings_drawer.on_swarm_error)
        self._swarm.connection_error.connect(lambda msg: self._chat_display.add_bubble('tool', f'⚠️ Swarm connection error: {msg}'))
        self._swarm.response_complete.connect(self._on_swarm_response)
        self.settings_drawer.connect_requested.connect(self._swarm.connect_to_node)
        self.settings_drawer.disconnect_requested.connect(self._swarm.disconnect_from_node)

        # ── Model selection ────────────────────────────────────────────── #
        self.settings_drawer.model_changed.connect(self._on_model_changed)

        self._refresh_sidebar()

        self.setCentralWidget(central_widget)

        self._input = self._chat_display.input_bar.input_edit
        self._chat_display.input_bar.message_ready.connect(self._on_send)
        self._chat_display.input_bar.mic_toggled.connect(self._on_mic_toggled)
        self._connect_bridge()
        self._init_audio()
        self._init_tray()
        self._init_hotkey()
        self._register_local_shortcuts()
        self._chat_display.add_bubble('assistant', 'AXIOM v11.2')
        
        self._apply_theme()
        self._theme_manager.theme_changed.connect(self._apply_theme)

    def _apply_theme(self):
        t = self._theme_manager.theme
        self.setStyleSheet(f"QMainWindow {{ background-color: {t.colors.bg_base}; color: {t.colors.text_primary}; font-family: {t.typography.font_main}; }}")
        self.splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {t.colors.border_default}; width: {t.geometry.border_width}px; }}")

    def _show_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_hub(self):
        dialog = AxiomHubDialog(self)
        dialog.tool_installed.connect(self._on_tool_installed)
        dialog.exec()

    def _on_tool_installed(self, tool_id: str):
        if self._bridge and hasattr(self._bridge, 'send_reload_plugins'):
            self._bridge.send_reload_plugins()
        self._chat_display.add_bubble('system', f'✅ Tool "{tool_id}" installed and dynamically hot-reloaded.')

    def _on_attach_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Attach File", "", "Text Files (*.txt *.py *.md *.json *.csv);;All Files (*)"
        )
        if file_name:
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    file_content = f.read()
                current_text = self._chat_display.input_bar.input_area.toPlainText()
                new_text = f"{current_text}\n\n--- FILE: {file_name} ---\n{file_content}\n"
                self._chat_display.input_bar.input_area.setPlainText(new_text)
            except Exception as e:
                logger.error("Failed to read file: %s", e)

    def _refresh_sidebar(self) -> None:
        projects = self._project_manager.get_projects()
        data = []
        for p in projects:
            chats = self._project_manager.get_conversations(p["id"])
            data.append({"project": p, "chats": chats})
        self.sidebar.populate_projects(data)

    def _on_new_project_requested(self) -> None:
        dialog = ProjectDialog(self)
        dialog.project_created.connect(self._create_project)
        dialog.exec()

    def _create_project(self, title: str, context: str, files: list) -> None:
        self._project_manager.create_project(title=title, context_text=context, attached_files=files)
        self._refresh_sidebar()

    def _on_conversation_selected(self, project_id: str, chat_id: str) -> None:
        self._current_project_id = project_id
        self._current_chat_id = chat_id
        chat_data = self._project_manager.load_conversation(project_id, chat_id)
        
        from axiom.gui.widgets.modern_chat import ModernChatBubble
        for i in reversed(range(self._chat_display.chat_layout.count())):
            item = self._chat_display.chat_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ModernChatBubble):
                item.widget().deleteLater()
                
        if chat_data:
            if hasattr(self._chat_display, 'watermark'):
                self._chat_display.watermark.hide()
            messages = chat_data.get("messages", [])
            for msg in messages:
                self._chat_display.add_bubble(msg.get("role", "user"), msg.get("content", ""))
        else:
            if hasattr(self._chat_display, 'watermark'):
                self._chat_display.watermark.show()
            self._chat_display.add_bubble("assistant", "AXIOM v11.2")

    def _on_new_chat(self) -> None:
        # Just clear the UI, don't create an empty chat file yet
        self._current_chat_id = None
        self._refresh_sidebar()
        
        from axiom.gui.widgets.modern_chat import ModernChatBubble
        for i in reversed(range(self._chat_display.chat_layout.count())):
            item = self._chat_display.chat_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ModernChatBubble):
                item.widget().deleteLater()
        
        if hasattr(self._chat_display, 'watermark'):
            self._chat_display.watermark.show()
        self._chat_display.add_bubble("assistant", "AXIOM v11.2")

    def _on_mode_changed(self, mode: str) -> None:
        if self._bridge and hasattr(self._bridge, 'set_auth_mode'):
            self._bridge.set_auth_mode(mode)

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
            logger.info('Window hidden to system tray.')
        else:
            super().closeEvent(event)

    def force_quit(self) -> None:
        """Actually shut down the application."""
        if hasattr(self, '_swarm'):
            self._swarm.shutdown()
        if hasattr(self, '_temporal_service'):
            self._temporal_service.stop()
        if hasattr(self, '_sys_watchdog'):
            self._sys_watchdog.stop()
        if hasattr(self, '_wake_daemon') and self._wake_daemon:
            self._wake_daemon.stop()
        if hasattr(self, '_hotkey_service'):
            self._hotkey_service.stop()
        logger.info('AXIOM shutting down gracefully.')
        QApplication.quit()

    def _init_audio(self) -> None:
        """Initialize the AudioManager facade (TTS + STT) in a background thread.

        AudioManager may trigger WhisperModel loading which takes several
        seconds.  Running it on a daemon thread lets the UI paint and respond
        immediately while the model loads silently in the background.
        """
        import threading

        def _load():
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex(('127.0.0.1', 9410)) == 0:
                        logger.info("Daemon is running (port 9410 open). Skipping GUI local audio engine to prevent lock contention.")
                        self._audio = None
                        return
                        
                from axiom.core.audio import AudioManager
                self._audio = AudioManager.instance()
                logger.info('AudioManager initialized (background thread)')
            except Exception as exc:
                self._audio = None
                logger.warning('AudioManager init failed (expected if daemon owns lock): %s', exc)

        threading.Thread(target=_load, daemon=True).start()

    def _init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        tray_menu = QMenu()
        toggle_action = QAction('Show/Hide AXIOM', self)
        toggle_action.triggered.connect(lambda: self.hide() if self.isVisible() else self.show())
        tray_menu.addAction(toggle_action)
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(lambda: None)
        tray_menu.addAction(settings_action)
        quit_action = QAction('Quit AXIOM', self)
        quit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _init_hotkey(self) -> None:
        try:
            from axiom.services.hotkey_service import GlobalHotkeyService
            self._hotkey_service = GlobalHotkeyService()
            self._hotkey_service.signaler.toggle_requested.connect(
                lambda: self.hide() if self.isVisible() else self.show()
            )
            self._hotkey_service.signaler.context_summoned.connect(self._on_context_summoned)
            self._hotkey_service.signaler.vision_summoned.connect(self._on_vision_summoned)
            # New registry-driven global signals
            self._hotkey_service.signaler.start_audio.connect(self._on_global_start_audio)
            self._hotkey_service.signaler.capture_screen.connect(self._on_vision_summoned)
            self._hotkey_service.start()
        except ImportError:
            logger.error('pynput not found. Global hotkey disabled.')

    def _register_local_shortcuts(self) -> None:
        """Create QShortcut bindings for every non-global entry in SHORTCUTS."""
        actions = {
            "new_chat":       lambda: self._on_new_chat(),
            "new_project":    lambda: self._on_new_project_requested(),
            "focus_input":    lambda: self._chat_display.input_bar.input_area.setFocus(),
            "toggle_sidebar": lambda: self._toggle_sidebar(),
            "clear_chat":     lambda: self._on_clear_chat(),
            "open_settings":  lambda: self.settings_drawer.toggle(),
            "prev_chat":      lambda: self._on_prev_chat(),
            "next_chat":      lambda: self._on_next_chat(),
            # search_history: no UI hook yet — skipped gracefully
        }
        for action_id, spec in SHORTCUTS.items():
            if spec.get("global"):
                continue
            key = spec.get("default")
            if not key:
                continue
            handler = actions.get(action_id)
            if handler is None:
                continue
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(handler)
            print(f"[GUI] Registered local shortcut: {action_id} -> {key}")

    def _toggle_sidebar(self) -> None:
        """Collapse or restore the sidebar via the splitter."""
        sizes = self.splitter.sizes()
        if sizes[0] > 0:
            self.splitter.setSizes([0, sum(sizes)])
        else:
            self.splitter.setSizes([280, max(0, sum(sizes) - 280)])

    def _on_clear_chat(self) -> None:
        """Clear all bubbles from the chat view."""
        layout = self._chat_display.scroll_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_prev_chat(self) -> None:
        """Select the previous chat item in the sidebar tree."""
        self._navigate_chat(direction=-1)

    def _on_next_chat(self) -> None:
        """Select the next chat item in the sidebar tree."""
        self._navigate_chat(direction=+1)

    def _navigate_chat(self, direction: int) -> None:
        """Walk the sidebar tree by `direction` (+1 next, -1 prev).

        Project headers are not selectable (ItemIsSelectable cleared in
        populate_projects), so we skip them and only land on chat leaves.
        """
        tree = self.sidebar.tree

        # Flatten all tree items into a list in display order.
        def _flatten(parent_item=None):
            items = []
            count = parent_item.childCount() if parent_item else tree.topLevelItemCount()
            for i in range(count):
                child = parent_item.child(i) if parent_item else tree.topLevelItem(i)
                items.append(child)
                items.extend(_flatten(child))
            return items

        all_items = _flatten()
        # Keep only selectable chat leaves (project headers have ItemIsSelectable cleared).
        selectable = [
            it for it in all_items
            if bool(it.flags() & Qt.ItemFlag.ItemIsSelectable)
        ]
        if not selectable:
            return

        selected = tree.selectedItems()
        current = selected[0] if selected else None

        if current and current in selectable:
            idx = selectable.index(current)
        else:
            # Nothing selected yet — jump to first or last depending on direction.
            idx = -1 if direction > 0 else 0

        new_idx = (idx + direction) % len(selectable)
        tree.setCurrentItem(selectable[new_idx])
        tree.scrollToItem(selectable[new_idx])

    def _on_global_start_audio(self) -> None:
        """Activate the mic from a global hotkey — show window then start STT."""
        self.show()
        self.activateWindow()
        self.raise_()
        # Simulate a mic toggle-on if the button exists
        if hasattr(self._chat_display, 'input_bar'):
            mic_btn = self._chat_display.input_bar.mic_btn
            if not mic_btn.isChecked():
                mic_btn.click()

    @Slot()
    def _on_context_summoned(self) -> None:
        """Fetch clipboard, inject into prompt, and summon."""
        from axiom.services.clipboard_service import ClipboardService
        clipboard_text = ClipboardService.get_text()
        if clipboard_text:
            injection = f'\\n```\\n{clipboard_text}\\n```\\n'
            self._input.setText(injection)
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
        path = VisionService.capture_screen()
        if path and os.path.exists(path):
            self._chat_display.attach_image(path)
        self.show()
        self.activateWindow()
        self.raise_()
        if hasattr(self, '_input'):
            self._input.setFocus()

    def _check_updates_async(self):
        import asyncio
        from axiom.updater.manager import UpdateManager

        async def _check():
            mgr = UpdateManager()
            res = await mgr.check_for_updates()
            if res.get('update_available'):
                self._status_updates.setText(f"[ Updates: {res['latest_version']} Available ]")
                self._status_updates.setStyleSheet('font-weight: 600; color: #f38ba8; padding-right: 10px;')
                from PySide6.QtCore import QMetaObject, Q_ARG, Qt
                QMetaObject.invokeMethod(self, '_prompt_update', Qt.ConnectionType.QueuedConnection, Q_ARG(str, res['latest_version']))
            else:
                self._status_updates.setText('[ Updates: Up-to-Date ]')
                self._status_updates.setStyleSheet('font-weight: 600; color: #a6e3a1; padding-right: 10px;')
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_check(), loop)
        else:
            asyncio.run(_check())

    def _connect_bridge(self) -> None:
        if not self._bridge:
            return
        
        # Core Chat Event
        if hasattr(self._bridge, 'chat_event'):
            self._bridge.chat_event.connect(lambda role, text: self._chat_display.add_bubble(role, text))
            
        # Standard Events
        self._bridge.token_received.connect(self._on_token)
        self._bridge.response_finished.connect(self._on_response_finished)
        self._bridge.telemetry_updated.connect(self._on_telemetry)
        self._bridge.error_occurred.connect(self._on_error)
        self._bridge.request_gui_auth.connect(self._on_request_gui_auth)
        self._bridge.swarm_status_changed.connect(self._on_swarm_status_changed)
        self._bridge.swarm_agent_started.connect(self._on_swarm_started)
        self._bridge.swarm_agent_token.connect(self._on_swarm_token)
        self._bridge.swarm_agent_completed.connect(self._on_swarm_completed)
        self._bridge.axiomfs_status.connect(self._on_axiomfs_status)
        self._bridge.governor_approval_requested.connect(self._on_approval_requested)
        pass
        self._bridge.ui_widget_generated.connect(self._on_widget_generated)
        pass

    def _on_axiomfs_status(self, status: str) -> None:
        self._status_axiomfs.setText(f'AxiomFS: {status}')

    def _on_daemon_connection_changed(self, state: str) -> None:
        if state == 'connected':
            self._status_daemon.setText('⚡ Daemon: Connected')
            self._status_daemon.setStyleSheet('color: #10b981; font-weight: bold; padding-left: 5px; padding-right: 15px;')
        elif state == 'connecting':
            self._status_daemon.setText('⏳ Daemon: Starting...')
            self._status_daemon.setStyleSheet('color: #f59e0b; font-weight: bold; padding-left: 5px; padding-right: 15px;')
        else:
            self._status_daemon.setText('🔌 Daemon: Disconnected')
            self._status_daemon.setStyleSheet('color: #f87171; font-weight: bold; padding-left: 5px; padding-right: 15px;')

    @Slot(dict)
    def _on_swarm_status_changed(self, payload: dict) -> None:
        pass

    def _on_request_gui_auth(self, tool_name: str, arguments: str, ctx: dict) -> None:
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle('[SECURITY APPROVAL REQUIRED]')
        msg.setText(f'AXIOM requests permission to execute an external action:\\n\\nTool: {tool_name}\\nCommand / Args: {arguments}')
        msg.setIcon(QMessageBox.Icon.Warning)
        allow_btn = msg.addButton('Allow Execution', QMessageBox.ButtonRole.AcceptRole)
        allow_btn.setStyleSheet('background-color: #10b981; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;')
        deny_btn = msg.addButton('Deny Action', QMessageBox.ButtonRole.RejectRole)
        deny_btn.setStyleSheet('background-color: #ef4444; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;')
        msg.setStyleSheet('QMessageBox { background-color: #1a1a1f; color: #d4d4d8; } QLabel { color: #d4d4d8; font-family: monospace; }')
        msg.exec()
        ctx['result']['granted'] = msg.clickedButton() == allow_btn
        ctx['event'].set()

    def _on_submit_background_task(self, prompt: str) -> None:
        self._chat_display.add_bubble('user', f'[SYSTEM/BACKGROUND] {prompt}')
        self._streaming_text = ''
        self._streaming_bubble = self._chat_display.add_bubble('assistant', '')
        self._active_swarm_pill = None
        self._bridge.submit_task(prompt)

    @Slot()
    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        attachment_path = getattr(self._chat_display, '_current_attachment_path', None)
        
        if not text and not attachment_path:
            return
        
        self._input.clear()
        
        # Build the routing payload
        if attachment_path:
            import base64
            try:
                with open(attachment_path, 'rb') as f:
                    raw = f.read()
                b64 = base64.b64encode(raw).decode('utf-8')
                # Detect mime type from extension
                ext = attachment_path.rsplit('.', 1)[-1].lower()
                mime = 'image/png' if ext == 'png' else 'image/jpeg'
                multimodal_payload = [
                    {"type": "text", "text": text or "Describe this image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                ]
                route_payload = multimodal_payload  # list-style OpenAI content
                display_text = f'{text}\\n\\n*[Image: {os.path.basename(attachment_path)}]*' if text else f'*[Image: {os.path.basename(attachment_path)}]*'
            except Exception as e:
                logger.error(f'Failed to encode attachment: {e}')
                route_payload = text
                display_text = text
            finally:
                self._chat_display.clear_attachment()
        else:
            route_payload = text
            display_text = text
        
        self._chat_display.add_bubble('user', display_text.strip())
        self._streaming_text = ''
        self._streaming_bubble = self._chat_display.add_bubble('assistant', '⏳ Routing to Swarm Node…' if self._swarm.is_connected else '')
        self._active_swarm_pill = None

        # Ensure we have a conversation file created before saving
        if hasattr(self, '_project_manager'):
            if not self._current_chat_id:
                self._current_chat_id = self._project_manager.create_conversation(self._current_project_id, "New Chat")
            self._project_manager.append_message(self._current_project_id, self._current_chat_id, {
                'role': 'user',
                'content': display_text.strip()
            })
            self._refresh_sidebar()

        # Route: swarm node first, local engine as fallback
        if self._swarm.is_connected:
            sent = self._swarm.send_prompt(text if not attachment_path else str(route_payload))
            if not sent:
                self._streaming_bubble.set_text('')
                self._bridge.submit_task(route_payload)
        else:
            self._bridge.submit_task(route_payload)

    @Slot(str)
    def _on_swarm_response(self, response: str) -> None:
        """Handle the final response from a remote AXIOM Swarm Node."""
        if self._streaming_bubble:
            self._streaming_bubble.set_text(response)
            self._streaming_bubble = None
        self._streaming_text = ''
        self._chat_display._scroll_to_bottom()
        # Persist to local JSON history
        if hasattr(self, '_project_manager') and self._current_chat_id:
            self._project_manager.append_message(self._current_project_id, self._current_chat_id, {
                'role': 'assistant',
                'content': response
            })
        # TTS — respects the speaker toggle in SettingsDrawer
        audio = getattr(self, '_audio', None)
        if audio and self.settings_drawer.tts_enabled and self._bridge:
            import asyncio
            asyncio.run_coroutine_threadsafe(audio.speak(response), self._bridge._loop)

    @Slot(str)
    def _on_model_changed(self, model: str) -> None:
        """Apply model selection from the Settings Drawer dropdown."""
        if model == 'Auto-Select':
            return
        try:
            from axiom.config import get_config
            cfg = get_config()
            cfg.ollama_model = model
            if self._bridge and hasattr(self._bridge, '_engine'):
                llm = getattr(self._bridge._engine, 'ollama', None)
                if llm and hasattr(llm, 'config'):
                    llm.config.model = model
            logger.info(f'Model switched to: {model}')
            self._chat_display.add_bubble('assistant', f'🔄 Model switched to **{model}**')
        except Exception as e:
            logger.warning(f'Could not apply model change: {e}')

    @Slot(bool)
    def _on_mic_toggled(self, listening: bool) -> None:
        """Handle push-to-talk: start/stop recording and transcribe."""
        audio = getattr(self, '_audio', None)
        mic_btn = self._chat_display.input_bar.mic_btn
        if not audio or not audio.has_stt:
            # No STT available: uncheck the button visually and bail
            if mic_btn and mic_btn.isChecked():
                mic_btn.blockSignals(True)
                mic_btn.setChecked(False)
                mic_btn.blockSignals(False)
            return

        if listening:
            audio.start_listening()
            self._input.setPlaceholderText('Listening...')
        else:
            self._input.setPlaceholderText('Transcribing...')
            audio_data = audio.stop_listening()
            import asyncio

            async def _transcribe():
                text = await audio.transcribe(audio_data)
                from PySide6.QtCore import QMetaObject, Q_ARG
                QMetaObject.invokeMethod(
                    self, '_on_transcription_complete',
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, text)
                )
            if self._bridge:
                asyncio.run_coroutine_threadsafe(_transcribe(), self._bridge._loop)

    @Slot(str)
    def _on_transcription_complete(self, text: str) -> None:
        self._input.setPlaceholderText('Ask AXIOM anything… (Enter to send, Shift+Enter for new line)')
        if text:
            current = self._input.toPlainText()
            self._input.setPlainText((current + ' ' + text).strip())

    @Slot()
    def _on_wake_word(self) -> None:
        self._chat_display.add_bubble('user', '[Wake Word Detected] Listening...')
        pass

    @Slot(str)
    def _on_token(self, token: str) -> None:
        if self._streaming_bubble:
            self._streaming_text += token
            # Do NOT html.escape here — _basic_markdown in the bubble already handles escaping
            self._streaming_bubble.set_text(self._streaming_text)
            self._chat_display._scroll_to_bottom()

    @Slot(str, str)
    def _on_tool_status(self, tool_id: str, status: str) -> None:
        pass

    def _on_swarm_started(self, agent_name: str, task: str) -> None:
        if hasattr(self, '_swarm_hud'):
            self._chat_display.swarm_hud.add_pill(agent_name, task)

    @Slot(str, str)
    def _on_swarm_token(self, agent_name: str, chunk: str) -> None:
        if hasattr(self, '_swarm_hud'):
            self._chat_display.swarm_hud.update_pill(agent_name, chunk)

    @Slot(str, str)
    def _on_swarm_completed(self, agent_name: str, result: str) -> None:
        if hasattr(self, '_swarm_hud'):
            self._chat_display.swarm_hud.remove_pill(agent_name)

    @Slot(dict)
    def _on_telemetry(self, data: dict) -> None:
        pass

    def _on_response_finished(self, text: str) -> None:
        if self._streaming_bubble and (not self._streaming_text):
            # Do NOT html.escape — _basic_markdown already escapes safely
            self._streaming_bubble.set_text(text)
        self._streaming_bubble = None
        self._streaming_text = ''
        self._chat_display._scroll_to_bottom()
        
        # Save to JSON backend
        if hasattr(self, '_project_manager') and self._current_chat_id:
            self._project_manager.append_message(self._current_project_id, self._current_chat_id, {
                "role": "assistant",
                "content": text
            })
            self._refresh_sidebar()
            
        if hasattr(self, '_tts') and self._tts:
            import asyncio
            asyncio.run_coroutine_threadsafe(self._tts.speak(text), self._bridge._loop)

    @Slot(str)
    def _on_error(self, message: str) -> None:
        if self._streaming_bubble:
            self._streaming_bubble.deleteLater()
            self._streaming_bubble = None
            self._streaming_text = ''
        self._chat_display.add_bubble('tool', f'⚠️ {message}')
        self._chat_display._scroll_to_bottom()

    @Slot(bool, float)
    def _on_ollama_status_changed(self, is_online: bool, latency: float) -> None:
        if is_online:
            self._ollama_status_label.setText(f'🟢 Ollama: Online ({latency:.0f}ms)')
            self._ollama_status_label.setStyleSheet('font-weight: 600; font-size: 13px; color: #10b981;')
            self._ollama_start_btn.setVisible(False)
            self._ollama_start_action.setVisible(False)
            self._bridge.refresh_models()
        else:
            self._ollama_status_label.setText('🔴 Ollama: Offline')
            self._ollama_status_label.setStyleSheet('font-weight: 600; font-size: 13px; color: #ef4444;')
            self._ollama_start_btn.setVisible(True)
            self._ollama_start_action.setVisible(True)
            if getattr(self, '_first_ollama_ping', True):
                from axiom.config import get_config
                if get_config().auto_ollama_start:
                    self._on_ollama_start_clicked()
        self._first_ollama_ping = False

    @Slot(str, dict)
    @Slot(dict)
    def _on_widget_generated(self, payload: dict) -> None:
        widget_type = payload.get('widget_type', 'unknown')
        spec = payload.get('spec', {})
        try:
            from axiom.gui.widgets.sandbox_container import SandboxContainer
            sandbox = SandboxContainer(widget_type, spec, self)
            count = self._chat_display.chat_layout.count()
            self._chat_display.chat_layout.insertWidget(count - 1, sandbox)
            self._chat_display._scroll_to_bottom()
        except Exception as e:
            print(f'Failed to render widget: {e}')

    def _on_approval_requested(self, tool_name: str, arguments: dict) -> None:
        from axiom.gui.widgets.governor_dialog import ExecutionGateDialog
        dlg = ExecutionGateDialog(tool_name, arguments, self)
        approved = dlg.exec_() == QDialog.Accepted
        self._bridge.send_approval_response(tool_name, approved)

    @Slot()
    def _on_settings_updated(self):
        import axiom.gui.app as gui_app
        from PySide6.QtWidgets import QApplication
        from axiom.config import get_config
        gui_app._load_stylesheet(QApplication.instance())
        config = get_config()
        if config.model_selection_mode == 'manual':
            self.update_model_label(f'{config.ollama_model} (Manual)')
        else:
            self.update_model_label(config.ollama_model)

    @Slot()
    def _on_ollama_start_clicked(self) -> None:
        self._ollama_status_label.setText('🟡 Starting Daemon...')
        self._ollama_status_label.setStyleSheet('font-weight: 600; font-size: 13px; color: #fbbf24;')
        self._ollama_start_btn.setEnabled(False)
        self._ollama_monitor.trigger_rapid_polling()
        import threading

        def _spawn():
            success = self._ollama_monitor.spawn_ollama_service()
            if not success:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._ollama_start_btn.setEnabled(True))
        threading.Thread(target=_spawn, daemon=True).start()

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        self._expert_btn.setChecked(visible)
        self._expert_btn.setText(f"⚙️ Expert Mode: {('ON' if visible else 'OFF')}")
        
    def update_model_label(self, model: str) -> None:
        pass
