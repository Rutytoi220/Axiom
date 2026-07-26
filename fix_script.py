import os
import re

def rep(filepath, old, new):
    with open(filepath, 'r') as f:
        c = f.read()
    c = c.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(c)

rep('axiom/tools/mcp_sse_client.py', 'self.data_buffer = []', 'self.data_buffer: list[str] = []')
rep('axiom/tools/mcp_sse_client.py', 'if self.on_disconnect:', 'if self.on_disconnect is not None:')

rep('axiom/tools/mcp_hub.py', 'future = asyncio.Future()', 'future: asyncio.Future[Any] = asyncio.Future()')

# IO[Any] | None write flush readline errors
# We can just change the type from IO[Any] | None to IO[Any] or use if is not None
import re
with open('axiom/tools/mcp_hub.py', 'r') as f: c = f.read()
c = c.replace('self.process.stdin.write', 'if self.process.stdin: self.process.stdin.write')
c = c.replace('self.process.stdin.flush', 'if self.process.stdin: self.process.stdin.flush')
c = c.replace('self.process.stdout.readline', 'if self.process.stdout: self.process.stdout.readline')
with open('axiom/tools/mcp_hub.py', 'w') as f: f.write(c)

