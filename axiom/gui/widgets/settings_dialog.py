from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QCheckBox
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        
        self.setObjectName("settings_dialog")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(16)
        
        # Title
        title_label = QLabel("System Settings")
        title_label.setObjectName("settings_title_label")
        self.layout.addWidget(title_label)
        
        # Mock Model Selector
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("settings_model_combo")
        self.model_combo.addItems(["qwen2.5:1.5b", "qwen3:8b"])
        self.layout.addWidget(self.model_combo)
        
        from axiom.config import get_config
        config = get_config()
        
        self.plugins_checkbox = QCheckBox("Enable Third-Party Plugins")
        self.plugins_checkbox.setObjectName("settings_checkbox")
        self.plugins_checkbox.setChecked(getattr(config, 'allow_third_party_plugins', False))
        
        self.plugins_warning = QLabel("DANGER: Allowing third-party plugins executes unverified Python code on your machine.")
        self.plugins_warning.setObjectName("danger_warning_label")
        self.plugins_warning.setProperty("status", "danger")
        self.plugins_warning.style().unpolish(self.plugins_warning)
        self.plugins_warning.style().polish(self.plugins_warning)
        self.plugins_warning.setWordWrap(True)
        
        self.layout.addWidget(self.plugins_checkbox)
        self.layout.addWidget(self.plugins_warning)
        
        # Persona Selector
        self.persona_combo = QComboBox()
        self.persona_combo.setObjectName("settings_persona_combo")
        from axiom.core.persona import PERSONA_PRESETS
        self.persona_combo.addItems(list(PERSONA_PRESETS.keys()))
        current_persona = getattr(config, 'persona_key', 'default')
        if current_persona in PERSONA_PRESETS:
            self.persona_combo.setCurrentText(current_persona)
        
        self.layout.addWidget(QLabel("Agent Persona:"))
        self.layout.addWidget(self.persona_combo)
        
        # Wake Word Toggle
        self.wake_word_checkbox = QCheckBox("🎙️ Always-On Wake Word ('hey jarvis')")
        self.wake_word_checkbox.setObjectName("settings_checkbox_wakeword")
        self.wake_word_checkbox.setChecked(getattr(config, 'wake_word_enabled', False))
        self.layout.addWidget(self.wake_word_checkbox)
        
        self.layout.addStretch(1)
        
        # Button Box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.layout.addWidget(self.button_box)
        
    def accept(self):
        from axiom.config import get_config
        config = get_config()
        config.allow_third_party_plugins = self.plugins_checkbox.isChecked()
        config.wake_word_enabled = self.wake_word_checkbox.isChecked()
        
        config.persona_key = self.persona_combo.currentText()
        from axiom.core.persona import PERSONA_PRESETS
        config.persona = PERSONA_PRESETS.get(config.persona_key, PERSONA_PRESETS["default"])
        config.save()
        super().accept()

