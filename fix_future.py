bridge_path = 'axiom/gui/bridge.py'
with open(bridge_path, 'r') as f:
    lines = f.readlines()

future_imports = []
other_lines = []

for line in lines:
    if line.startswith('from __future__ import'):
        future_imports.append(line)
    else:
        other_lines.append(line)

with open(bridge_path, 'w') as f:
    # Write __future__ imports first
    for f_line in future_imports:
        f.write(f_line)
    # Write the rest of the code (including our injected import time)
    for line in other_lines:
        f.write(line)

print("✅ __future__ imports safely moved to the absolute top!")
