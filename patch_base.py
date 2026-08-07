import sys

with open("axiom/tools/base.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "    plugin_parameters: Dict[str, Any] = {}\n":
        new_lines.append(line)
        new_lines.append("    requires_approval: bool = False\n")
    elif line.startswith("def axiom_tool(name: str, description: str, parameters: dict"):
        new_lines.append("def axiom_tool(name: str, description: str, parameters: dict, requires_approval: bool = False):\n")
    elif line == "        func.__tool_parameters__ = parameters\n":
        new_lines.append(line)
        new_lines.append("        func.__tool_requires_approval__ = requires_approval\n")
    elif line.startswith("    def __init__(self, func, name: str, description: str, parameters: dict"):
        new_lines.append("    def __init__(self, func, name: str, description: str, parameters: dict, requires_approval: bool = False):\n")
    elif line == "        self._tool_parameters = parameters\n":
        new_lines.append(line)
        new_lines.append("        self.requires_approval = requires_approval\n")
    else:
        new_lines.append(line)

with open("axiom/tools/base.py", "w") as f:
    f.writelines(new_lines)

