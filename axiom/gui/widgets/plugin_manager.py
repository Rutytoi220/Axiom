from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QCheckBox, QPushButton, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
import logging

from axiom.config import get_config

logger = logging.getLogger(__name__)

class PluginManagerDialog(QDialog):
    """Dialog to manage loaded plugins and toggle them on/off."""
    
    plugins_updated = Signal()
    
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Plugin Manager")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.config = get_config()
        self._bridge = bridge
        self._loading = True
        
        self._build_ui()
        
        # Connect to bridge to receive tools, then request them
        self._bridge.tools_received.connect(self._populate_tools)
        self._bridge.request_tools()

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
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(10)
        
        # Placeholder while loading
        self.loading_lbl = QLabel("Fetching plugins from daemon...")
        self.loading_lbl.setStyleSheet("color: #a1a1aa; font-style: italic;")
        self.container_layout.addWidget(self.loading_lbl)
        
        self.container_layout.addStretch()
        scroll.setWidget(self.container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet("background-color: #3f3f46; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        close_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _populate_tools(self, tools_list: list):
        # Clear container
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self._loading = True
                
        for t in tools_list:
            tool_id = t["id"]
            desc_text = t["description"]
            is_enabled = t["enabled"]
            
            card = QFrame()
            card.setStyleSheet("QFrame { background-color: #27272a; border-radius: 6px; }")
            card_layout = QHBoxLayout(card)
            
            info_layout = QVBoxLayout()
            name_lbl = QLabel(tool_id)
            name_lbl.setStyleSheet("font-weight: bold; color: #e4e4e7; font-size: 14px;")
            
            desc_lbl = QLabel(desc_text)
            desc_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px;")
            desc_lbl.setWordWrap(True)
            
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            card_layout.addLayout(info_layout)
            
            toggle = QCheckBox("Enabled" if is_enabled else "Disabled")
            toggle.setChecked(is_enabled)
            toggle.setProperty("tool_id", tool_id)
            toggle.setStyleSheet("""
                QCheckBox { color: #a1a1aa; font-weight: bold; background: transparent; }
                QCheckBox::indicator { width: 36px; height: 18px; border-radius: 9px; }
                QCheckBox::indicator:checked { background-color: #2ecc71; border: 2px solid #2ecc71; }
                QCheckBox::indicator:unchecked { background-color: #3f3f46; border: 2px solid #52525b; }
            """)
            toggle.toggled.connect(self._on_plugin_toggled)
            
            card_layout.addWidget(toggle)
            self.container_layout.addWidget(card)
            
        self.container_layout.addStretch()
        self._loading = False

    def _on_plugin_toggled(self, checked: bool):
        if self._loading:
            return
            
        sender = self.sender()
        if not sender:
            return
            
        tool_id = sender.property("tool_id")
        
        # Update text dynamically
        sender.setText("Enabled" if checked else "Disabled")
        
        # Send IPC toggle request
        self._bridge.toggle_tool(tool_id, checked)
        
        logger.info(f"Plugin {tool_id} IPC toggle requested (enabled={checked}).")
        self.plugins_updated.emit()
