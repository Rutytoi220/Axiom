import re

with open("axiom/gui/widgets/oobe_wizard.py", "r") as f:
    content = f.read()

# 1. Remove Next/Finish buttons from pages
# We look for blocks like:
# btn = QPushButton("Next")
# ...
# l.addLayout(h_btn)
btn_regex = r'(\s+btn = QPushButton\("Next"\).*?l\.addLayout\(h_btn\))'
content = re.sub(btn_regex, '', content, flags=re.DOTALL)

finish_btn_regex = r'(\s+btn = QPushButton\("Finish Setup & Boot AXIOM"\).*?l\.addLayout\(h_btn\))'
content = re.sub(finish_btn_regex, '', content, flags=re.DOTALL)

# 2. Add toolbar to __init__
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

# 3. Add methods
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

# Inject before _build_welcome_page
content = content.replace("    def _build_welcome_page(self):", methods + "\n    def _build_welcome_page(self):")

with open("axiom/gui/widgets/oobe_wizard.py", "w") as f:
    f.write(content)

