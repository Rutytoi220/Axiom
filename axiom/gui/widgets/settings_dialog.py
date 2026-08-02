from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QCheckBox, QPushButton, QFormLayout, QWidget, QLineEdit,
    QTabWidget, QSpinBox
)
from PySide6.QtCore import Qt, Signal
import logging
import json
import os
from pathlib import Path

from axiom.config import get_config

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """Settings dialog for Theme, Ollama, Routing preferences, and Federation."""
    
    settings_updated = Signal()
    
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._bridge = bridge
        self.config = get_config()
        self._keys_path = Path.home() / '.config' / 'axiom' / 'keys.json'
        self._keys_path.parent.mkdir(parents=True, exist_ok=True)
        self._loading = True
        self._build_ui()
        self._load_current_settings()
        self._loading = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        # --- General Tab ---
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_form = QFormLayout()
        general_form.setSpacing(12)
        
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Dark", "Light"])
        self._theme_combo.currentIndexChanged.connect(self._save_settings)
        general_form.addRow("Theme Mode:", self._theme_combo)
        
        self._auto_start_cb = QCheckBox("Automatically start Ollama daemon if offline")
        self._auto_start_cb.toggled.connect(self._save_settings)
        general_form.addRow("Ollama:", self._auto_start_cb)
        
        self._routing_combo = QComboBox()
        self._routing_combo.addItem("Auto (SmartRouter)", "auto")
        self._routing_combo.addItem("Manual (Override)", "manual")
        self._routing_combo.currentIndexChanged.connect(self._on_routing_changed)
        general_form.addRow("Model Selection:", self._routing_combo)
        
        self._model_combo = QComboBox()
        self._model_combo.currentIndexChanged.connect(self._save_settings)
        general_form.addRow("Target Model:", self._model_combo)
        
        self._watchdog_cb = QCheckBox("Enable Auto-Indexing Watchdog")
        self._watchdog_cb.toggled.connect(self._save_settings)
        general_form.addRow("Storage & Memory:", self._watchdog_cb)
        
        self._paths_input = QLineEdit()
        self._paths_input.setPlaceholderText("~/Documents, ~/Projects")
        self._paths_input.editingFinished.connect(self._save_settings)
        general_form.addRow("Monitored Folders:", self._paths_input)
        
        general_layout.addLayout(general_form)
        general_layout.addStretch()
        self.tabs.addTab(general_tab, "⚙️ General")
        
        # --- Federation Tab ---
        fed_tab = QWidget()
        fed_layout = QVBoxLayout(fed_tab)
        fed_form = QFormLayout()
        fed_form.setSpacing(12)
        
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setEchoMode(QLineEdit.Password)
        self._anthropic_key.setPlaceholderText("sk-ant-...")
        self._anthropic_key.editingFinished.connect(self._save_settings)
        fed_form.addRow("Anthropic API Key:", self._anthropic_key)
        
        self._daily_token_limit = QSpinBox()
        self._daily_token_limit.setRange(0, 10000000)
        self._daily_token_limit.setSingleStep(1000)
        self._daily_token_limit.valueChanged.connect(self._save_settings)
        fed_form.addRow("Daily Cloud Token Limit:", self._daily_token_limit)
        
        fed_layout.addLayout(fed_form)
        fed_layout.addStretch()
        self.tabs.addTab(fed_tab, "🌐 Cloud Federation & Budget")
        
        # --- Cron Swarms & Voice Tab ---
        cron_tab = QWidget()
        cron_layout = QVBoxLayout(cron_tab)
        cron_form = QFormLayout()
        cron_form.setSpacing(12)
        
        self._whisper_model = QComboBox()
        self._whisper_model.addItems(["tiny.en", "base.en", "small.en"])
        self._whisper_model.currentIndexChanged.connect(self._save_settings)
        cron_form.addRow("Whisper Dictation Model:", self._whisper_model)
        
        self._cron_jobs_label = QLabel("Active Cron Jobs:\n(See ~/.config/axiom/cron.json)")
        cron_form.addRow("Background Swarms:", self._cron_jobs_label)
        
        cron_layout.addLayout(cron_form)
        cron_layout.addStretch()
        self.tabs.addTab(cron_tab, "⏱️ Cron Swarms & Voice")
        
        # --- LAN Mesh Tab ---
        mesh_tab = QWidget()
        mesh_layout = QVBoxLayout(mesh_tab)
        
        mesh_info_label = QLabel("Connected LAN Mesh Peer Nodes:")
        mesh_info_label.setStyleSheet("font-weight: bold;")
        mesh_layout.addWidget(mesh_info_label)
        
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.mesh_table = QTableWidget(0, 4)
        self.mesh_table.setHorizontalHeaderLabels(["Hostname", "Role", "Hardware", "Status"])
        self.mesh_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mesh_table.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        
        # Add a dummy local node for illustration
        self.mesh_table.insertRow(0)
        self.mesh_table.setItem(0, 0, QTableWidgetItem("localhost"))
        self.mesh_table.setItem(0, 1, QTableWidgetItem("Orchestrator"))
        self.mesh_table.setItem(0, 2, QTableWidgetItem("Local GPU"))
        self.mesh_table.setItem(0, 3, QTableWidgetItem("Active"))
        
        mesh_layout.addWidget(self.mesh_table)
        
        mesh_refresh_btn = QPushButton("🔄 Scan Network (Port 9412)")
        mesh_layout.addWidget(mesh_refresh_btn)
        
        self.tabs.addTab(mesh_tab, "🕸️ LAN Mesh")
        
        layout.addWidget(self.tabs)

    def _load_current_settings(self):
        # General
        theme_map = {"system": 0, "dark": 1, "light": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self.config.theme_mode.lower(), 1))
        self._auto_start_cb.setChecked(self.config.auto_ollama_start)
        
        routing_idx = 1 if self.config.model_selection_mode == "manual" else 0
        self._routing_combo.setCurrentIndex(routing_idx)
        self._model_combo.addItem(self.config.ollama_model)
        
        if hasattr(self._bridge, "get_available_models"):
            models = self._bridge.get_available_models()
            if models:
                self._model_combo.clear()
                for m in models:
                    self._model_combo.addItem(m)
                idx = self._model_combo.findText(self.config.ollama_model)
                if idx >= 0:
                    self._model_combo.setCurrentIndex(idx)
                    
        self._watchdog_cb.setChecked(self.config.auto_index_watchdog)
        self._paths_input.setText(", ".join(self.config.monitored_paths))
        self._on_routing_changed()
        
        # Federation
        try:
            if self._keys_path.exists():
                with open(self._keys_path, 'r') as f:
                    keys = json.load(f)
                    self._anthropic_key.setText(keys.get("anthropic_api_key", ""))
        except Exception as e:
            logger.warning(f"Could not load keys: {e}")
            
        self._daily_token_limit.setValue(getattr(self.config, 'daily_cloud_token_limit', 50000))
        
        whisper_model = getattr(self.config, 'whisper_model', 'tiny.en')
        idx = self._whisper_model.findText(whisper_model)
        if idx >= 0:
            self._whisper_model.setCurrentIndex(idx)

    def _on_routing_changed(self):
        mode = self._routing_combo.currentData()
        self._model_combo.setEnabled(mode == "manual")
        self._save_settings()

    def _save_settings(self, *args):
        # Don't save during initialization — widgets are still being populated
        if self._loading:
            return

        # Save general config
        self.config.theme_mode = self._theme_combo.currentText().lower()
        self.config.auto_ollama_start = self._auto_start_cb.isChecked()

        routing_mode = self._routing_combo.currentData()
        if routing_mode is not None:
            self.config.model_selection_mode = routing_mode

        self.config.auto_index_watchdog = self._watchdog_cb.isChecked()
        
        paths_str = self._paths_input.text()
        paths_list = [p.strip() for p in paths_str.split(",") if p.strip()]
        if paths_list:
            self.config.monitored_paths = paths_list
            
        if self._model_combo.isEnabled() and self._model_combo.currentText():
            self.config.ollama_model = self._model_combo.currentText()
            
        setattr(self.config, 'daily_cloud_token_limit', self._daily_token_limit.value())
        setattr(self.config, 'whisper_model', self._whisper_model.currentText())
        self.config.save()
        
        # Save federation keys
        key = self._anthropic_key.text().strip()
        try:
            keys = {}
            if self._keys_path.exists():
                with open(self._keys_path, 'r') as f:
                    keys = json.load(f)
            keys["anthropic_api_key"] = key
            
            # Secure write
            with open(self._keys_path, 'w') as f:
                json.dump(keys, f)
            os.chmod(self._keys_path, 0o600)
        except Exception as e:
            logger.error(f"Could not save keys: {e}")
            
        logger.info("Settings saved to disk.")
        self.settings_updated.emit()
