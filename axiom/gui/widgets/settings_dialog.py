from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
)
from PySide6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E2E; color: white; }
            QLabel { font-size: 14px; font-weight: bold; }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(16)
        
        # Title
        title_label = QLabel("System Settings")
        self.layout.addWidget(title_label)
        
        # Mock Model Selector
        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen2.5:1.5b", "qwen3:8b"])
        self.layout.addWidget(self.model_combo)
        
        self.layout.addStretch(1)
        
        # Button Box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.layout.addWidget(self.button_box)
