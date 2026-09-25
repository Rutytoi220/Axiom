import re

with open("axiom/gui/widgets/oobe_wizard.py", "r") as f:
    content = f.read()

theme_card_code = """
class ThemeCard(QFrame):
    clicked = Signal(str)

    def __init__(self, key: str, display_name: str, gradient_css: str):
        super().__init__()
        self.card_key = key
        self.setProperty("class", "Card")
        self.setProperty("selected", False)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # The visual preview box
        self.preview = QFrame()
        self.preview.setStyleSheet(f"border-top-left-radius: 8px; border-top-right-radius: 8px; {gradient_css}")
        self.preview.setMinimumHeight(100)
        
        # The text label container
        text_container = QFrame()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel(display_name)
        title.setObjectName("oobe_card_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_layout.addWidget(title)
        
        layout.addWidget(self.preview)
        layout.addWidget(text_container)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(220, 160)
        # We don't set fixed size so it scales nicely

    def mousePressEvent(self, event):
        self.clicked.emit(self.card_key)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
"""

if "class ThemeCard" not in content:
    content = content.replace("class SelectionCard", theme_card_code + "\nclass SelectionCard")

with open("axiom/gui/widgets/oobe_wizard.py", "w") as f:
    f.write(content)
