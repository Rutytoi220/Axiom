import re

with open('axiom/gui/widgets/modern_chat.py', 'r') as f:
    content = f.read()

# Replace AutoExpandTextEdit init
content = content.replace("        self.t = theme_manager.theme\n", "")

# Replace _apply_theme in ModernInputBar
inputbar_apply_theme = """    def _apply_theme(self):
        # Delegate styles to base.qss.template
        pass"""
content = re.sub(r'    def _apply_theme\(self\):\n        self\.setStyleSheet\(f"""\n            ModernInputBar \{\{.*?\}\}\n        """\)\n', inputbar_apply_theme + '\n', content, flags=re.DOTALL)

# Replace _apply_theme in ModernChatBubble
chatbubble_apply_theme = """    def _apply_theme(self):
        # Delegate styles to base.qss.template
        pass"""
content = re.sub(r'    def _apply_theme\(self\):\n        bg_color = self\.t\.colors\.bg_surface_active if self\.role == "user" else self\.t\.colors\.bg_surface\n        border = self\.t\.colors\.border_default if self\.role == "user" else self\.t\.colors\.border_strong\n        \n        self\.setStyleSheet\(f"""\n            ModernChatBubble \{\{.*?\}\}\n        """\)\n', chatbubble_apply_theme + '\n', content, flags=re.DOTALL)

with open('axiom/gui/widgets/modern_chat.py', 'w') as f:
    f.write(content)
