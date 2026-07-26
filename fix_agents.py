import re

def rep(fpath, old, new):
    with open(fpath, 'r') as f: c = f.read()
    c = c.replace(old, new)
    with open(fpath, 'w') as f: f.write(c)

rep('axiom/agents/shell_agent.py', 'self.steps = []', 'self.steps: list[Any] = []')
rep('axiom/agents/echo_agent.py', 'self.steps = []', 'self.steps: list[Any] = []')

rep('axiom/tools/__init__.py', 'return None', 'return ToolResult(success=True)') # maybe?
