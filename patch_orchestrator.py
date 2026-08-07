import sys

with open("axiom/agents/orchestrator_agent.py", "r") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if line.startswith("        self._agents[agent.name] = agent"):
        new_lines.append("        if agent.name not in self._agents:\n")
        new_lines.append("            self._agents[agent.name] = agent\n\n")
        new_lines.append("    def _emit_synapse_event(self, event_type: str, data: dict):\n")
        new_lines.append('        """Helper to emit synapse telemetry over the EventBus."""\n')
        new_lines.append("        bus = getattr(self, '_bus', None) or getattr(self, 'bus', None)\n")
        new_lines.append("        if bus:\n")
        new_lines.append("            from axiom.core.events import Event\n")
        new_lines.append("            try:\n")
        new_lines.append("                bus.publish(Event(event_type=f'synapse.{event_type}', source='OrchestratorAgent', data=data))\n")
        new_lines.append("            except Exception:\n")
        new_lines.append("                pass\n")
    elif line == "                if tool_calls and use_tools:\n" and "pending_calls" in lines[i+3]:
        new_lines.append(line)
        new_lines.append("                    self._emit_synapse_event('agent_thought', {'thought': str(content) if content else \"Evaluating tool call...\"})\n")
    elif line == "                        self._persist_step(session_id, 'reasoning', response_msg)\n" and "state = AgentState.EXIT" in lines[i+1] and "else:" in lines[i-1]:
        new_lines.append("                        self._emit_synapse_event('agent_thought', {'thought': final_response})\n")
        new_lines.append(line)
    elif line == "                        result = self._execute_tool(tool_name, arguments)\n" and "executed_signatures" in lines[i-1]:
        new_lines.append("                        self._emit_synapse_event('tool_call_started', {'tool': tool_name, 'args': arguments})\n")
        new_lines.append(line)
        new_lines.append("                        self._emit_synapse_event('tool_call_completed', {'tool': tool_name, 'success': result.get('success')})\n")
    else:
        new_lines.append(line)

with open("axiom/agents/orchestrator_agent.py", "w") as f:
    f.writelines(new_lines)

