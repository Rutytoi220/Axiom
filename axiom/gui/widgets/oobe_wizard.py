from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QStackedWidget, QWidget, QComboBox, QPlainTextEdit, QFrame
)
from PySide6.QtCore import Qt, Signal
from axiom.config import get_config

_WIZARD_QSS = """
QDialog {
    background-color: #1E1E2E;
    color: #FFFFFF;
}
QLabel {
    color: #E4E4E7;
    font-family: 'Inter', sans-serif;
}
QLabel#TitleLabel {
    font-size: 32px;
    font-weight: 800;
    color: #FFFFFF;
}
QLabel#SubtitleLabel {
    font-size: 16px;
    color: #A1A1AA;
}
QPushButton {
    background-color: #313244;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #45475A;
}
QPushButton#PrimaryBtn {
    background-color: #2ECC71;
    color: #11111B;
}
QPushButton#PrimaryBtn:hover {
    background-color: #27AE60;
}
QFrame.Card {
    background-color: #313244;
    border-radius: 8px;
    border: 2px solid transparent;
}
QFrame.Card:hover {
    background-color: #45475A;
}
QFrame.Card[selected="true"] {
    border: 2px solid #2ECC71;
}
QComboBox, QPlainTextEdit {
    background-color: #11111B;
    color: #E4E4E7;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 8px;
}
"""

class ThemeCard(QFrame):
    clicked = Signal(str)

    def __init__(self, theme_name: str, display_name: str, desc: str):
        super().__init__()
        self.theme_name = theme_name
        self.setProperty("class", "Card")
        self.setProperty("selected", False)
        
        layout = QVBoxLayout(self)
        
        title = QLabel(display_name)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        subtitle = QLabel(desc)
        subtitle.setStyleSheet("color: #A1A1AA; font-size: 12px;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(220, 150)
        
    def mousePressEvent(self, event):
        self.clicked.emit(self.theme_name)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        # Force style re-evaluation
        self.style().unpolish(self)
        self.style().polish(self)


class OobeWizardDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AXIOM Setup Wizard")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(800, 600)
        self.setStyleSheet(_WIZARD_QSS)

        self.config = get_config()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self._build_welcome_page()
        self._build_theme_page()
        self._build_persona_page()
        self._build_directives_page()

    def _build_welcome_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        l.addStretch()
        
        title = QLabel("Welcome to AXIOM.")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sub = QLabel("Let's configure your sovereign desktop agent.")
        sub.setObjectName("SubtitleLabel")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        l.addWidget(title)
        l.addWidget(sub)
        l.addStretch()
        
        btn = QPushButton("Next")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn)
        l.addLayout(hl)
        
        self.stack.addWidget(page)

    def _build_theme_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Choose Your Aesthetic")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        l.addSpacing(40)
        
        hl = QHBoxLayout()
        hl.setSpacing(20)
        
        self.theme_cards = []
        themes = [
            ("nothing", "Nothing OS", "Brutalist, high contrast"),
            ("cyberpunk", "Cyberpunk", "Neon dark"),
            ("minimalist", "Minimalist", "Apple-like, clean")
        ]
        
        for t_id, t_name, t_desc in themes:
            card = ThemeCard(t_id, t_name, t_desc)
            card.clicked.connect(self._on_theme_selected)
            hl.addWidget(card)
            self.theme_cards.append(card)
            
        l.addLayout(hl)
        l.addStretch()
        
        # Default selection
        self._on_theme_selected("minimalist")
        
        btn = QPushButton("Next")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)

    def _on_theme_selected(self, theme_name: str):
        self.config.theme = theme_name
        for card in self.theme_cards:
            card.set_selected(card.theme_name == theme_name)

    def _build_persona_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Persona & Behavior")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        l.addSpacing(20)
        
        # Presets
        l.addWidget(QLabel("Presets:"))
        preset_layout = QHBoxLayout()
        presets = [
            ("The Engineer", "highly_formal", "phd_level"),
            ("The Assistant", "balanced", "standard"),
            ("The Scholar", "highly_formal", "academic"),
            ("The Buddy", "casual_snarky", "explain_like_im_5")
        ]
        
        for p_name, p_tone, p_complex in presets:
            btn = QPushButton(p_name)
            btn.clicked.connect(lambda checked, t=p_tone, c=p_complex: self._apply_persona_preset(t, c))
            preset_layout.addWidget(btn)
            
        l.addLayout(preset_layout)
        l.addSpacing(30)
        
        # Customization
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Highly Formal", "Balanced", "Casual/Snarky"])
        
        self.complex_combo = QComboBox()
        self.complex_combo.addItems(["Explain like I'm 5", "Standard", "PhD Level", "Academic"])
        
        l.addWidget(QLabel("Tone:"))
        l.addWidget(self.tone_combo)
        l.addSpacing(15)
        l.addWidget(QLabel("Complexity:"))
        l.addWidget(self.complex_combo)
        
        l.addStretch()
        
        # Default combo
        self.tone_combo.setCurrentText("Balanced")
        self.complex_combo.setCurrentText("Standard")
        
        btn = QPushButton("Next")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)
        
    def _apply_persona_preset(self, tone: str, complexity: str):
        tone_map = {
            "highly_formal": "Highly Formal",
            "balanced": "Balanced",
            "casual_snarky": "Casual/Snarky"
        }
        complex_map = {
            "explain_like_im_5": "Explain like I'm 5",
            "standard": "Standard",
            "phd_level": "PhD Level",
            "academic": "Academic"
        }
        self.tone_combo.setCurrentText(tone_map.get(tone, "Balanced"))
        self.complex_combo.setCurrentText(complex_map.get(complexity, "Standard"))

    def _build_directives_page(self):
        page = QWidget()
        l = QVBoxLayout(page)
        
        title = QLabel("Global System Instructions")
        title.setObjectName("TitleLabel")
        l.addWidget(title)
        
        sub = QLabel("Special Directives that AXIOM will follow for all tasks.")
        sub.setObjectName("SubtitleLabel")
        l.addWidget(sub)
        l.addSpacing(20)
        
        self.directives_input = QPlainTextEdit()
        self.directives_input.setPlaceholderText("e.g., Always provide a confidence percentage for factual answers. Never use emojis.")
        l.addWidget(self.directives_input)
        
        l.addStretch()
        
        btn = QPushButton("Finish & Boot AXIOM")
        btn.setObjectName("PrimaryBtn")
        btn.setFixedWidth(200)
        btn.clicked.connect(self._on_finish)
        
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)
        
        self.stack.addWidget(page)

    def _on_finish(self):
        # Save all settings to config
        self.config.persona_tone = self.tone_combo.currentText().lower()
        self.config.persona_complexity = self.complex_combo.currentText().lower()
        self.config.special_instructions = self.directives_input.toPlainText()
        
        self.config.oobe_completed = True
        self.config.save()
        
        self.accept()
