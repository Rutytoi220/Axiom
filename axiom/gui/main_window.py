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
from PySide6.QtWidgets import QButtonGroup, QDockWidget, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QStatusBar, QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget, QSystemTrayIcon, QMenu, QApplication
from axiom.config import get_config, AuthMode
from axiom.gui.widgets.swarm_pill import SwarmPill
from axiom.gui.widgets.settings_dialog import SettingsDialog
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
        self.setStyleSheet('QMainWindow { background-color: #121212; }')
        
        self._project_manager = ProjectManager()
        self._current_project_id = "general"
        self._current_chat_id = None

        from axiom.gui.widgets.modern_chat import ModernChatDisplay
        from axiom.gui.widgets.modern_sidebar import ModernSidebar

        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.sidebar = ModernSidebar(self)
        self.sidebar.new_chat_requested.connect(self._on_new_chat)
        self.sidebar.new_project_requested.connect(self._on_new_project_requested)
        self.sidebar.conversation_selected.connect(self._on_conversation_selected)
        self.sidebar.mode_changed.connect(self._on_mode_changed)
        main_layout.addWidget(self.sidebar)

        self._chat_display = ModernChatDisplay(self)
        main_layout.addWidget(self._chat_display, 1)
        
        self._refresh_sidebar()

        self.setCentralWidget(central_widget)

        self._input = self._chat_display.input_bar.input_edit
        self._chat_display.input_bar.message_ready.connect(self._on_send)
        self._connect_bridge()
        self._init_audio()
        self._init_tray()
        self._init_hotkey()
        self._chat_display.add_bubble('assistant', '⚡ AXIOM Pro Online.')

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
            self._chat_display.logo_widget.hide()
            messages = chat_data.get("messages", [])
            for msg in messages:
                self._chat_display.add_bubble(msg.get("role", "user"), msg.get("content", ""))
        else:
            self._chat_display.logo_widget.show()
            self._chat_display.add_bubble("assistant", "⚡ AXIOM Pro Online.")

    def _on_new_chat(self) -> None:
        chat_id = self._project_manager.create_conversation(self._current_project_id, "New Chat")
        self._current_chat_id = chat_id
        self._refresh_sidebar()
        
        from axiom.gui.widgets.modern_chat import ModernChatBubble
        for i in reversed(range(self._chat_display.chat_layout.count())):
            item = self._chat_display.chat_layout.itemAt(i)
            if item.widget() and isinstance(item.widget(), ModernChatBubble):
                item.widget().deleteLater()
        self._chat_display.logo_widget.show()
        self._chat_display.add_bubble("assistant", "⚡ AXIOM Pro Online.")

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
        from axiom.gui.config_manager import get_ui_config_manager
        self._voice_mode = get_ui_config_manager().load().voice_mode
        self._tts = None
        self._stt = None
        self._recorder = None
        self._wake_daemon = None
        try:
            from axiom.audio.tts import TextToSpeechEngine
            self._tts = TextToSpeechEngine.instance()
        except Exception as e:
            logger.error(f'TTS init failed: {e}')
        try:
            from axiom.audio.stt import WhisperTranscriber, AudioRecorder, WakeWordDaemon
            self._stt = WhisperTranscriber.instance()
            self._recorder = AudioRecorder()
            if self._voice_mode == 'wake_word':
                self._wake_daemon = WakeWordDaemon(self)
                self._wake_daemon.wake_word_detected.connect(self._on_wake_word)
                self._wake_daemon.start()
        except Exception as e:
            logger.error(f'STT init failed: {e}')

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
            self._hotkey_service.signaler.toggle_requested.connect(lambda: self.hide() if self.isVisible() else self.show())
            self._hotkey_service.signaler.context_summoned.connect(self._on_context_summoned)
            self._hotkey_service.signaler.vision_summoned.connect(self._on_vision_summoned)
            self._hotkey_service.start()
        except ImportError:
            logger.error('pynput not found. Global hotkey disabled.')

    @Slot()
    def _on_context_summoned(self) -> None:
        """Fetch clipboard, inject into prompt, and summon."""
        from axiom.services.clipboard_service import ClipboardService
        clipboard_text = ClipboardService.get_text()
        if clipboard_text:
            injection = f'\n```\n{clipboard_text}\n```\n'
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
        msg.setText(f'AXIOM requests permission to execute an external action:\n\nTool: {tool_name}\nCommand / Args: {arguments}')
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
        display_text = text
        has_attachment = hasattr(self, '_current_attachment') and self._current_attachment
        if not text and (not has_attachment):
            return
        if has_attachment:
            import base64
            try:
                with open(self._current_attachment, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                text += f'\n\n![screenshot](data:image/png;base64,{b64})'
                display_text = f'{display_text}\n\n*[Attached Screen Capture]*' if display_text else '*[Attached Screen Capture]*'
            except Exception as e:
                logger.error(f'Failed to read attachment: {e}')
            self._attachment_preview.hide()
            self._current_attachment = None
        self._input.clear()
        self._chat_display.add_bubble('user', display_text.strip())
        self._streaming_text = ''
        self._streaming_bubble = self._chat_display.add_bubble('assistant', '')
        self._active_swarm_pill = None
        self._bridge.submit_task(text)

    @Slot()
    def _on_mic_toggled(self) -> None:
        if not self._mic_btn or not self._recorder or (not self._stt):
            return
        if self._mic_btn.isChecked():
            self._mic_btn.setStyleSheet('background-color: #ef4444; color: white; border: 1px solid #ef4444; border-radius: 8px; font-size: 18px;')
            self._input.setPlaceholderText('Listening...')
            self._recorder.start_recording()
        else:
            self._mic_btn.setStyleSheet('background-color: #161B22; border: 1px solid #30363D; border-radius: 8px; font-size: 18px;')
            self._input.setPlaceholderText('Transcribing...')
            audio_data = self._recorder.stop_recording()
            import asyncio

            async def _transcribe():
                text = await self._stt.transcribe(audio_data)
                from PySide6.QtCore import QMetaObject, Q_ARG, Qt
                QMetaObject.invokeMethod(self, '_on_transcription_complete', Qt.ConnectionType.QueuedConnection, Q_ARG(str, text))
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
            self._streaming_bubble.set_text(html.escape(self._streaming_text))
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
            self._streaming_bubble.set_text(html.escape(text))
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
