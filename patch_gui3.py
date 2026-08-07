import sys

with open("axiom/gui/main_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "        self._status_memory = QLabel(\"🧠 Memory: Active (0 Chunks)\")\n":
        new_lines.append(line)
        new_lines.append("        self._status_axiomfs = QLabel(\"AxiomFS: Offline\")\n")
        new_lines.append("        self._status_axiomfs.setStyleSheet(\"color: #a6e3a1; font-weight: bold;\")\n")
    elif line == "        sb.addPermanentWidget(self.governor_btn)\n":
        new_lines.append("        sb.addPermanentWidget(self._status_axiomfs)\n")
        new_lines.append(line)
    elif line == "        self._bridge.synapse_event.connect(self._synapse_graph.handle_telemetry)\n":
        new_lines.append(line)
        new_lines.append("        self._bridge.axiomfs_status.connect(self._on_axiomfs_status)\n")
    elif line == "    def _on_daemon_connection_changed(self, state: str) -> None:\n":
        new_lines.append("    @Slot(str)\n")
        new_lines.append("    def _on_axiomfs_status(self, status: str) -> None:\n")
        new_lines.append("        self._status_axiomfs.setText(f\"AxiomFS: {status}\")\n\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/main_window.py", "w") as f:
    f.writelines(new_lines)

