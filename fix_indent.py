import os

bridge_path = 'axiom/gui/bridge.py'
with open(bridge_path, 'r') as f:
    lines = f.readlines()

clean_lines = []
for line in lines:
    # Strip out the broken hardcoded lines I injected
    if '[GUI] Waiting 3 seconds' in line or 'time.sleep(3)' in line:
        continue
    clean_lines.append(line)

with open(bridge_path, 'w') as f:
    for line in clean_lines:
        f.write(line)
        # Dynamically inject the pause with the exact matching whitespace
        if 'logger.info("Started daemon via subprocess fallback.")' in line:
            indent = line[:len(line) - len(line.lstrip())]
            f.write(indent + 'print("[GUI] Waiting 3 seconds for daemon to bind to port 9410...")\n')
            f.write(indent + 'time.sleep(3)\n')

print("✅ Syntax error and indentation successfully patched!")
