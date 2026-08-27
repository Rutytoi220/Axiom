import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QScrollArea, QFrame, QLabel, QPushButton, QHBoxLayout

logger = logging.getLogger(__name__)

MANIFEST = [
    {
        "id": "sys_info",
        "name": "System Info Tool",
        "desc": "Returns RAM/CPU usage",
        "code": "from axiom.tools.base import BaseTool\n\nclass SysInfoTool(BaseTool):\n    def __init__(self):\n        super().__init__('sys_info', 'SysInfoTool', 'Returns RAM/CPU usage')\n    async def execute(self, **kw): return __import__('axiom.tools', fromlist=['ToolResult']).ToolResult(success=True, output='System Nominal')"
    }
]

class AxiomHubDialog(QDialog):
    tool_installed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Hub")
        self.setMinimumSize(600, 450)
        self.setStyleSheet("QDialog { background-color: #1E1E2E; color: white; }")
        
        self.layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tools_tab = QWidget()
        self.themes_tab = QWidget()
        
        self.tabs.addTab(self.tools_tab, "Tools")
        self.tabs.addTab(self.themes_tab, "Themes")
        
        self._setup_tools_tab()
        
        self.layout.addWidget(self.tabs)

    def _setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        for item in MANIFEST:
            card = self._create_tool_card(item)
            scroll_layout.addWidget(card)
            
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _create_tool_card(self, item: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #2D2B3D; border-radius: 8px; padding: 12px; } QLabel { color: white; }")
        layout = QHBoxLayout(card)
        
        text_layout = QVBoxLayout()
        name_label = QLabel(item["name"])
        name_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        desc_label = QLabel(item["desc"])
        desc_label.setStyleSheet("color: #A0A0B0; font-size: 14px;")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(desc_label)
        
        install_btn = QPushButton("Install")
        install_btn.setStyleSheet("QPushButton { background-color: #3B82F6; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; } QPushButton:hover { background-color: #2563EB; }")
        install_btn.clicked.connect(lambda _, btn=install_btn, i=item: self._install_tool(i, btn))
        
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(install_btn)
        
        return card

    def _install_tool(self, item: dict, btn: QPushButton):
        plugins_dir = Path.home() / ".config" / "ChienGPT" / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = plugins_dir / f"{item['id']}.py"
        try:
            file_path.write_text(item["code"], encoding="utf-8")
            btn.setText("Installed")
            btn.setStyleSheet("QPushButton { background-color: #10B981; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }")
            btn.setEnabled(False)
            self.tool_installed.emit(item["id"])
        except Exception as e:
            logger.error(f"Failed to install tool {item['id']}: {e}")
