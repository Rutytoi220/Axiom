import sys

with open("axiom/gui/main_window.py", "r") as f:
    text = f.read()

old_build = """    def _build_central_widget(self) -> None:
        \"\"\"Scrollable chat viewport with message bubbles.\"\"\"
        container = QWidget()
        self.setCentralWidget(container)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()"""

new_build = """    def _build_central_widget(self) -> None:
        \"\"\"Scrollable chat viewport with message bubbles.\"\"\"
        container = QWidget()
        self.setCentralWidget(container)
        
        # AXIOM Background Watermark
        self.logo_widget = QLabel("AXIOM", container)
        from PySide6.QtGui import QFont
        font = QFont("Inter", 72, QFont.Weight.Bold)
        self.logo_widget.setFont(font)
        # Fix the black box glitch by ensuring transparent background and border none
        self.logo_widget.setStyleSheet("color: rgba(255, 255, 255, 0.05); background-color: transparent; border: none;")
        self.logo_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_widget.lower() # Send to back
        # Use an event filter or resize event to keep it centered if needed, but for now we just let it sit
        self.logo_widget.resize(800, 600)
        
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        # Make the scroll area transparent so the watermark shows through
        self._scroll.setStyleSheet("background-color: transparent; border: none;")
        self._scroll.viewport().setAutoFillBackground(False)"""

text = text.replace(old_build, new_build)

old_bubble = """    def _add_bubble(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, html.escape(text))  # type: ignore[arg-type]
        # Insert before the trailing stretch
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)"""

new_bubble = """    def _add_bubble(self, role: str, text: str) -> MessageBubble:
        if hasattr(self, 'logo_widget') and self.logo_widget.isVisible():
            self.logo_widget.hide()
            
        bubble = MessageBubble(role, html.escape(text))  # type: ignore[arg-type]
        # Insert before the trailing stretch
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)"""

text = text.replace(old_bubble, new_bubble)

# Also ensure QWidget#chatContainer is transparent in case we are trying to see through
old_scroll_end = """        self._chat_layout.addStretch()  # pushes bubbles to bottom

        self._scroll.setWidget(self._chat_container)"""

new_scroll_end = """        self._chat_layout.addStretch()  # pushes bubbles to bottom
        self._chat_container.setStyleSheet("background-color: transparent; border: none;")
        
        self._scroll.setWidget(self._chat_container)"""

text = text.replace(old_scroll_end, new_scroll_end)


with open("axiom/gui/main_window.py", "w") as f:
    f.write(text)
