import re

def refactor_main_window():
    with open('axiom/gui/main_window.py', 'r') as f:
        content = f.read()

    # SettingsDrawer background
    content = re.sub(r'self\.setStyleSheet\("SettingsDrawer.*?\"\)', 'self.setObjectName("surface")', content)
    
    # Title
    content = re.sub(r'title\.setStyleSheet\("color: #FFFFFF; font-size: 18px; font-weight: bold; margin-bottom: 10px;"\)', 'title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")', content)
    
    # model_label
    content = re.sub(r'model_label\.setStyleSheet\("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0\.5px;"\)', 'model_label.setProperty("status", "muted"); model_label.setStyleSheet("font-size: 13px; font-weight: 600; letter-spacing: 0.5px;")', content)
    
    # model_combo
    content = re.sub(r'self\.model_combo\.setStyleSheet\("""\s*QComboBox \{.*?\n\s*\}\s*"""\)', '', content, flags=re.DOTALL)
    
    # node_label
    content = re.sub(r'node_label\.setStyleSheet\("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0\.5px; margin-top: 10px;"\)', 'node_label.setProperty("status", "muted"); node_label.setStyleSheet("font-size: 13px; font-weight: 600; letter-spacing: 0.5px; margin-top: 10px;")', content)
    
    # status_label
    content = re.sub(r'self\._status_label\.setStyleSheet\("color: #ef4444; font-size: 12px;"\)', 'self._status_label.setProperty("status", "danger"); self._status_label.setStyleSheet("font-size: 12px;")', content)
    content = re.sub(r'self\._status_label\.setStyleSheet\("color: #10b981; font-size: 12px;"\)', 'self._status_label.setProperty("status", "success"); self._status_label.style().unpolish(self._status_label); self._status_label.style().polish(self._status_label)', content)
    content = re.sub(r'self\._status_label\.setStyleSheet\("color: #ef4444; font-size: 12px;"\)', 'self._status_label.setProperty("status", "danger"); self._status_label.style().unpolish(self._status_label); self._status_label.style().polish(self._status_label)', content)
    content = re.sub(r'self\._status_label\.setStyleSheet\("color: #f59e0b; font-size: 12px;"\)', 'self._status_label.setProperty("status", "warning"); self._status_label.style().unpolish(self._status_label); self._status_label.style().polish(self._status_label)', content)
    
    # node_input
    content = re.sub(r'self\.node_input\.setStyleSheet\("""\s*QLineEdit \{.*?\n\s*\}\s*QLineEdit:focus \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    
    # connect_btn
    content = re.sub(r'self\._btn_idle_style = ".*?"\n', '', content)
    content = re.sub(r'self\._btn_connecting_style = ".*?"\n', '', content)
    content = re.sub(r'self\._btn_connected_style = ".*?"\n', '', content)
    content = re.sub(r'self\.connect_btn\.setStyleSheet\(self\._btn_idle_style\)', 'self.connect_btn.setProperty("status", "")\n        self.connect_btn.style().unpolish(self.connect_btn)\n        self.connect_btn.style().polish(self.connect_btn)', content)
    content = re.sub(r'self\.connect_btn\.setStyleSheet\(self\._btn_connecting_style\)', 'self.connect_btn.setProperty("status", "warning")\n                self.connect_btn.style().unpolish(self.connect_btn)\n                self.connect_btn.style().polish(self.connect_btn)', content)
    content = re.sub(r'self\.connect_btn\.setStyleSheet\(self\._btn_connected_style\)', 'self.connect_btn.setProperty("status", "active")\n        self.connect_btn.style().unpolish(self.connect_btn)\n        self.connect_btn.style().polish(self.connect_btn)', content)
    
    # node_list_label
    content = re.sub(r'self\._node_list_label\.setStyleSheet\("color: #6b7280; font-size: 11px; font-style: italic;"\)', 'self._node_list_label.setProperty("status", "muted"); self._node_list_label.setStyleSheet("font-size: 11px; font-style: italic;")', content)
    
    # audio_label
    content = re.sub(r'audio_label\.setStyleSheet\("color: #a0a0a0; font-size: 13px; font-weight: 600; letter-spacing: 0\.5px;"\)', 'audio_label.setProperty("status", "muted"); audio_label.setStyleSheet("font-size: 13px; font-weight: 600; letter-spacing: 0.5px;")', content)
    
    # _tts_toggle_btn
    content = re.sub(r'self\._tts_toggle_btn\.setStyleSheet\("""\s*QPushButton \{.*?\n\s*\}\s*QPushButton:hover \{.*?\}\s*QPushButton:checked \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    content = re.sub(r'self\._tts_toggle_btn\.setStyleSheet\(\'background-color: #3b82f6.*?\)', 'self._tts_toggle_btn.setProperty("status", "active"); self._tts_toggle_btn.style().unpolish(self._tts_toggle_btn); self._tts_toggle_btn.style().polish(self._tts_toggle_btn)', content)
    content = re.sub(r'self\._tts_toggle_btn\.setStyleSheet\(\'background-color: #ef4444.*?\)', 'self._tts_toggle_btn.setProperty("status", "danger"); self._tts_toggle_btn.style().unpolish(self._tts_toggle_btn); self._tts_toggle_btn.style().polish(self._tts_toggle_btn)', content)
    
    # central_widget
    content = re.sub(r'central_widget\.setStyleSheet\("background: transparent;"\)', '', content)
    
    # startup_status
    content = re.sub(r'self\._startup_status\.setStyleSheet\("color: #f59e0b; font-size: 12px; font-weight: bold; padding-left: 10px;"\)', 'self._startup_status.setProperty("status", "warning"); self._startup_status.setStyleSheet("font-size: 12px; font-weight: bold; padding-left: 10px;")', content)
    content = re.sub(r'self\._startup_status\.setStyleSheet\("color: #10b981; font-size: 12px; font-weight: bold; padding-left: 10px;"\)', 'self._startup_status.setProperty("status", "success")\n                self._startup_status.style().unpolish(self._startup_status)\n                self._startup_status.style().polish(self._startup_status)', content)
    content = re.sub(r'self\._startup_status\.setStyleSheet\("color: #ef4444; font-size: 12px; font-weight: bold; padding-left: 10px;"\)', 'self._startup_status.setProperty("status", "danger")\n                self._startup_status.style().unpolish(self._startup_status)\n                self._startup_status.style().polish(self._startup_status)', content)

    # status_daemon
    content = re.sub(r'self\._status_daemon\.setStyleSheet\(\'color: #10b981; font-weight: bold; padding-left: 5px; padding-right: 15px;\'\)', 'self._status_daemon.setProperty("status", "success")\n            self._status_daemon.style().unpolish(self._status_daemon)\n            self._status_daemon.style().polish(self._status_daemon)', content)
    content = re.sub(r'self\._status_daemon\.setStyleSheet\(\'color: #f59e0b; font-weight: bold; padding-left: 5px; padding-right: 15px;\'\)', 'self._status_daemon.setProperty("status", "warning")\n            self._status_daemon.style().unpolish(self._status_daemon)\n            self._status_daemon.style().polish(self._status_daemon)', content)
    content = re.sub(r'self\._status_daemon\.setStyleSheet\(\'color: #f87171; font-weight: bold; padding-left: 5px; padding-right: 15px;\'\)', 'self._status_daemon.setProperty("status", "danger")\n            self._status_daemon.style().unpolish(self._status_daemon)\n            self._status_daemon.style().polish(self._status_daemon)', content)

    # QMainWindow global styles
    content = re.sub(r'self\.setStyleSheet\(f"QMainWindow \{\{.*?\}\}"\)\n', '', content, flags=re.DOTALL)
    content = re.sub(r'self\.splitter\.setStyleSheet\(f"QSplitter::handle \{\{.*?\}\}"\)\n', '', content, flags=re.DOTALL)

    # status_updates
    content = re.sub(r'self\._status_updates\.setStyleSheet\(\'font-weight: 600; color: #f38ba8; padding-right: 10px;\'\)', 'self._status_updates.setProperty("status", "danger"); self._status_updates.style().unpolish(self._status_updates); self._status_updates.style().polish(self._status_updates)', content)
    content = re.sub(r'self\._status_updates\.setStyleSheet\(\'font-weight: 600; color: #a6e3a1; padding-right: 10px;\'\)', 'self._status_updates.setProperty("status", "success"); self._status_updates.style().unpolish(self._status_updates); self._status_updates.style().polish(self._status_updates)', content)

    # msg box
    content = re.sub(r'allow_btn\.setStyleSheet\(\'background-color: #10b981; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;\'\)', 'allow_btn.setProperty("status", "success")', content)
    content = re.sub(r'deny_btn\.setStyleSheet\(\'background-color: #ef4444; color: white; font-weight: bold; border: none; padding: 6px 12px; border-radius: 4px;\'\)', 'deny_btn.setProperty("status", "danger")', content)
    content = re.sub(r'msg\.setStyleSheet\(\'QMessageBox \{ background-color: #1a1a1f; color: #d4d4d8; \} QLabel \{ color: #d4d4d8; font-family: monospace; \}\'\)', '', content)

    # ollama_status
    content = re.sub(r'self\._ollama_status_label\.setStyleSheet\(\'font-weight: 600; font-size: 13px; color: #10b981;\'\)', 'self._ollama_status_label.setProperty("status", "success"); self._ollama_status_label.style().unpolish(self._ollama_status_label); self._ollama_status_label.style().polish(self._ollama_status_label)', content)
    content = re.sub(r'self\._ollama_status_label\.setStyleSheet\(\'font-weight: 600; font-size: 13px; color: #ef4444;\'\)', 'self._ollama_status_label.setProperty("status", "danger"); self._ollama_status_label.style().unpolish(self._ollama_status_label); self._ollama_status_label.style().polish(self._ollama_status_label)', content)
    content = re.sub(r'self\._ollama_status_label\.setStyleSheet\(\'font-weight: 600; font-size: 13px; color: #fbbf24;\'\)', 'self._ollama_status_label.setProperty("status", "warning"); self._ollama_status_label.style().unpolish(self._ollama_status_label); self._ollama_status_label.style().polish(self._ollama_status_label)', content)

    with open('axiom/gui/main_window.py', 'w') as f:
        f.write(content)

def refactor_hud():
    with open('axiom/gui/hud.py', 'r') as f:
        content = f.read()

    # container
    content = re.sub(r'container\.setStyleSheet\("""\s*QFrame \{.*?\n\s*\}\s*"""\)', 'container.setObjectName("surface")', content, flags=re.DOTALL)
    
    # input_field
    content = re.sub(r'self\.input_field\.setStyleSheet\("""\s*QLineEdit \{.*?\n\s*\}\s*"""\)', '', content, flags=re.DOTALL)
    
    # dictate_btn
    content = re.sub(r'self\.dictate_btn\.setStyleSheet\("""\s*QPushButton \{.*?\n\s*\}\s*QPushButton:hover \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    content = re.sub(r'self\.dictate_btn\.setStyleSheet\("QPushButton \{ background-color: #f38ba8; color: #11111b; border-radius: 6px; padding: 5px 10px; font-weight: bold; \}"\)', 'self.dictate_btn.setProperty("status", "danger"); self.dictate_btn.style().unpolish(self.dictate_btn); self.dictate_btn.style().polish(self.dictate_btn)', content)
    content = re.sub(r'self\.dictate_btn\.setStyleSheet\("QPushButton \{ background-color: #f9e2af; color: #11111b; border-radius: 6px; padding: 5px 10px; font-weight: bold; \}"\)', 'self.dictate_btn.setProperty("status", "warning"); self.dictate_btn.style().unpolish(self.dictate_btn); self.dictate_btn.style().polish(self.dictate_btn)', content)

    # crop_btn, paste_btn, mesh_sync_btn
    content = re.sub(r'self\.crop_btn\.setStyleSheet\("""\s*QPushButton \{.*?\n\s*\}\s*QPushButton:hover \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    content = re.sub(r'self\.paste_btn\.setStyleSheet\("""\s*QPushButton \{.*?\n\s*\}\s*QPushButton:hover \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    content = re.sub(r'self\.mesh_sync_btn\.setStyleSheet\("""\s*QPushButton \{.*?\n\s*\}\s*QPushButton:hover \{.*?\}\s*QPushButton:disabled \{.*?\}\s*"""\)', '', content, flags=re.DOTALL)
    
    # output_area
    content = re.sub(r'self\.output_area\.setStyleSheet\("""\s*QTextEdit \{.*?\n\s*\}\s*"""\)', '', content, flags=re.DOTALL)

    with open('axiom/gui/hud.py', 'w') as f:
        f.write(content)

def refactor_oobe():
    with open('axiom/gui/widgets/oobe_wizard.py', 'r') as f:
        content = f.read()
    
    # We strip all setStyleSheet that inject colors. I'll just strip the whole strings if they contain `#`.
    content = re.sub(r'setStyleSheet\(.*?#[a-fA-F0-9]{3,6}.*?\)', 'setStyleSheet("")', content, flags=re.DOTALL)
    
    with open('axiom/gui/widgets/oobe_wizard.py', 'w') as f:
        f.write(content)

refactor_main_window()
refactor_hud()
refactor_oobe()
