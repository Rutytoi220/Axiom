import re

with open("axiom/gui/widgets/modern_chat.py", "r") as f:
    content = f.read()

content = content.replace(
    'self.mic_btn.setIcon(QIcon(str(icons_dir / "mic.svg")))',
    'self.mic_btn.setObjectName("mic_btn")\n        self.mic_btn.setIcon(QIcon(str(icons_dir / "mic.svg")))'
)

content = content.replace(
    'self.send_btn.setIcon(QIcon(str(icons_dir / "send.svg")))',
    'self.send_btn.setObjectName("send_btn")\n        self.send_btn.setIcon(QIcon(str(icons_dir / "send.svg")))'
)

with open("axiom/gui/widgets/modern_chat.py", "w") as f:
    f.write(content)

print("Added object names.")
