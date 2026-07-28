import sys
import asyncio
import qasync
import logging
import shutil
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTextEdit, QLabel
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QColor

from axiom.client.ipc_client import AxiomDaemonClient

logger = logging.getLogger(__name__)

class HUDWindow(QWidget):
    def __init__(self):
        super().__init__()
        # Frameless, top-level popup
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setFixedSize(700, 400)
        self._init_ui()
        self._client = AxiomDaemonClient()
        self._client.on_event = self._on_daemon_event
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 4
        )

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Main container with rounded corners and dark theme
        container = QWidget()
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 12px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        container_layout.setSpacing(10)
        
        # Header row: Icon, Input, Paste Button
        header_layout = QHBoxLayout()
        
        self.status_icon = QLabel("⚡")
        self.status_icon.setFont(QFont("Arial", 16))
        header_layout.addWidget(self.status_icon)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask AXIOM... (Press Enter to submit)")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #cdd6f4;
                font-size: 16px;
            }
        """)
        self.input_field.returnPressed.connect(self._on_submit)
        header_layout.addWidget(self.input_field)
        
        self.paste_btn = QPushButton("📋 Paste Context")
        self.paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)
        self.paste_btn.clicked.connect(self._on_paste_context)
        header_layout.addWidget(self.paste_btn)
        
        container_layout.addLayout(header_layout)
        
        # Output Area (hidden by default until submission)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setStyleSheet("""
            QTextEdit {
                background-color: #181825;
                color: #a6adc8;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        self.output_area.hide()
        container_layout.addWidget(self.output_area)
        
        main_layout.addWidget(container)
        
    def showEvent(self, event):
        self.input_field.setFocus()
        super().showEvent(event)
        
        # Connect client when shown
        loop = asyncio.get_event_loop()
        asyncio.create_task(self._client.connect())

    def _on_paste_context(self):
        text = ""
        try:
            if shutil.which("wl-paste"):
                proc = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True)
                text = proc.stdout
            elif shutil.which("xclip"):
                proc = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
                text = proc.stdout
        except Exception as e:
            logger.error(f"Failed to read clipboard: {e}")
            
        if text:
            current = self.input_field.text()
            self.input_field.setText(f"[System Clipboard Context]:\n{text}\n\n[User Request]: {current}")
            self.input_field.setFocus()

    def _on_submit(self):
        prompt = self.input_field.text().strip()
        if not prompt:
            return
            
        self.input_field.clear()
        self.output_area.show()
        self.output_area.clear()
        self.status_icon.setText("🔄")
        
        if not self._client.is_connected:
            self.output_area.append("Error: Not connected to daemon.")
            self.status_icon.setText("❌")
            return
            
        loop = asyncio.get_event_loop()
        asyncio.create_task(self._client.submit_task(prompt))

    def _on_daemon_event(self, data: dict):
        event_type = data.get("event_type", "")
        payload = data.get("payload", {})
        
        if event_type == "llm.token":
            chunk = payload.get("chunk", "")
            # Use QTimer or signal in a real app, but qasync loop makes this thread-safe enough
            self.output_area.insertPlainText(chunk)
            self.output_area.verticalScrollBar().setValue(self.output_area.verticalScrollBar().maximum())
        elif event_type == "orchestrator.finished":
            self.status_icon.setText("✅")

def run_hud():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    hud = HUDWindow()
    hud.show()
    
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    run_hud()
