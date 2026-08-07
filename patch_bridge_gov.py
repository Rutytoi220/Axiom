import sys

with open("axiom/gui/bridge.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("    axiomfs_status: Signal = Signal(str)"):
        new_lines.append(line)
        new_lines.append("    governor_approval_requested: Signal = Signal(str, dict)\n")
    elif line == '        elif event_type == "axiomfs.status":\n':
        new_lines.append('        elif event_type == "governor.approval_requested":\n')
        new_lines.append('            self.governor_approval_requested.emit(payload.get("tool_name", ""), payload.get("arguments", {}))\n')
        new_lines.append(line)
    elif line == "    # Internal async task runner\n":
        new_lines.append("    def send_approval_response(self, tool_name: str, approved: bool) -> None:\n")
        new_lines.append("        if self._loop is None or not self._client.is_connected:\n")
        new_lines.append("            return\n")
        new_lines.append("        event = {\"type\": \"publish\", \"event\": {\"event_type\": \"governor.approval_response\", \"source\": \"gui\", \"data\": {\"tool_name\": tool_name, \"approved\": approved}}}\n")
        new_lines.append("        import json, asyncio\n")
        new_lines.append("        asyncio.run_coroutine_threadsafe(self._client.websocket.send(json.dumps(event)), self._loop)\n\n")
        new_lines.append("    def set_strict_mode(self, enabled: bool) -> None:\n")
        new_lines.append("        if self._loop is None or not self._client.is_connected:\n")
        new_lines.append("            return\n")
        new_lines.append("        event = {\"type\": \"publish\", \"event\": {\"event_type\": \"governor.set_strict_mode\", \"source\": \"gui\", \"data\": {\"enabled\": enabled}}}\n")
        new_lines.append("        import json, asyncio\n")
        new_lines.append("        asyncio.run_coroutine_threadsafe(self._client.websocket.send(json.dumps(event)), self._loop)\n\n")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("axiom/gui/bridge.py", "w") as f:
    f.writelines(new_lines)

