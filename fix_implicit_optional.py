import os
import re
import glob

def fix_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Pattern: parameter: type = None  -> parameter: type | None = None
    # e.g., desc: str = None -> desc: str | None = None
    
    # regex for type annotation not containing Optional or | None
    def replacer(match):
        param_name = match.group(1)
        type_ann = match.group(2)
        if "Optional" in type_ann or "|" in type_ann or "Any" in type_ann:
            return match.group(0)
        return f"{param_name}: {type_ann} | None = None"

    new_content = re.sub(r'([a-zA-Z0-9_]+)\s*:\s*([a-zA-Z0-9_\[\]]+)\s*=\s*None', replacer, content)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Fixed {filepath}")

for root, _, files in os.walk('axiom'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

for root, _, files in os.walk('brain'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

for root, _, files in os.walk('utils'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
