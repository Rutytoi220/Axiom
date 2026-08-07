import sys

with open("axiom/gui/bridge.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("    governor_approval_requested: Signal = Signal(str, dict)"):
        new_lines.append(line)
        new_lines.append("    ui_widget_generated: Signal = Signal(dict)\n")
    elif line == '        elif event_type == "governor.approval_requested":\n':
        new_lines.append('        elif event_type == "ui.widget_generated":\n')
        new_lines.append('            self.ui_widget_generated.emit(payload)\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/bridge.py", "w") as f:
    f.writelines(new_lines)

