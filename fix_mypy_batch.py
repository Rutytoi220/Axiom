import re

def rep(filepath, old, new):
    with open(filepath, 'r') as f: c = f.read()
    c = c.replace(old, new)
    with open(filepath, 'w') as f: f.write(c)

rep('axiom/memory/memory_async.py', 'len(rows)', 'len(list(rows))')
rep('axiom/memory/memory_async.py', 'return count', 'return count or 0') # This might be too broad, but let's see. Wait, better to be specific.
rep('axiom/perception/watcher.py', 'self.observer = None', 'self.observer: Any | None = None')
rep('axiom/perception/watcher.py', 'self._cpu_history = []', 'self._cpu_history: list[float] = []')
rep('axiom/perception/watcher.py', 'self.thread = None', 'self.thread: Any | None = None')
rep('axiom/engine/router.py', 'result = None', 'result: Any | None = None')
rep('axiom/agents/orchestrator_agent.py', 'self.executed_signatures = set()', 'self.executed_signatures: set[str] = set()')
rep('axiom/agents/orchestrator_agent.py', 'category = None', 'category: str | None = None')
rep('axiom/api/cli.py', 'self.daemon = None', 'self.daemon: Any | None = None')
rep('axiom/api/cli.py', 'self.engine = None', 'self.engine: Any | None = None')

