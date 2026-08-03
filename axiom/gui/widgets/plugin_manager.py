from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QCheckBox, QPushButton, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
import logging

from axiom.config import get_config
from axiom.tool_registry import ToolRegistry
from axiom.engine.plugin_loader import PluginLoaderService

logger = logging.getLogger(__name__)

class PluginManagerDialog(QDialog):
    """Dialog to manage loaded plugins and toggle them on/off."""
    
    plugins_updated = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Plugin Manager")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.config = get_config()
        self._loading = True
        
        # Ensure all plugins are discovered in this process
        PluginLoaderService().discover_and_load()
        
        # Instantiate a local tool registry to get the full list
        # We access the core registry directly because `list_tools()` filters disabled ones now!
        self.registry = ToolRegistry()
        
        self._build_ui()
        self._loading = False

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        self.setStyleSheet("background-color: #18181b; color: #d4d4d8; font-family: 'Inter', 'Segoe UI', sans-serif;")
        
        title = QLabel("🔌 Plugin Hub")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2ecc71;")
        layout.addWidget(title)
        
        desc = QLabel("Enable or disable AXIOM tools and plugins. Changes apply instantly to the active agent.")
        desc.setStyleSheet("color: #a0a0b0; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Scroll area for plugins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #27272a; border-radius: 6px; background-color: #18181b; }")
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        
        # We need all tools, even disabled ones
        all_tools = self.registry._core_registry.list_tools()
        disabled_list = getattr(self.config, 'disabled_plugins', [])
        
        for tool_id, tool in sorted(all_tools.items()):
            card = QFrame()
            card.setStyleSheet("QFrame { background-color: #27272a; border-radius: 6px; }")
            card_layout = QHBoxLayout(card)
            
            info_layout = QVBoxLayout()
            name_lbl = QLabel(tool_id)
            name_lbl.setStyleSheet("font-weight: bold; color: #e4e4e7; font-size: 14px;")
            
            desc_text = getattr(tool, 'description', '')
            if not desc_text and tool.__doc__:
                desc_text = tool.__doc__.strip().split('\n')[0]
                
            desc_lbl = QLabel(desc_text or "No description provided.")
            desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px;")
            desc_lbl.setWordWrap(True)
            
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            
            card_layout.addLayout(info_layout)
            
            toggle = QCheckBox("Enabled")
            toggle.setChecked(tool_id not in disabled_list)
            # Use property to store tool_id
            toggle.setProperty("tool_id", tool_id)
            toggle.setStyleSheet("""
                QCheckBox { color: #a1a1aa; font-weight: bold; }
                QCheckBox::indicator { width: 36px; height: 18px; border-radius: 9px; }
                QCheckBox::indicator:checked { background-color: #2ecc71; border: 2px solid #2ecc71; }
                QCheckBox::indicator:unchecked { background-color: #3f3f46; border: 2px solid #52525b; }
            """)
            toggle.toggled.connect(self._on_plugin_toggled)
            
            card_layout.addWidget(toggle)
            container_layout.addWidget(card)
            
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet("background-color: #3f3f46; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        close_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _on_plugin_toggled(self, checked: bool):
        if self._loading:
            return
            
        sender = self.sender()
        if not sender:
            return
            
        tool_id = sender.property("tool_id")
        disabled_list = getattr(self.config, 'disabled_plugins', [])
        
        if checked:
            if tool_id in disabled_list:
                disabled_list.remove(tool_id)
        else:
            if tool_id not in disabled_list:
                disabled_list.append(tool_id)
                
        self.config.disabled_plugins = disabled_list
        self.config.save()
        logger.info(f"Plugin {tool_id} {'enabled' if checked else 'disabled'}.")
        self.plugins_updated.emit()
