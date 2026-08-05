"""AXIOM Desktop v3.0 — Chat message bubble widget."""

from __future__ import annotations

import html
import time
from typing import Literal

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
    QWidget, QToolButton,
)

Role = Literal["user", "assistant", "tool"]


class ToolPill(QFrame):
    """Collapsible tool execution pill shown inside a chat bubble."""

    def __init__(self, tool_id: str, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolPill")
        self._expanded = False
        self._detail_text = status

        from axiom.gui.config_manager import get_ui_config_manager
        accent = get_ui_config_manager().load().accent_color
        
        self.setStyleSheet("QFrame#toolPill { background: transparent; border: none; padding: 2px 4px; }")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._summary = QLabel(f"<span style='color: {accent};'>[✓] Executing {html.escape(tool_id)}...</span>")
        self._summary.setObjectName("toolPillSummary")
        self._summary.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(self._summary, 1)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(layout)
        self.setLayout(outer)

    def update_status(self, status: str) -> None:
        self._detail_text = status

    def _toggle_detail(self) -> None:
        pass


class MessageBubble(QFrame):
    """Single chat message bubble (user or assistant)."""

    _USER_STYLE = (
        "QFrame#msgBubble { background: transparent; border: none; border-bottom: 1px solid #30363D; border-left: 3px solid {accent}; padding: 12px 16px; border-radius: 0px; }"
    )
    _ASST_STYLE = (
        "QFrame#msgBubble { background: transparent; border: none; border-bottom: 1px solid #30363D; padding: 12px 16px; border-radius: 0px; }"
    )
    _ERR_STYLE = (
        "QFrame#msgBubble { background: #2a1010; border: none; border-bottom: 1px solid #30363D; border-left: 3px solid #ef4444; padding: 12px 16px; border-radius: 0px; }"
    )

    def __init__(
        self,
        role: Role,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("msgBubble")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        from axiom.gui.config_manager import get_ui_config_manager
        accent = get_ui_config_manager().load().accent_color
        
        if role == "user":
            self.setStyleSheet(self._USER_STYLE.format(accent=accent))
        elif role == "assistant":
            self.setStyleSheet(self._ASST_STYLE)
        else:
            self.setStyleSheet(self._ERR_STYLE)

        self.setProperty("bubbleRole", role)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Role badge + timestamp
        header = QHBoxLayout()
        role_label = QLabel({"user": "You", "assistant": "AXIOM", "tool": "Tool"}.get(role, role))
        role_label.setObjectName(f"roleLabel_{role}")
        ts = QLabel(time.strftime("%H:%M"))
        ts.setObjectName("msgTimestamp")
        
        self._copy_btn = QToolButton()
        self._copy_btn.setText("📋 Copy")
        self._copy_btn.setStyleSheet("background: transparent; color: #a6adc8; border: none; font-size: 11px;")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)

        header.addWidget(role_label)
        header.addStretch()
        header.addWidget(self._copy_btn)
        header.addWidget(ts)
        layout.addLayout(header)

        # Main text
        self._body = QLabel()
        self._body.setObjectName("msgBody")
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setOpenExternalLinks(True)
        self._body.setText(text)
        layout.addWidget(self._body)

    def set_text(self, text: str) -> None:
        """Update the bubble body (used for streaming)."""
        self._body.setText(text)

    def append_text(self, chunk: str) -> None:
        """Append a streamed chunk to the existing body text."""
        self._body.setText(self._body.text() + html.escape(chunk))

    def _copy_to_clipboard(self) -> None:
        """Copy the raw plain text of the bubble and attached annotations to the clipboard."""
        import PySide6.QtGui as QtGui
        import PySide6.QtWidgets as QtWidgets
        
        doc = QtGui.QTextDocument()
        doc.setHtml(self._body.text())
        full_text = doc.toPlainText().strip()
        
        # Traverse sibling widgets to find attached annotations (ToolPills/SwarmPills)
        parent = self.parentWidget()
        if parent and parent.layout():
            layout = parent.layout()
            idx = layout.indexOf(self)
            if idx != -1:
                # Look ahead for annotations belonging to this message
                for i in range(idx + 1, layout.count()):
                    item = layout.itemAt(i)
                    if not item:
                        continue
                    widget = item.widget()
                    if not widget:
                        continue
                        
                    # Stop if we hit the next chat message
                    if widget.objectName() == "msgBubble":
                        break
                        
                    # Extract ToolPill data
                    if widget.objectName() == "toolPill":
                        summary = widget.findChild(QtWidgets.QLabel, "toolPillSummary")
                        detail = widget.findChild(QtWidgets.QLabel, "toolPillDetail")
                        
                        s_text = summary.text().replace('<b>', '').replace('</b>', '') if summary else "Tool"
                        d_text = detail.text() if detail else ""
                        full_text += f"\n\n[🛠️ Tool Call: {s_text}]\n{d_text}"

        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(full_text.strip())
        self._copy_btn.setText("✅ Copied!")
        
        # Reset button text after 2 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("📋 Copy"))
