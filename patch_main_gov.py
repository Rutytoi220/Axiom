import sys

with open("axiom/gui/main_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "        self.governor_btn.clicked.connect(self._open_governor_dialog)\n":
        new_lines.append("        self.governor_btn.setCheckable(True)\n")
        new_lines.append("        self.governor_btn.setChecked(False)\n")
        new_lines.append("        self.governor_btn.setText(\"⚡ Governor: Inactive\")\n")
        new_lines.append("        self.governor_btn.setStyleSheet(\"border: none; color: #a6adc8; font-weight: bold;\")\n")
        new_lines.append("        self.governor_btn.clicked.connect(self._toggle_strict_mode)\n")
    elif line == "        self._bridge.axiomfs_status.connect(self._on_axiomfs_status)\n":
        new_lines.append(line)
        new_lines.append("        self._bridge.governor_approval_requested.connect(self._on_approval_requested)\n")
    elif line == "    def _open_governor_dialog(self) -> None:\n":
        new_lines.append("    def _toggle_strict_mode(self) -> None:\n")
        new_lines.append("        is_strict = self.governor_btn.isChecked()\n")
        new_lines.append("        if is_strict:\n")
        new_lines.append("            self.governor_btn.setText(\"⚡ Governor: Active\")\n")
        new_lines.append("            self.governor_btn.setStyleSheet(\"border: none; color: #f9e2af; font-weight: bold;\")\n")
        new_lines.append("        else:\n")
        new_lines.append("            self.governor_btn.setText(\"⚡ Governor: Inactive\")\n")
        new_lines.append("            self.governor_btn.setStyleSheet(\"border: none; color: #a6adc8; font-weight: bold;\")\n")
        new_lines.append("        self._bridge.set_strict_mode(is_strict)\n\n")
        
        new_lines.append("    @Slot(str, dict)\n")
        new_lines.append("    def _on_approval_requested(self, tool_name: str, arguments: dict) -> None:\n")
        new_lines.append("        from axiom.gui.widgets.governor_dialog import ExecutionGateDialog\n")
        new_lines.append("        dlg = ExecutionGateDialog(tool_name, arguments, self)\n")
        new_lines.append("        approved = dlg.exec_() == QDialog.Accepted\n")
        new_lines.append("        self._bridge.send_approval_response(tool_name, approved)\n\n")
        
        # Skip original _open_governor_dialog
        new_lines.append(line)
    elif line == "        from axiom.gui.widgets.governor_dialog import GovernorDialog\n" and "dlg = GovernorDialog(self)" in lines[i+1]:
        pass # Skip these 3 lines
    elif "dlg = GovernorDialog(self)" in line and "from axiom.gui.widgets.governor_dialog" in lines[i-1]:
        pass
    elif "dlg.exec_()" in line and "dlg = GovernorDialog(self)" in lines[i-1]:
        pass
    else:
        new_lines.append(line)

with open("axiom/gui/main_window.py", "w") as f:
    f.writelines(new_lines)

