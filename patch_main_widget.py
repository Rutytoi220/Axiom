import sys

with open("axiom/gui/main_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("        self._bridge.governor_approval_requested.connect("):
        new_lines.append(line)
        new_lines.append("        self._bridge.ui_widget_generated.connect(self._on_widget_generated)\n")
    elif line == "    def _on_approval_requested(self, tool_name: str, arguments: dict) -> None:\n":
        new_lines.append("    @Slot(dict)\n")
        new_lines.append("    def _on_widget_generated(self, payload: dict) -> None:\n")
        new_lines.append("        widget_type = payload.get('widget_type', 'unknown')\n")
        new_lines.append("        spec = payload.get('spec', {})\n")
        new_lines.append("        try:\n")
        new_lines.append("            from axiom.gui.widgets.sandbox_container import SandboxContainer\n")
        new_lines.append("            sandbox = SandboxContainer(widget_type, spec, self)\n")
        new_lines.append("            count = self._chat_layout.count()\n")
        new_lines.append("            self._chat_layout.insertWidget(count - 1, sandbox)\n")
        new_lines.append("            self._scroll_to_bottom()\n")
        new_lines.append("        except Exception as e:\n")
        new_lines.append("            print(f'Failed to render widget: {e}')\n\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/main_window.py", "w") as f:
    f.writelines(new_lines)

