import sys

with open("axiom/gui/bridge.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("    tools_received: Signal = Signal(list)"):
        new_lines.append(line)
        new_lines.append("    synapse_event: Signal = Signal(object)\n")
    elif line == '        elif event_type.startswith("swarm."):\n':
        new_lines.append('        elif event_type.startswith("synapse."):\n')
        new_lines.append('            class _Evt:\n')
        new_lines.append('                def __init__(self, t, d):\n')
        new_lines.append('                    self.event_type = t\n')
        new_lines.append('                    self.data = d\n')
        new_lines.append('            self.synapse_event.emit(_Evt(event_type, payload))\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/bridge.py", "w") as f:
    f.writelines(new_lines)

