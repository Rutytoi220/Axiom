import re

with open("axiom/memory/memory_async.py", "r") as f:
    content = f.read()

# Replace cursor = await db.execute(...) that spans multiple lines (none exist, but just in case)
# Replace await db.execute(...) that spans multiple lines
def replacer(m):
    indent = m.group(1)
    args = m.group(2)
    # We just replace the await db.execute with async with db.execute, then append : pass?
    # No, it's easier to just use db.execute inside async with db.execute(args): pass
    return f"{indent}async with db.execute({args}):\n{indent}    pass"

content = re.sub(r'^(\s*)await db\.execute\((.*?)\)', replacer, content, flags=re.MULTILINE | re.DOTALL)

with open("axiom/memory/memory_async.py", "w") as f:
    f.write(content)
