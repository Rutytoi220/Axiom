"""Automation Dialog UI.

A minimalist interface to toggle core autonomous background
triggers built in v5.0+ (REM Sleep, Power Governor, Watchdog, Interceptor).
"""
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QWidget
)
import logging

logger = logging.getLogger(__name__)

class SchedulerDialog(QDialog):
    """Minimalist UI for managing autonomous triggers."""

    def __init__(self, scheduler_service=None, parent=None, event_bus=None):
        super().__init__(parent)
        self.scheduler_service = scheduler_service
        self.event_bus = event_bus
        self.setWindowTitle("⏱️ AXIOM Automation Triggers")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>Autonomous Background Triggers</h2>")
        header.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        layout.addWidget(header)
        
        desc = QLabel("Easily toggle AXIOM's core background subsystems without complex cron rules.")
        desc.setStyleSheet("color: #a6adc8; margin-bottom: 20px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Trigger List
        self._add_toggle_row(layout, "🌌 Nightly REM Sleep", "Compacts GraphRAG memory at 03:00 AM.", "rem_sleep", True)
        self._add_toggle_row(layout, "🔋 Power Governor", "Dynamically throttles AI models when on battery power.", "power_gov", True)
        self._add_toggle_row(layout, "🔌 Hardware Interceptor", "Zero-trust sandbox for incoming USB/BLE mounts.", "hw_intercept", True)
        self._add_toggle_row(layout, "📂 Directory Watchdog", "Pre-computes responses based on file system events.", "watchdog", False)
        
        layout.addStretch()

    def _add_toggle_row(self, parent_layout, title: str, description: str, trigger_id: str, default_state: bool):
        row = QFrame()
        row.setStyleSheet("""
            QFrame {
                background-color: #313244;
                border-radius: 8px;
                padding: 10px;
                margin-bottom: 10px;
            }
        """)
        row_layout = QHBoxLayout(row)
        
        text_layout = QVBoxLayout()
        t_label = QLabel(f"<b>{title}</b>")
        t_label.setStyleSheet("color: #cdd6f4; font-size: 15px;")
        
        d_label = QLabel(description)
        d_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        
        text_layout.addWidget(t_label)
        text_layout.addWidget(d_label)
        row_layout.addLayout(text_layout)
        
        row_layout.addStretch()
        
        btn = QPushButton("ON" if default_state else "OFF")
        self._style_toggle_btn(btn, default_state)
        btn.setProperty("trigger_id", trigger_id)
        btn.setProperty("state", default_state)
        btn.setFixedSize(60, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _, b=btn: self._on_toggle(b))
        
        row_layout.addWidget(btn)
        parent_layout.addWidget(row)

    def _style_toggle_btn(self, btn: QPushButton, state: bool):
        if state:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #a6e3a1;
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 15px;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #45475a;
                    color: #cdd6f4;
                    font-weight: bold;
                    border-radius: 15px;
                }
            """)

    @Slot()
    def _on_toggle(self, btn: QPushButton):
        current_state = btn.property("state")
        new_state = not current_state
        trigger_id = btn.property("trigger_id")
        
        btn.setProperty("state", new_state)
        btn.setText("ON" if new_state else "OFF")
        self._style_toggle_btn(btn, new_state)
        
        logger.info(f"Automation Dialog: Toggled {trigger_id} to {new_state}")
        
        if self.event_bus:
            self.event_bus.publish_sync(f"system.toggle.{trigger_id}", {"state": new_state})
