import sys
import re

with open("axiom/agents/orchestrator_agent.py", "r") as f:
    content = f.read()

# Add the 11th rule to the base prompt
target_line = "10. [MOTOR CORTEX AUTOMATION] If the user asks you to interact with the desktop, click a button, read an error, or answer a question about their current screen, you MUST first use the 'capture_screen' tool to look at the screen. Only after you have observed the screen may you use motor tools like 'mouse_click' or 'keyboard_type'.\""

replacement = target_line[:-1] + "\\n11. [CONTEXTUAL SANDBOX] If the user asks for a visualization, interactive calculation, or physics simulation, you MUST use the 'generate_interactive_widget' tool to return a dynamic UI component instead of describing it in text.\""

content = content.replace(target_line, replacement)

with open("axiom/agents/orchestrator_agent.py", "w") as f:
    f.write(content)

