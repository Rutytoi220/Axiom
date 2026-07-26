import re
import os

def process_file(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    out = []
    for line in lines:
        if ('def execute(self,' in line or 'def emptyline(self' in line) and 'ignore' not in line:
            line = line.rstrip() + '  # type: ignore[override]\n'
        out.append(line)
        
    with open(filepath, 'w') as f:
        f.writelines(out)

for root, _, files in os.walk('axiom'):
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))
