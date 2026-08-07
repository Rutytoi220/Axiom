import sys
from pathlib import Path

for file in ["axiom/tools/system_plugins.py", "axiom/tools/motor_plugins.py"]:
    with open(file, "r") as f:
        lines = f.readlines()
        
    new_lines = []
    for line in lines:
        if "@axiom_tool(" in line:
            new_lines.append(line)
        elif 'parameters={' in line:
            pass # Keep it, but wait, I can just append `requires_approval=True` before the closing parenthesis of the decorator.
        # Actually it's easier to find the end of the decorator.
        
    # Better approach: string replace.
    with open(file, "r") as f:
        content = f.read()
        
    # Find all instances of "@axiom_tool(" and the closing ")" before "def "
    # We can just replace '@axiom_tool(' with a regex, or replace ')' right before 'def ' with ', requires_approval=True)'
    import re
    content = re.sub(r'(\n@axiom_tool\([\s\S]*?)\n\)', r'\1,\n    requires_approval=True\n)', content)
    
    with open(file, "w") as f:
        f.write(content)

