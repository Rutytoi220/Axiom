import json
import logging
import urllib.request
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QScrollArea, 
    QFrame, QLabel, QPushButton, QHBoxLayout
)

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST = [
    {
        "id": "sys_info",
        "name": "System Info Tool",
        "author": "axiom-core",
        "version": "1.0.0",
        "desc": "Returns RAM/CPU usage",
        "tags": ["[System]", "[Diagnostics]"],
        "download_url": None,
        "code": "from axiom.tools.base import BaseTool\n\nclass SysInfoTool(BaseTool):\n    def __init__(self):\n        super().__init__('sys_info', 'SysInfoTool', 'Returns RAM/CPU usage')\n    async def execute(self, **kw): return __import__('axiom.tools', fromlist=['ToolResult']).ToolResult(success=True, output='System Nominal')"
    }
]

MANIFEST_URL = "https://raw.githubusercontent.com/ChienGPT/axiom-registry/main/manifest.json"

class FetchManifestThread(QThread):
    finished = Signal(list)
    error = Signal(str)

    def run(self):
        try:
            req = urllib.request.Request(MANIFEST_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list):
                    self.finished.emit(data)
                else:
                    self.finished.emit(DEFAULT_MANIFEST)
        except Exception as e:
            logger.warning(f"Failed to fetch live manifest, falling back to default: {e}")
            self.finished.emit(DEFAULT_MANIFEST)

class InstallToolThread(QThread):
    finished = Signal(str, str) # tool_id, status (success/error)
    
    def __init__(self, item: dict):
        super().__init__()
        self.item = item
        
    def run(self):
        try:
            code = self.item.get("code")
            download_url = self.item.get("download_url")
            
            if not code and download_url:
                req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    code = response.read().decode('utf-8')
            
            if not code:
                self.finished.emit(self.item['id'], "Error: No code or download URL provided")
                return
                
            plugins_dir = Path.home() / ".config" / "ChienGPT" / "plugins"
            plugins_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = plugins_dir / f"{self.item['id']}.py"
            file_path.write_text(code, encoding="utf-8")
            self.finished.emit(self.item['id'], "Success")
        except Exception as e:
            logger.error(f"Failed to download/install tool {self.item.get('id')}: {e}")
            self.finished.emit(self.item.get('id', 'unknown'), f"Error: {str(e)}")

class AxiomHubDialog(QDialog):
    tool_installed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AXIOM Hub")
        self.setMinimumSize(650, 500)
        self.setStyleSheet("QDialog { background-color: #1E1E2E; color: white; }")
        
        self.layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tools_tab = QWidget()
        self.themes_tab = QWidget()
        
        self.tabs.addTab(self.tools_tab, "Tools")
        self.tabs.addTab(self.themes_tab, "Themes")
        
        self.layout.addWidget(self.tabs)
        
        self.tools_layout = QVBoxLayout(self.tools_tab)
        
        self.loading_label = QLabel("Loading live tools manifest...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tools_layout.addWidget(self.loading_label)
        
        self._fetch_manifest()

    def _fetch_manifest(self):
        self.fetch_thread = FetchManifestThread()
        self.fetch_thread.finished.connect(self._on_manifest_fetched)
        self.fetch_thread.start()

    def _on_manifest_fetched(self, manifest: list):
        self.loading_label.hide()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: transparent; }")
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(12)
        
        for item in manifest:
            card = self._create_tool_card(item)
            self.scroll_layout.addWidget(card)
            
        scroll.setWidget(scroll_content)
        self.tools_layout.addWidget(scroll)

    def _create_tool_card(self, item: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #2D2B3D; border-radius: 8px; padding: 12px; }")
        
        layout = QHBoxLayout(card)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        # Top line: Name + Author + Version
        header_layout = QHBoxLayout()
        
        name_label = QLabel(item.get("name", "Unknown Tool"))
        name_label.setStyleSheet("font-weight: bold; font-size: 16px; color: white;")
        header_layout.addWidget(name_label)
        
        if "author" in item:
            author_label = QLabel(f"by @{item['author']}")
            author_label.setStyleSheet("color: #89B4FA; font-size: 13px; font-weight: 500;")
            header_layout.addWidget(author_label)
            
        if "version" in item:
            version_label = QLabel(f"v{item['version']}")
            version_label.setStyleSheet("background-color: #181825; color: #A6E3A1; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold;")
            header_layout.addWidget(version_label)
            
        header_layout.addStretch()
        text_layout.addLayout(header_layout)
        
        # Tags line
        if "tags" in item and item["tags"]:
            tags_str = " ".join(item["tags"])
            tags_label = QLabel(tags_str)
            tags_label.setStyleSheet("color: #F9E2AF; font-size: 12px;")
            text_layout.addWidget(tags_label)
            
        # Description
        desc_label = QLabel(item.get("desc", ""))
        desc_label.setStyleSheet("color: #A0A0B0; font-size: 14px;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Install Button
        install_btn = QPushButton()
        self._update_btn_state(install_btn, item["id"])
        install_btn.clicked.connect(lambda _, btn=install_btn, i=item: self._install_tool(i, btn))
        layout.addWidget(install_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        return card

    def _update_btn_state(self, btn: QPushButton, tool_id: str):
        plugins_dir = Path.home() / ".config" / "ChienGPT" / "plugins"
        file_path = plugins_dir / f"{tool_id}.py"
        
        if file_path.exists():
            btn.setText("Installed")
            btn.setStyleSheet("QPushButton { background-color: #10B981; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }")
            btn.setEnabled(False)
        else:
            btn.setText("1-Click Install")
            btn.setStyleSheet("QPushButton { background-color: #3B82F6; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; } QPushButton:hover { background-color: #2563EB; }")
            btn.setEnabled(True)

    def _install_tool(self, item: dict, btn: QPushButton):
        btn.setText("Installing...")
        btn.setEnabled(False)
        
        # Keep a strong reference to the thread so it doesn't get garbage collected
        if not hasattr(self, '_install_threads'):
            self._install_threads = []
            
        thread = InstallToolThread(item)
        self._install_threads.append(thread)
        thread.finished.connect(lambda tid, status: self._on_install_finished(tid, status, btn, thread))
        thread.start()

    def _on_install_finished(self, tool_id: str, status: str, btn: QPushButton, thread: QThread):
        if status == "Success":
            self._update_btn_state(btn, tool_id)
            self.tool_installed.emit(tool_id)
        else:
            btn.setText("Failed")
            btn.setStyleSheet("QPushButton { background-color: #F28FAD; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }")
            btn.setEnabled(False)
            
        if thread in self._install_threads:
            self._install_threads.remove(thread)
