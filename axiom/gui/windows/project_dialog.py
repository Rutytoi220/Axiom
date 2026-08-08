import os
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QFileDialog, QListWidget, QFrame
)

class ProjectDialog(QDialog):
    """Modal dialog to create a new project with context and files."""
    
    project_created = Signal(str, str, list)  # title, context, file_paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setFixedSize(500, 550)
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
                color: #FFFFFF;
            }
            QLabel {
                font-family: 'Inter', sans-serif;
                font-size: 13px;
                color: #D1D5DB;
                margin-top: 10px;
            }
            QLineEdit, QTextEdit {
                background-color: #262626;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                padding: 10px;
                color: #FFFFFF;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #2563EB;
            }
            QListWidget {
                background-color: #262626;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                padding: 5px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #4A4A4A;
                border-radius: 8px;
                padding: 8px 16px;
                font-family: 'Inter', sans-serif;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton#createBtn {
                background-color: #2563EB;
                border: none;
                font-weight: bold;
            }
            QPushButton#createBtn:hover {
                background-color: #1D4ED8;
            }
        """)

        self.attached_files = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Title
        layout.addWidget(QLabel("Project Name"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("e.g. AXIOM Refactoring")
        layout.addWidget(self.title_input)

        # Context
        layout.addWidget(QLabel("Custom Context Instructions (Optional)"))
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("Provide any context, system prompts, or background information you want the AI to always know in this project...")
        layout.addWidget(self.context_input)

        # Attachments
        attach_layout = QHBoxLayout()
        attach_layout.addWidget(QLabel("Attached Files"))
        attach_layout.addStretch()
        
        self.btn_attach = QPushButton("Browse Files")
        self.btn_attach.setCursor(Qt.PointingHandCursor)
        self.btn_attach.clicked.connect(self._browse_files)
        attach_layout.addWidget(self.btn_attach)
        layout.addLayout(attach_layout)

        self.file_list = QListWidget()
        self.file_list.setFixedHeight(80)
        layout.addWidget(self.file_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_create = QPushButton("Create Project")
        self.btn_create.setObjectName("createBtn")
        self.btn_create.setCursor(Qt.PointingHandCursor)
        self.btn_create.clicked.connect(self._on_create)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_create)
        
        layout.addStretch()
        layout.addLayout(btn_layout)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Attach", str(Path.home()))
        for f in files:
            if f not in self.attached_files:
                self.attached_files.append(f)
                self.file_list.addItem(os.path.basename(f))

    def _on_create(self):
        title = self.title_input.text().strip()
        if not title:
            self.title_input.setStyleSheet("border: 1px solid #DC2626;")
            return
            
        context = self.context_input.toPlainText()
        self.project_created.emit(title, context, self.attached_files)
        self.accept()
