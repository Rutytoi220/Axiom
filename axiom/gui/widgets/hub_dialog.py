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

DEFAULT_THEMES_MANIFEST = [
    {
        "id": "nordic",
        "name": "Nordic Frost",
        "author": "Community",
        "version": "1.0",
        "desc": "A beautiful icy blue theme for late-night coding.",
        "url": "mock://nordic"
    },
    {
        "id": "malicious",
        "name": "H4ck3r R3d",
        "author": "Evil Corp",
        "version": "1.0",
        "desc": "Danger! This theme tries to do bad things.",
        "url": "mock://malicious"
    }
]

MOCK_THEME_CONTENTS = {
    "mock://nordic": json.dumps({
        "id": "nordic",
        "name": "Nordic Frost",
        "author": "Community",
        "version": "1.0",
        "tokens": {
            "bg_base": "#2e3440",
            "fg_base": "#eceff4",
            "accent": "#88c0d0"
        }
    }),
    "mock://malicious": json.dumps({
        "id": "malicious",
        "name": "H4ck3r R3d",
        "author": "Evil Corp",
        "version": "1.0",
        "tokens": {
            "bg_base": "#000000",
            "fg_base": "#ff0000",
            "accent": "url('../../../../../../etc/shadow')"
        }
    })
}

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

class FetchThemesManifestThread(QThread):
    finished = Signal(list)
    error = Signal(str)

    def run(self):
        # In a real scenario, this would make an HTTP request to a themes manifest URL
        self.finished.emit(DEFAULT_THEMES_MANIFEST)

class DownloadThemeThread(QThread):
    finished = Signal(str, str) # theme_id, status (success/error)
    
    def __init__(self, item: dict):
        super().__init__()
        self.item = item
        
    def run(self):
        try:
            theme_id = self.item["id"]
            url = self.item.get("url")
            
            from axiom.gui.styles.theme_manager import THEMES_DIR
            if not THEMES_DIR.exists():
                THEMES_DIR.mkdir(parents=True, exist_ok=True)
                
            theme_path = THEMES_DIR / f"{theme_id}.json"
            
            if url.startswith("mock://"):
                content = MOCK_THEME_CONTENTS.get(url, "{}")
            else:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    content = response.read().decode('utf-8')
                    
            theme_path.write_text(content, encoding="utf-8")
            
            # Validate via ThemeRegistry
            from axiom.gui.styles.theme_registry import ThemeRegistry, ThemeValidationError
            registry = ThemeRegistry(THEMES_DIR)
            try:
                registry.validate_theme(theme_path)
                self.finished.emit(theme_id, "Success")
            except ThemeValidationError as ve:
                theme_path.unlink(missing_ok=True)
                self.finished.emit(theme_id, f"Validation Error: {str(ve)}")
            except Exception as ve:
                theme_path.unlink(missing_ok=True)
                self.finished.emit(theme_id, f"Error: {str(ve)}")

        except Exception as e:
            logger.error(f"Failed to download/install theme {self.item.get('id')}: {e}")
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

        self.themes_layout = QVBoxLayout(self.themes_tab)
        self.themes_loading_label = QLabel("Fetching community themes...")
        self.themes_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.themes_layout.addWidget(self.themes_loading_label)
        
        self._fetch_manifest()
        self._fetch_themes_manifest()

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

    def _fetch_themes_manifest(self):
        self.fetch_themes_thread = FetchThemesManifestThread()
        self.fetch_themes_thread.finished.connect(self._on_themes_manifest_fetched)
        self.fetch_themes_thread.start()

    def _on_themes_manifest_fetched(self, manifest: list):
        self.themes_loading_label.hide()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("QWidget { background-color: transparent; }")
        self.themes_scroll_layout = QVBoxLayout(scroll_content)
        self.themes_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.themes_scroll_layout.setSpacing(12)
        
        for item in manifest:
            card = self._create_theme_card(item)
            self.themes_scroll_layout.addWidget(card)
            
        scroll.setWidget(scroll_content)
        self.themes_layout.addWidget(scroll)

    def _create_theme_card(self, item: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #2D2B3D; border-radius: 8px; padding: 12px; }")
        
        layout = QHBoxLayout(card)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        header_layout = QHBoxLayout()
        name_label = QLabel(item.get("name", "Unknown Theme"))
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
        
        desc_label = QLabel(item.get("desc", ""))
        desc_label.setStyleSheet("color: #A0A0B0; font-size: 14px;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        install_btn = QPushButton()
        self._update_theme_btn_state(install_btn, item["id"])
        install_btn.clicked.connect(lambda _, btn=install_btn, i=item: self._install_theme(i, btn))
        layout.addWidget(install_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        return card

    def _update_theme_btn_state(self, btn: QPushButton, theme_id: str):
        from axiom.gui.styles.theme_manager import THEMES_DIR
        file_path = THEMES_DIR / f"{theme_id}.json"
        
        if file_path.exists():
            btn.setText("Applied")
            btn.setStyleSheet("QPushButton { background-color: #10B981; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }")
            btn.setEnabled(False)
        else:
            btn.setText("Install")
            btn.setStyleSheet("QPushButton { background-color: #3B82F6; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; } QPushButton:hover { background-color: #2563EB; }")
            btn.setEnabled(True)

    def _install_theme(self, item: dict, btn: QPushButton):
        btn.setText("Installing...")
        btn.setEnabled(False)
        
        if not hasattr(self, '_install_theme_threads'):
            self._install_theme_threads = []
            
        thread = DownloadThemeThread(item)
        self._install_theme_threads.append(thread)
        thread.finished.connect(lambda tid, status: self._on_theme_install_finished(tid, status, btn, thread))
        thread.start()

    def _on_theme_install_finished(self, theme_id: str, status: str, btn: QPushButton, thread: QThread):
        if status == "Success":
            self._update_theme_btn_state(btn, theme_id)
            # Apply the theme immediately
            from axiom.gui.styles.theme_manager import get_theme_manager
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            mgr = get_theme_manager()
            mgr._load_themes()
            mgr.apply_theme(app, theme_id)
        else:
            btn.setText("Failed")
            btn.setStyleSheet("QPushButton { background-color: #F28FAD; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; }")
            btn.setEnabled(False)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Theme Installation Failed", f"Validation failed for theme '{theme_id}':\n{status}")
            
        if thread in self._install_theme_threads:
            self._install_theme_threads.remove(thread)
