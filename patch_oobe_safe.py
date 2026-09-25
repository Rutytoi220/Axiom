import re

with open("axiom/gui/widgets/oobe_wizard.py", "r") as f:
    content = f.read()

# 1. Inject ThemeCard
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
        
        self.preview = QFrame()
        self.preview.setStyleSheet(f"border-top-left-radius: 8px; border-top-right-radius: 8px; {gradient_css}")
        self.preview.setMinimumHeight(100)
        
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

    def mousePressEvent(self, event):
        self.clicked.emit(self.card_key)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
"""
content = content.replace("class SelectionCard", theme_card_code + "\nclass SelectionCard")

# 2. Update _build_theme_page
old_theme_grid = """        hl = QHBoxLayout()
        hl.setSpacing(20)

        self.theme_cards = []
        themes = [
            ("nothing", "Nothing OS", "Brutalist, high contrast"),
            ("cyberpunk", "Cyberpunk", "Neon dark"),
            ("minimalist", "Minimalist", "Apple-like, clean")
        ]

        for t_id, t_name, t_desc in themes:
            card = SelectionCard(t_id, t_name, t_desc)
            card.clicked.connect(self._on_theme_selected)
            hl.addWidget(card)
            self.theme_cards.append(card)

        l.addLayout(hl)"""

new_theme_grid = """        grid = QGridLayout()
        grid.setSpacing(20)

        self.theme_cards = []
        themes = [
            ("axiom_pro", "AXIOM Pro", "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161B22, stop:1 #0D1117); border-bottom: 2px solid #A78BFA;"),
            ("nordic", "Nordic Frost", "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2E3440, stop:1 #3B4252); border-bottom: 2px solid #88C0D0;"),
            ("jarvis", "J.A.R.V.I.S", "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A0F0D, stop:1 #050806); border-bottom: 2px solid #00FF41;")
        ]

        row, col = 0, 0
        for t_id, t_name, t_grad in themes:
            card = ThemeCard(t_id, t_name, t_grad)
            card.clicked.connect(self._on_theme_selected)
            grid.addWidget(card, row, col)
            self.theme_cards.append(card)
            col += 1
            if col > 2:
                col = 0
                row += 1

        l.addLayout(grid)"""
content = content.replace(old_theme_grid, new_theme_grid)

old_theme_reload = """        for card in self.theme_cards:
            card.set_selected(card.card_key == theme_name)"""
new_theme_reload = """        for card in self.theme_cards:
            card.set_selected(card.card_key == theme_name)
            
        # LIVE RELOAD
        from axiom.gui.styles.theme_manager import get_theme_manager
        from PySide6.QtWidgets import QApplication
        tm = get_theme_manager()
        tm.apply_theme(QApplication.instance(), theme_name)"""
content = content.replace(old_theme_reload, new_theme_reload)

# 3. Replace Next buttons safely
def strip_next_btn(page_name, next_idx=None, finish=False):
    global content
    if not finish:
        btn_block = f"""        btn = QPushButton("Next")
        btn.setObjectName("oobe_primary_btn")
        btn.setFixedWidth(150)
        btn.clicked.connect(lambda: self.stack.setCurrentIndex({next_idx}))

        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn)
        l.addLayout(hl)"""
        # Sometimes variable is `h_btn`
        btn_block2 = btn_block.replace("hl = ", "h_btn = ").replace("hl.add", "h_btn.add")
        content = content.replace(btn_block, "")
        content = content.replace(btn_block2, "")
    else:
        btn_block3 = """        btn = QPushButton("Finish Setup & Boot AXIOM")
        btn.setObjectName("oobe_primary_btn")
        btn.setFixedWidth(200)
        btn.clicked.connect(self._on_finish)

        h_btn = QHBoxLayout()
        h_btn.addStretch()
        h_btn.addWidget(btn)
        l.addLayout(h_btn)"""
        content = content.replace(btn_block3, "")

strip_next_btn("welcome", 1)
strip_next_btn("theme", 2)
strip_next_btn("persona", 3)
strip_next_btn("directives", finish=True)

# 4. Inject Toolbar
init_injection = """
        self._build_welcome_page()
        self._build_theme_page()
        self._build_persona_page()
        self._build_directives_page()

        # UNIFIED TOOLBAR
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        
        self.nav_btn = QPushButton("Next")
        self.nav_btn.setObjectName("oobe_primary_btn")
        self.nav_btn.setFixedWidth(200)
        self.nav_btn.clicked.connect(self._on_nav_clicked)
        
        toolbar.addWidget(self.nav_btn)
        self.layout.addLayout(toolbar)
        
        self.stack.currentChanged.connect(self._on_page_changed)
"""
content = content.replace(
"""        self._build_welcome_page()
        self._build_theme_page()
        self._build_persona_page()
        self._build_directives_page()""", init_injection)

# 5. Add methods
methods = """
    def _on_page_changed(self, index: int):
        if index == self.stack.count() - 1:
            self.nav_btn.setText("Finish Setup & Boot AXIOM")
        else:
            self.nav_btn.setText("Next")

    def _on_nav_clicked(self):
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
        else:
            self._on_finish()
"""
content = content.replace("    def _build_welcome_page(self):", methods + "\n    def _build_welcome_page(self):")

with open("axiom/gui/widgets/oobe_wizard.py", "w") as f:
    f.write(content)

