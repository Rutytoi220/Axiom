import sys

# 1. Fix typo in themes.qss
with open("axiom/gui/styles/themes.qss", "r") as f:
    text = f.read()
text = text.replace("     cing: 0.08em;", "    letter-spacing: 0.08em;")
with open("axiom/gui/styles/themes.qss", "w") as f:
    f.write(text)

# 2. Update oobe_window.py
with open("axiom/gui/windows/oobe_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "layout.setContentsMargins(" in line:
        new_lines.append("        layout.setContentsMargins(20, 20, 20, 20)\n")
    elif "layout.setSpacing(" in line and "hex_layout" not in line and "color_layout" not in line and "voice_layout" not in line:
        new_lines.append("        layout.setSpacing(15)\n")
    elif "self.hex_input = QLineEdit()" in line:
        new_lines.append(line)
        new_lines.append("        self.hex_input.setMinimumHeight(32)\n")
    elif "self.init_btn.setObjectName(\"initBtn\")" in line:
        new_lines.append(line)
        new_lines.append("        self.init_btn.setMinimumHeight(40)\n")
    else:
        new_lines.append(line)

with open("axiom/gui/windows/oobe_window.py", "w") as f:
    f.writelines(new_lines)
