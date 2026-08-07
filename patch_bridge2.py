import sys

with open("axiom/gui/bridge.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("    synapse_event: Signal = Signal(object)"):
        new_lines.append(line)
        new_lines.append("    axiomfs_status: Signal = Signal(str)\n")
    elif line == '        elif event_type.startswith("swarm."):\n':
        new_lines.append('        elif event_type == "axiomfs.status":\n')
        new_lines.append('            self.axiomfs_status.emit(payload.get("status", "Unknown"))\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/bridge.py", "w") as f:
    f.writelines(new_lines)

