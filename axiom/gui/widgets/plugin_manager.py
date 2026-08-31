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
        
        title = QLabel("Plugin Hub")
        title.setObjectName("hub_name")
        layout.addWidget(title)
        
        desc = QLabel("Enable or disable AXIOM tools and plugins. Changes apply instantly to the active agent.")
        desc.setObjectName("hub_desc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("plugin_scroll")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(10)
        
        self.loading_lbl = QLabel("Fetching plugins from daemon...")
        self.loading_lbl.setObjectName("plugin_loading")
        self.container_layout.addWidget(self.loading_lbl)
        
        self.container_layout.addStretch()
        scroll.setWidget(self.container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.setObjectName("plugin_close")
        close_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _populate_tools(self, tools_list: list):
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
            card.setObjectName("plugin_card")
            card_layout = QHBoxLayout(card)
            
            info_layout = QVBoxLayout()
            name_lbl = QLabel(tool_id)
            name_lbl.setObjectName("plugin_name")
            
            desc_lbl = QLabel(desc_text)
            desc_lbl.setObjectName("plugin_desc")
            desc_lbl.setWordWrap(True)
            
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(desc_lbl)
            card_layout.addLayout(info_layout)
            
            toggle = QCheckBox("Enabled" if is_enabled else "Disabled")
            toggle.setChecked(is_enabled)
            toggle.setProperty("tool_id", tool_id)
            toggle.setObjectName("plugin_toggle")
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
        
        sender.setText("Enabled" if checked else "Disabled")
        
        self._bridge.toggle_tool(tool_id, checked)
        
        logger.info(f"Plugin {tool_id} IPC toggle requested (enabled={checked}).")
        self.plugins_updated.emit()
