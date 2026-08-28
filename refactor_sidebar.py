import re

with open('axiom/gui/widgets/modern_sidebar.py', 'r') as f:
    content = f.read()

# Replace _apply_theme in SegmentedControl
seg_apply_theme = """    def _apply_theme(self):
        # Delegate styles to base.qss.template
        # The dynamic tokens are no longer hardcoded here
        pass"""
content = re.sub(r'    def _apply_theme\(self\):\n        self\.setStyleSheet.*?\}\n        "\)\n', seg_apply_theme + '\n', content, flags=re.DOTALL)

# Replace _apply_theme in ModernSidebar
sidebar_apply_theme = """    def _apply_theme(self):
        pass"""
content = re.sub(r'    def _apply_theme\(self\):\n        self\.setStyleSheet\(f"""\n            ModernSidebar \{\{.*?QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical \{\n                border: none;\n                background: none;\n            \}\n        """\)\n', sidebar_apply_theme + '\n', content, flags=re.DOTALL)

# Remove `self.t` initialization
content = content.replace("        self.t = theme_manager.theme\n", "")
content = content.replace("        self.t = self.theme_manager.theme\n", "")

with open('axiom/gui/widgets/modern_sidebar.py', 'w') as f:
    f.write(content)
