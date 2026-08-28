from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QTextBrowser, QPushButton, QScrollArea, QFrame, QLabel, QSizePolicy, QToolButton
)
from PySide6.QtCore import Qt, QSize, Signal
from axiom.gui.styles.theme_manager import ThemeManager
import markdown

class AutoExpandTextEdit(QTextEdit):
    return_pressed = Signal()

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlaceholderText("Ask AXIOM...")
        self.textChanged.connect(self.adjust_height)
        self.setFixedHeight(24) 

    def adjust_height(self):
        doc_height = self.document().size().height()
        new_height = max(24, min(int(doc_height) + 4, 120))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event):
        from PySide6.QtCore import Qt
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event) # Shift+Enter = Newline
            else:
                self.return_pressed.emit() # Enter = Send
                event.accept()
        else:
            super().keyPressEvent(event)

class ModernInputBar(QFrame):
    message_ready = Signal(str)
    image_attached = Signal(str)
    mic_toggled = Signal(bool)

    def __init__(self, theme_manager: ThemeManager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(48)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 0, 16, 0)
        self.layout.setSpacing(12)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attach_btn")
        self.attach_btn.setFixedSize(32, 32)
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.input_area = AutoExpandTextEdit(theme_manager)
        self.input_edit = self.input_area  # ALIAS for main_window.py
        
        self.mic_btn = QToolButton()
        self.mic_btn.setText("🎤")
        self.mic_btn.setFixedSize(28, 28)
        self.mic_btn.setCheckable(True)
        self.mic_btn.toggled.connect(self.mic_toggled.emit)
        
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._on_send)
        
        self.input_area.return_pressed.connect(self.send_btn.click)

        self.layout.addWidget(self.attach_btn, 0, Qt.AlignmentFlag.AlignBottom)
        self.layout.addWidget(self.input_area, 1, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(self.mic_btn, 0, Qt.AlignmentFlag.AlignBottom)
        self.layout.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._apply_theme()

    def _apply_theme(self):
        # Delegate styles to base.qss.template
        pass
        
    def _on_send(self):
        text = self.input_area.toPlainText().strip()
        if text:
            self.message_ready.emit(text)
            self.input_area.clear()

class ModernChatBubble(QFrame):
    def __init__(self, role: str, text: str, theme_manager: ThemeManager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("chat_bubble")
        self.role = role
        self.setProperty("role", role)
        self._raw_text = text

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(0)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.document().setDocumentMargin(0)
        self.text_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Size policy is intentionally left at default (Preferred/Preferred).
        # resizeEvent below takes over height management precisely.
        
        html_content = markdown.markdown(self._raw_text, extensions=['fenced_code', 'tables'])
        self.text_browser.setHtml(html_content)
        
        self.layout.addWidget(self.text_browser)
        self._apply_theme()

    def _apply_theme(self):
        # Delegate styles to base.qss.template
        pass

    def set_text(self, text: str):
        self._raw_text = text
        html_content = markdown.markdown(self._raw_text, extensions=['fenced_code', 'tables'])
        self.text_browser.setHtml(html_content)
        # Trigger a height recalculation after content changes.
        self.resizeEvent(None)

    def resizeEvent(self, event):
        if event is not None:
            super().resizeEvent(event)
        vp_width = self.text_browser.viewport().width()
        if vp_width > 0:
            # Force text reflow to the exact viewport width so Qt knows the height.
            self.text_browser.document().setTextWidth(vp_width)
        exact_h = int(self.text_browser.document().size().height())
        if exact_h > 0:
            self.text_browser.setFixedHeight(exact_h)
            self.setFixedHeight(exact_h + 24)  # 24px = 12px top + 12px bottom padding

class ModernChatDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = getattr(parent, 'theme_manager', ThemeManager())
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(32, 0, 32, 24)
        self.layout.setSpacing(24)

        from axiom.gui.widgets.swarm_hud import SwarmHUD
        self.swarm_hud = SwarmHUD()
        if hasattr(self, 'swarm_hud') and self.swarm_hud is not None:
            self.swarm_hud.hide()
            self.swarm_hud.setObjectName("swarm_hud")
        self.layout.addWidget(self.swarm_hud)
        
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙️")
        top_bar.addWidget(self.settings_btn)
        self.layout.addLayout(top_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("chat_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("chat_scroll_widget")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.chat_layout = self.scroll_layout
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Sentinel stretch — keeps bubbles pinned to natural height.
        # add_bubble inserts before this item so bubbles never stretch to fill.
        self.scroll_layout.addStretch(1)
        
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.watermark = QLabel("AXIOM v11.2", self.scroll_area.viewport())
        self.watermark.setObjectName("chat_watermark")
        self.watermark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.watermark.lower()
        
        self.layout.addWidget(self.scroll_area)

        self.input_bar = ModernInputBar(self.theme_manager)
        self.layout.addWidget(self.input_bar, 0, Qt.AlignmentFlag.AlignBottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'watermark'):
            self.watermark.resize(self.scroll_area.viewport().size())

    def attach_image(self, filepath: str):
        pass # mock
        
    def clear_attachment(self):
        pass # mock
        
    def _scroll_to_bottom(self):
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def add_bubble(self, role: str, text: str):
        if text.strip() == "AXIOM v11.2":
            return None

        if text.strip() == "":
            text = "<i>[Executing Tool...]</i>"

        if self.watermark.isVisible():
            self.watermark.hide()

        bubble = ModernChatBubble(role, text, self.theme_manager)

        wrapper = QHBoxLayout()
        if role == "user":
            wrapper.addStretch()
            wrapper.addWidget(bubble)
        else:
            wrapper.addWidget(bubble)
            wrapper.addStretch()

        # Insert before the sentinel stretch so bubbles don't expand vertically.
        self.scroll_layout.insertLayout(self.scroll_layout.count() - 1, wrapper)
        self._scroll_to_bottom()
        return bubble
