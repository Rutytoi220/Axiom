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

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        if tool_id == "screen_capture":
            self._icon = QLabel("📸")
            self.setStyleSheet("QFrame#toolPill { background: #2b1f3c; border-radius: 6px; }")
        else:
            self._icon = QLabel("⚙️")
            
        layout.addWidget(self._icon)

        self._summary = QLabel(f"<b>{html.escape(tool_id)}</b>")
        self._summary.setObjectName("toolPillSummary")
        layout.addWidget(self._summary, 1)

        self._toggle = QToolButton()
        self._toggle.setObjectName("toolPillToggle")
        self._toggle.setText("▶")
        self._toggle.clicked.connect(self._toggle_detail)
        layout.addWidget(self._toggle)

        self._detail_label = QLabel(html.escape(status))
        self._detail_label.setObjectName("toolPillDetail")
        self._detail_label.setWordWrap(True)
        self._detail_label.setVisible(False)
        
        self._consensus_badge = QLabel()
        self._consensus_badge.setObjectName("consensusBadge")
        self._consensus_badge.setStyleSheet("background: #312e81; color: #a5b4fc; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;")
        self._consensus_badge.setVisible(False)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addLayout(layout)
        outer.addWidget(self._consensus_badge)
        outer.addWidget(self._detail_label)
        self.setLayout(outer)

    def update_status(self, status: str) -> None:
        self._detail_text = status
        self._detail_label.setText(html.escape(status))
        
        # Check for Swarm Consensus triggers
        if "[🔄 Swarm Consensus" in status:
            self._consensus_badge.setText("🧪 Swarm Consensus: Testing generated code...")
            self._consensus_badge.setVisible(True)
        elif "Swarm Consensus: Verification PASSED" in status:
            self._consensus_badge.setText("🧪 Swarm Consensus: Iterations Passed (Verified by TestAgent)")
            self._consensus_badge.setStyleSheet("background: #064e3b; color: #6ee7b7; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;")
            self._consensus_badge.setVisible(True)
        elif "Swarm Consensus: Max retries exhausted" in status or "Verification FAILED" in status:
            self._consensus_badge.setText("🧪 Swarm Consensus: Verification Failed (Exhausted)")
            self._consensus_badge.setStyleSheet("background: #7f1d1d; color: #fca5a5; border-radius: 4px; padding: 2px 6px; font-weight: bold; font-size: 11px;")
            self._consensus_badge.setVisible(True)

    def _toggle_detail(self) -> None:
        self._expanded = not self._expanded
        self._detail_label.setVisible(self._expanded)
        self._toggle.setText("▼" if self._expanded else "▶")


class MessageBubble(QFrame):
    """Single chat message bubble (user or assistant)."""

    _USER_STYLE = (
        "QFrame#msgBubble { background:#1d3a2f; border:1px solid #10b981;"
        "border-radius:12px; padding:10px 14px; }"
    )
    _ASST_STYLE = (
        "QFrame#msgBubble { background:#1e1e22; border:1px solid #2e2e36;"
        "border-radius:12px; padding:10px 14px; }"
    )
    _ERR_STYLE = (
        "QFrame#msgBubble { background:#2a1010; border:1px solid #ef4444;"
        "border-radius:12px; padding:10px 14px; }"
    )

    def __init__(
        self,
        role: Role,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("msgBubble")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

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
