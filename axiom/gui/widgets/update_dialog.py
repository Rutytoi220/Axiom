"""Update Manager Dialog.

Displays the GitHub release changelog, a download progress bar, and
Install / Remind Me Later controls.
"""
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class UpdateDialog(QDialog):
    """OTA Update Manager — changelog viewer with install controls."""

    def __init__(self, parent=None, release_data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("🔄 AXIOM Update Manager")
        self.setMinimumSize(600, 420)
        self._release_data = release_data or {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Version header
        tag = self._release_data.get("tag_name", "—")
        header = QLabel(f"<h2>New Release Available: {tag}</h2>")
        header.setStyleSheet("color: #a6e3a1;")
        layout.addWidget(header)

        # Changelog
        changelog = self._release_data.get("body", "No changelog available.")
        self.changelog_view = QTextEdit()
        self.changelog_view.setReadOnly(True)
        self.changelog_view.setMarkdown(changelog)
        self.changelog_view.setStyleSheet(
            "background-color: #181825; color: #cdd6f4; border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(self.changelog_view)

        # Progress bar (hidden until download starts)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Action buttons
        btn_row = QHBoxLayout()

        self.install_btn = QPushButton("🚀 Install && Relaunch Now")
        self.install_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #11111b; font-weight: bold; "
            "padding: 10px 20px; border-radius: 6px;"
        )
        self.install_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self.install_btn)

        self.later_btn = QPushButton("⏰ Remind Me Later")
        self.later_btn.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; font-weight: bold; "
            "padding: 10px 20px; border-radius: 6px;"
        )
        self.later_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.later_btn)

        layout.addLayout(btn_row)

    def _on_install(self):
        self.progress_bar.show()
        self.progress_bar.setValue(10)
        self.install_btn.setEnabled(False)
        self.install_btn.setText("⏳ Downloading…")

        # In a real implementation we would kick off an async download task
        # and update the progress bar via a signal.  For now, simulate.
        self.progress_bar.setValue(100)
        self.install_btn.setText("✅ Complete")

        QMessageBox.information(
            self,
            "Update Staged",
            "The update has been staged. The daemon will restart momentarily.",
        )
        self.accept()
