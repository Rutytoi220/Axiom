"""AXIOM Desktop v3.0 — Next-Gen Modern Chat UI."""

import html
import os
import re
from PySide6.QtCore import Qt, Signal, QSize, Slot, QTimer
from PySide6.QtGui import QFont, QCursor, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QScrollArea,
    QSizePolicy, QToolButton, QTextEdit, QTextBrowser, QApplication,
    QMenu, QFileDialog
)
from PySide6.QtGui import QFont, QCursor, QAction

def _basic_markdown(raw_text: str) -> str:
    safe_text = html.escape(raw_text)
    
    # Code blocks
    safe_text = re.sub(
        r"```(.*?)```", 
        lambda m: f"<pre style='background-color: #1E1E1E; color: #E0E0E0; padding: 10px; border-radius: 8px; font-family: monospace;'>{m.group(1)}</pre>", 
        safe_text, 
        flags=re.DOTALL
    )
    
    # Inline code
    safe_text = re.sub(
        r"`([^`\n]+)`", 
        r"<code style='background-color: #1E1E1E; color: #E0E0E0; padding: 2px 4px; border-radius: 4px; font-family: monospace;'>\1</code>", 
        safe_text
    )
    
    # Bold
    safe_text = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", safe_text)
    
    # Newlines
    safe_text = safe_text.replace("\n", "<br>")
    return safe_text

class AutoExpandTextEdit(QTextEdit):
    """A QTextEdit that automatically resizes its height based on document content."""
    
    send_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Ask AXIOM")
        self.setStyleSheet("QTextEdit { background: transparent; border: none; color: #FFFFFF; font-size: 15px; font-family: 'Inter', sans-serif; padding: 8px 0px; }")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textChanged.connect(self._adjust_height)
        self.setMinimumHeight(36)
        self.setMaximumHeight(120)
        self.document().setDocumentMargin(0)
        self.setFixedHeight(36) # Force it to be 36px tall initially

    def _adjust_height(self):
        doc_height = int(self.document().size().height())
        target_height = min(max(doc_height + 16, 36), 120)
        if self.height() != target_height:
            self.setFixedHeight(target_height)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
                event.accept()
        else:
            super().keyPressEvent(event)


class _AttachmentStrip(QFrame):
    """A slim preview strip shown above the input pill when an image is attached."""
    
    dismissed = Signal()   # emitted when user clicks the X
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("attachStrip")
        self.setStyleSheet(
            "QFrame#attachStrip {"
            "  background: #1A1A1A;"
            "  border: 1px solid #333;"
            "  border-radius: 12px;"
            "  padding: 4px 8px;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(72)
        self.setMaximumWidth(750)
        
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(10)
        
        self._thumb = QLabel()
        self._thumb.setFixedSize(52, 52)
        self._thumb.setStyleSheet("border-radius: 8px; background: #2A2A2A;")
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._thumb)
        
        self._filename = QLabel("")
        self._filename.setStyleSheet("color: #CCCCCC; font-size: 12px; font-family: 'Inter', sans-serif;")
        self._filename.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self._filename, 1)
        
        dismiss_btn = QToolButton()
        dismiss_btn.setText("✕")
        dismiss_btn.setFixedSize(22, 22)
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.setStyleSheet(
            "QToolButton { background: #333; border: none; border-radius: 11px;"
            "  color: #999; font-size: 11px; }"
            "QToolButton:hover { background: #ef4444; color: #fff; }"
        )
        dismiss_btn.clicked.connect(self.dismissed)
        row.addWidget(dismiss_btn, 0, Qt.AlignmentFlag.AlignTop)
        
        self.hide()  # hidden until an image is attached
    
    def set_image(self, filepath: str) -> None:
        pixmap = QPixmap(filepath)
        if not pixmap.isNull():
            self._thumb.setPixmap(
                pixmap.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        self._filename.setText(os.path.basename(filepath))
        self.show()
    
    def clear_image(self) -> None:
        self._thumb.clear()
        self._filename.setText("")
        self.hide()


class ModernInputBar(QFrame):
    """The floating Pill shape input bar."""
    
    message_ready = Signal(str)
    image_attached = Signal(str)   # emits the absolute filepath
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inputPill")
        self.setStyleSheet("QFrame#inputPill { border: 1px solid #2A2A2A; border-radius: 24px; background-color: #1E1E1E; margin-bottom: 20px; }")
        self.setMaximumWidth(750)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        # Attachment Button (Left)
        self.attach_btn = QToolButton()
        self.attach_btn.setText("＋")
        self.attach_btn.setFixedSize(36, 36)
        self.attach_btn.setCursor(Qt.PointingHandCursor)
        self.attach_btn.setStyleSheet("QToolButton::menu-indicator { image: none; } QToolButton { border: none; background: transparent; font-size: 18px; color: #a0a0a0; } QToolButton:hover { color: #ffffff; }")
        
        self.attach_menu = QMenu(self)
        self.attach_menu.setStyleSheet("QMenu { background-color: #1A1A1A; color: #E0E0E0; border: 1px solid #333333; border-radius: 8px; padding: 5px; } QMenu::item { padding: 5px 20px; border-radius: 4px; } QMenu::item:selected { background-color: #2A2A2A; }")
        
        upload_action = QAction("📄 Upload Image", self)
        upload_action.triggered.connect(self._on_upload_image)
        self.attach_menu.addAction(upload_action)
        
        vision_action = QAction("👁️ Enable Vision/Camera", self)
        vision_action.triggered.connect(lambda: print("[UI] Enable Vision clicked"))
        self.attach_menu.addAction(vision_action)
        
        tools_action = QAction("🔧 Manage Local Tools", self)
        tools_action.triggered.connect(lambda: print("[UI] Manage Local Tools clicked"))
        self.attach_menu.addAction(tools_action)
        
        self.attach_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.attach_btn.setMenu(self.attach_menu)
        
        layout.addWidget(self.attach_btn, 0, Qt.AlignmentFlag.AlignBottom)
        
        # Auto-expanding Text Edit
        self.input_edit = AutoExpandTextEdit()
        self.input_edit.send_requested.connect(self._on_send)
        layout.addWidget(self.input_edit, 1, Qt.AlignmentFlag.AlignBottom)
        
        # Mic Button (Optional/Right)
        from axiom.gui.config_manager import get_ui_config_manager
        voice_mode = get_ui_config_manager().load().voice_mode
        self.mic_btn = None
        if voice_mode == "push_to_talk":
            self.mic_btn = QToolButton()
            self.mic_btn.setText("🎤")
            self.mic_btn.setFixedSize(36, 36)
            self.mic_btn.setCheckable(True)
            self.mic_btn.setCursor(Qt.PointingHandCursor)
            self.mic_btn.setStyleSheet("QToolButton { border: none; background: transparent; font-size: 18px; color: #a0a0a0; } QToolButton:checked { color: #f59e0b; } QToolButton:hover { color: #ffffff; }")
            layout.addWidget(self.mic_btn, 0, Qt.AlignmentFlag.AlignBottom)
            
        # Send Button (Far Right)
        self.send_btn = QToolButton()
        self.send_btn.setText("↑")
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("QToolButton { border-radius: 16px; background-color: #FFFFFF; color: #000000; font-size: 16px; font-weight: bold; } QToolButton:hover { background-color: #E0E0E0; }")
        self.send_btn.clicked.connect(self._on_send)
        layout.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)

    def _on_send(self):
        text = self.input_edit.toPlainText().strip()
        if text:
            self.message_ready.emit(text)
            self.input_edit.clear()
    
    def _on_upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Image",
            os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
        )
        if path:
            self.image_attached.emit(path)
            
    def set_focus(self):
        self.input_edit.setFocus()


class ModernChatBubble(QWidget):
    """Sleek, minimalist dark mode chat bubble."""
    
    edit_requested = Signal(str)
    
    _USER_STYLE = "QFrame#bubbleFrame { background-color: #2F2F2F; border-radius: 16px; }"
    _ASST_STYLE = "QFrame#bubbleFrame { background-color: transparent; border-radius: 16px; }"
    _ERR_STYLE = "QFrame#bubbleFrame { background-color: #2a1010; border-radius: 16px; border-left: 3px solid #ef4444; }"
    
    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._raw_text = text
        
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 4, 0, 4)
        
        self.bubble_frame = QFrame()
        self.bubble_frame.setObjectName("bubbleFrame")
        self.bubble_frame.setMaximumWidth(700)
        
        if role == "user":
            self.bubble_frame.setStyleSheet(self._USER_STYLE)
            self.bubble_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            outer_layout.addStretch()
            outer_layout.addWidget(self.bubble_frame)
        elif role == "assistant":
            self.bubble_frame.setStyleSheet(self._ASST_STYLE)
            outer_layout.addWidget(self.bubble_frame)
            outer_layout.addStretch()
        else:
            self.bubble_frame.setStyleSheet(self._ERR_STYLE)
            outer_layout.addWidget(self.bubble_frame)
            outer_layout.addStretch()
            
        layout = QVBoxLayout(self.bubble_frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        
        # Determine text color per role
        if role == "user":
            text_color = "#FFFFFF"
        elif role == "assistant":
            text_color = "#EBEBEB"
        else:
            text_color = "#ef4444"
        
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.setFrameShape(QFrame.Shape.NoFrame)
        self.text_browser.setStyleSheet(f"background: transparent; font-family: 'Inter', sans-serif; font-size: 15px; line-height: 1.6; color: {text_color};")
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        
        layout.addWidget(self.text_browser)
        self._refresh_text()
        
        # Options Button (Three dots)
        self.options_btn = QToolButton(self.bubble_frame)
        self.options_btn.setText("⋮")
        self.options_btn.setFixedSize(24, 24)
        self.options_btn.setCursor(Qt.PointingHandCursor)
        self.options_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                color: #666666;
                font-size: 16px;
                font-weight: bold;
                border-radius: 12px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
        """)
        self.options_btn.hide()  # Hidden by default, shown on hover
        
        self._options_menu = QMenu(self)
        self._options_menu.setStyleSheet("QMenu { background-color: #1A1A1A; color: #E0E0E0; border: 1px solid #333333; border-radius: 8px; padding: 4px; } QMenu::item { padding: 5px 16px; border-radius: 4px; } QMenu::item:selected { background-color: #2A2A2A; }")
        
        if role == "user":
            edit_action = QAction("✏️ Edit Message", self)
            edit_action.triggered.connect(self._edit_bubble)
            self._options_menu.addAction(edit_action)
            
        copy_action = QAction("📋 Copy Message", self)
        copy_action.triggered.connect(self._copy_to_clipboard)
        self._options_menu.addAction(copy_action)
        delete_action = QAction("🗑️ Delete Message", self)
        delete_action.triggered.connect(self._delete_bubble)
        self._options_menu.addAction(delete_action)
        self.options_btn.clicked.connect(self._show_options_menu)
        
        # Position button absolutely in top-right corner of bubble
        self.options_btn.move(self.bubble_frame.width() - 30, 8)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'options_btn'):
            self.options_btn.move(self.bubble_frame.width() - 30, 8)

    def enterEvent(self, event):
        if hasattr(self, 'options_btn'):
            self.options_btn.show()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if hasattr(self, 'options_btn'):
            self.options_btn.hide()
        super().leaveEvent(event)
        
    def set_text(self, text: str):
        self._raw_text = text
        self._refresh_text()
        
    def append_text(self, chunk: str):
        self._raw_text += chunk
        self._refresh_text()
        
    def _refresh_text(self):
        html_str = _basic_markdown(self._raw_text)
        self.text_browser.setHtml(html_str)
        
        # Measure ideal width and shrink the bubble to hug the text
        self.text_browser.document().setTextWidth(-1)  # let it be natural
        ideal_width = int(self.text_browser.document().idealWidth()) + 56
        clamped = min(max(ideal_width, 85), 700)
        self.bubble_frame.setMaximumWidth(clamped)
        self.bubble_frame.setFixedWidth(clamped)
        
        # Constrain the text_browser widget itself to prevent defaulting to 640px
        self.text_browser.setMaximumWidth(clamped - 32)
        self.text_browser.document().setTextWidth(clamped - 56)
        
        doc_height = int(self.text_browser.document().size().height())
        self.text_browser.setFixedHeight(doc_height)
        self.bubble_frame.setFixedHeight(doc_height + 24)
    
    def _edit_bubble(self):
        self.edit_requested.emit(self._raw_text)
    
    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self._raw_text)
    
    def _delete_bubble(self):
        self.setParent(None)
        self.deleteLater()
    
    def _show_options_menu(self):
        pos = self.options_btn.mapToGlobal(self.options_btn.rect().bottomLeft())
        self._options_menu.popup(pos)


class ModernChatDisplay(QWidget):
    """The full modern chat viewport holding the scroll area and input pill."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        from axiom.gui.widgets.swarm_hud import SwarmHUD
        self.swarm_hud = SwarmHUD()
        layout.addWidget(self.swarm_hud)
        
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙️")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("QToolButton { background: transparent; border: none; font-size: 18px; color: #a0a0a0; } QToolButton:hover { color: #ffffff; }")
        top_bar.addWidget(self.settings_btn)
        top_bar.setContentsMargins(0, 10, 20, 0)
        layout.addLayout(top_bar)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_area.viewport().setAutoFillBackground(False)
        
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("QWidget { background-color: transparent; border: none; }")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(20, 20, 20, 20)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()
        
        self.scroll_area.setWidget(self.chat_container)
        
        self.logo_widget = QLabel("AXIOM", self.scroll_area.viewport())
        self.logo_widget.setStyleSheet("QLabel { font-family: 'Inter'; font-size: 72px; font-weight: bold; color: rgba(255, 255, 255, 0.05); background-color: transparent; border: none; }")
        self.logo_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_widget.resize(800, 600)
        self.logo_widget.lower()
        
        layout.addWidget(self.scroll_area, 1)
        
        # ── Image Attachment Strip (hidden until user attaches something) ── #
        self.attach_strip = _AttachmentStrip()
        layout.addWidget(self.attach_strip, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        
        self.input_bar = ModernInputBar()
        self.input_bar.image_attached.connect(self.attach_image)
        layout.addWidget(self.input_bar, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        
        # Wire strip dismiss to clear state
        self.attach_strip.dismissed.connect(self._on_dismiss_attachment)
        self._current_attachment_path: str | None = None
        
    def attach_image(self, filepath: str) -> None:
        """Show the image attachment strip and store the path."""
        self._current_attachment_path = filepath
        self.attach_strip.set_image(filepath)
    
    def clear_attachment(self) -> None:
        """Clear the attachment strip and state."""
        self._current_attachment_path = None
        self.attach_strip.clear_image()
    
    def _on_dismiss_attachment(self) -> None:
        self.clear_attachment()

    def add_bubble(self, role: str, text: str) -> ModernChatBubble:
        if self.logo_widget.isVisible():
            self.logo_widget.hide()
            
        bubble = ModernChatBubble(role, text)
        bubble.edit_requested.connect(lambda text: self.input_bar.input_edit.setPlainText(text))
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        return bubble
        
    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

