from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QCheckBox, QPushButton, QFormLayout, QWidget
)
from PySide6.QtCore import Qt, Signal
import logging

from axiom.config import get_config

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """Settings dialog for Theme, Ollama, and Routing preferences."""
    
    settings_updated = Signal()
    
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Settings")
        self.setMinimumWidth(400)
        self._bridge = bridge
        self.config = get_config()
        self._build_ui()
        self._load_current_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        # 1. Theme Selection
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Dark", "Light"])
        self._theme_combo.currentIndexChanged.connect(self._save_settings)
        form.addRow(QLabel("Theme Mode:"), self._theme_combo)
        
        # 2. Auto-Start Ollama
        self._auto_start_cb = QCheckBox("Automatically start Ollama daemon if offline")
        self._auto_start_cb.toggled.connect(self._save_settings)
        form.addRow(QLabel("Ollama:"), self._auto_start_cb)
        
        # 3. Model Selection Mode
        self._routing_combo = QComboBox()
        self._routing_combo.addItem("Auto (SmartRouter)", "auto")
        self._routing_combo.addItem("Manual (Override)", "manual")
        self._routing_combo.currentIndexChanged.connect(self._on_routing_changed)
        form.addRow(QLabel("Model Selection:"), self._routing_combo)
        
        # 4. Manual Model Dropdown
        self._model_combo = QComboBox()
        self._model_combo.currentIndexChanged.connect(self._save_settings)
        form.addRow(QLabel("Target Model:"), self._model_combo)
        
        layout.addLayout(form)
        
        layout.addStretch()

    def _load_current_settings(self):
        # Theme
        theme_map = {"system": 0, "dark": 1, "light": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self.config.theme_mode.lower(), 1))
        
        # Auto start
        self._auto_start_cb.setChecked(self.config.auto_ollama_start)
        
        # Routing mode
        routing_idx = 1 if self.config.model_selection_mode == "manual" else 0
        self._routing_combo.setCurrentIndex(routing_idx)
        
        # Populate models (async bridge doesn't hold them immediately, but we can try to fetch them if available or just list the current one)
        # For simplicity, if we have a config model, we add it. 
        self._model_combo.addItem(self.config.ollama_model)
        
        # In a real scenario, we might want to poll the bridge for the model list.
        # Let's see if the bridge exposes available models.
        if hasattr(self._bridge, "get_available_models"):
            models = self._bridge.get_available_models()
            if models:
                self._model_combo.clear()
                for m in models:
                    self._model_combo.addItem(m)
                idx = self._model_combo.findText(self.config.ollama_model)
                if idx >= 0:
                    self._model_combo.setCurrentIndex(idx)
                    
        self._on_routing_changed()

    def _on_routing_changed(self):
        mode = self._routing_combo.currentData()
        self._model_combo.setEnabled(mode == "manual")
        self._save_settings()

    def _save_settings(self, *args):
        theme_str = self._theme_combo.currentText().lower()
        self.config.theme_mode = theme_str
        
        self.config.auto_ollama_start = self._auto_start_cb.isChecked()
        self.config.model_selection_mode = self._routing_combo.currentData()
        
        if self._model_combo.isEnabled() and self._model_combo.currentText():
            self.config.ollama_model = self._model_combo.currentText()
            
        self.config.save()
        logger.info("Settings saved to disk.")
        self.settings_updated.emit()
