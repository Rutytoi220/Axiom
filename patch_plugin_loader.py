import sys

with open("axiom/tools/plugin_loader.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "                        parameters=obj.__tool_parameters__\n":
        new_lines.append("                        parameters=obj.__tool_parameters__,\n")
        new_lines.append("                        requires_approval=getattr(obj, '__tool_requires_approval__', False)\n")
    else:
        new_lines.append(line)

with open("axiom/tools/plugin_loader.py", "w") as f:
    f.writelines(new_lines)

