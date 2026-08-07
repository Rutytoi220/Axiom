import sys

with open("axiom/gui/main_window.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "        self._bridge.swarm_agent_completed.connect(self._on_swarm_completed)\n":
        new_lines.append(line)
        new_lines.append("        self._bridge.synapse_event.connect(self._synapse_graph.handle_telemetry)\n")
    elif line == "    def submit_prompt(self, prompt: str) -> None:\n":
        new_lines.append(line)
        new_lines.append("        if hasattr(self, '_synapse_graph'):\n")
        new_lines.append("            self._synapse_graph.reset_graph()\n")
    else:
        new_lines.append(line)

with open("axiom/gui/main_window.py", "w") as f:
    f.writelines(new_lines)

