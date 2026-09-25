import re

with open("axiom/gui/widgets/modern_chat.py", "r") as f:
    content = f.read()

# Locate the ModernInputBar __init__ method
# Find `from PySide6.QtWidgets import QStyle`

imports_and_paths = """        from PySide6.QtGui import QIcon
        from PySide6.QtCore import QSize
        import os
        from pathlib import Path
        
        # Resolve absolute path to assets/icons
        base_dir = Path(__file__).parent.parent.resolve()
        icons_dir = base_dir / "assets" / "icons"
"""

content = content.replace("        from PySide6.QtWidgets import QStyle", imports_and_paths)

# Replace attach btn icon
content = content.replace(
    'self.attach_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))',
    'self.attach_btn.setIcon(QIcon(str(icons_dir / "attach.svg")))\n        self.attach_btn.setIconSize(QSize(20, 20))'
)

# Replace mic btn icon
content = content.replace(
    'self.mic_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))',
    'self.mic_btn.setIcon(QIcon(str(icons_dir / "mic.svg")))\n        self.mic_btn.setIconSize(QSize(20, 20))'
)

# Replace send btn icon
content = content.replace(
    'self.send_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))',
    'self.send_btn.setIcon(QIcon(str(icons_dir / "send.svg")))\n        self.send_btn.setIconSize(QSize(20, 20))'
)

with open("axiom/gui/widgets/modern_chat.py", "w") as f:
    f.write(content)
print("Patched modern_chat.py.")
