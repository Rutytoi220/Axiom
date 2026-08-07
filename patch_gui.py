import sys

with open("axiom/gui/main_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("from axiom.gui.widgets.message_bubble import MessageBubble"):
        new_lines.append(line)
        new_lines.append("from axiom.gui.widgets.synapse_graph import SynapseGraph\n")
    elif line == "        self._build_expert_dock()\n":
        new_lines.append(line)
        new_lines.append("        self._build_synapse_dock()\n")
    elif line == "    def _build_expert_dock(self) -> None:\n":
        new_lines.append("    def _build_synapse_dock(self) -> None:\n")
        new_lines.append('        """Dock for Synapse Visualizer."""\n')
        new_lines.append("        self._synapse_dock = QDockWidget(\"Synapse Visualizer\", self)\n")
        new_lines.append("        self._synapse_dock.setObjectName(\"synapseDock\")\n")
        new_lines.append("        self._synapse_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)\n")
        new_lines.append("        self._synapse_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)\n")
        new_lines.append("        self._synapse_dock.setMinimumWidth(320)\n")
        new_lines.append("        self._synapse_graph = SynapseGraph(self._synapse_dock)\n")
        new_lines.append("        self._synapse_dock.setWidget(self._synapse_graph)\n")
        new_lines.append("        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._synapse_dock)\n")
        new_lines.append("\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/main_window.py", "w") as f:
    f.writelines(new_lines)

