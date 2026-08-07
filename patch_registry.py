import sys

with open("axiom/tool_registry.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line == "        val_error = self._pre_validate_path(tool.tool_id, arguments)\n" and "if val_error:" in lines[i+1]:
        # We need to distinguish between execute and execute_async based on context
        # Let's check context
        if "async def execute_async" in "".join(lines[max(0, i-20):i]):
            new_lines.append("        if getattr(tool, 'requires_approval', False):\n")
            new_lines.append("            try:\n")
            new_lines.append("                from axiom.services.governor import GovernorService\n")
            new_lines.append("                governor = GovernorService.instance()\n")
            new_lines.append("                if governor and governor.is_strict_mode():\n")
            new_lines.append("                    approved = await governor.request_approval(tool.name, arguments)\n")
            new_lines.append("                    if not approved:\n")
            new_lines.append("                        return ToolResult(success=False, error=\"User denied execution via The Governor.\")\n")
            new_lines.append("            except Exception as e:\n")
            new_lines.append("                return ToolResult(success=False, error=f\"Governor failed: {e}\")\n")
            new_lines.append(line)
        else:
            new_lines.append("        if getattr(tool, 'requires_approval', False):\n")
            new_lines.append("            try:\n")
            new_lines.append("                from axiom.services.governor import GovernorService\n")
            new_lines.append("                governor = GovernorService.instance()\n")
            new_lines.append("                if governor and governor.is_strict_mode():\n")
            new_lines.append("                    return ToolResult(success=False, error=\"This tool requires approval, but was invoked synchronously. Governor gates are only supported in async mode.\")\n")
            new_lines.append("            except Exception:\n")
            new_lines.append("                pass\n")
            new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/tool_registry.py", "w") as f:
    f.writelines(new_lines)

