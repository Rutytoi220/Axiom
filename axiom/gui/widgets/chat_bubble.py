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
        self.setStyleSheet(
            "QFrame#toolPill { background:#1e1e22; border:1px solid #2e2e36; "
            "border-radius:6px; padding:2px 8px; }"
        )
        self._expanded = False
        self._detail_text = status

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._icon = QLabel("⚙️")
        layout.addWidget(self._icon)

        self._summary = QLabel(f"<b>{html.escape(tool_id)}</b>")
        self._summary.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        layout.addWidget(self._summary, 1)

        self._toggle = QToolButton()
        self._toggle.setText("▶")
        self._toggle.setStyleSheet(
            "QToolButton { color:#a0a0b0; border:none; font-size:10px; }"
        )
        self._toggle.clicked.connect(self._toggle_detail)
        layout.addWidget(self._toggle)

        self._detail_label = QLabel(html.escape(status))
        self._detail_label.setStyleSheet(
            "color:#8888aa; font-size:11px; font-family:monospace;"
        )
        self._detail_label.setWordWrap(True)
        self._detail_label.setVisible(False)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addLayout(layout)
        outer.addWidget(self._detail_label)
        self.setLayout(outer)

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

        if role == "user":
            self.setStyleSheet(self._USER_STYLE)
        elif role == "tool":
            self.setStyleSheet(self._ERR_STYLE)
        else:
            self.setStyleSheet(self._ASST_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Role badge + timestamp
        header = QHBoxLayout()
        role_label = QLabel({"user": "You", "assistant": "AXIOM", "tool": "Tool"}.get(role, role))
        role_label.setStyleSheet(
            f"font-weight:600; font-size:12px; color:"
            f"{'#10b981' if role == 'assistant' else '#f59e0b' if role == 'user' else '#ef4444'};"
        )
        ts = QLabel(time.strftime("%H:%M"))
        ts.setStyleSheet("font-size:10px; color:#4a4a5a;")
        header.addWidget(role_label)
        header.addStretch()
        header.addWidget(ts)
        layout.addLayout(header)

        # Main text
        self._body = QLabel()
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.RichText)
        self._body.setOpenExternalLinks(True)
        self._body.setStyleSheet("color:#f0f0f5; font-size:13px; line-height:1.5;")
        self._body.setText(text)
        layout.addWidget(self._body)

    def set_text(self, text: str) -> None:
        """Update the bubble body (used for streaming)."""
        self._body.setText(text)

    def append_text(self, chunk: str) -> None:
        """Append a streamed chunk to the existing body text."""
        self._body.setText(self._body.text() + html.escape(chunk))
