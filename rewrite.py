import re

with open("axiom/memory/memory_async.py", "r") as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 1. match: cursor = await db.execute(...)
    m = re.match(r'^(\s*)cursor = await db\.execute\((.*)\)\s*$', line)
    if m:
        indent = m.group(1)
        args = m.group(2)
        new_lines.append(f"{indent}async with db.execute({args}) as cursor:\n")
        # Now indent all following lines until the indentation is LESS than indent
        i += 1
        while i < len(lines):
            next_line = lines[i]
            if next_line.strip() == "":
                new_lines.append(next_line)
                i += 1
                continue
            next_indent = len(next_line) - len(next_line.lstrip())
            if next_indent < len(indent):
                # block ended
                break
            # Indent the line by 4 spaces
            new_lines.append(indent + "    " + next_line[len(indent):])
            i += 1
        continue
        
    # 2. match: await db.execute(...)
    m2 = re.match(r'^(\s*)await db\.execute\((.*)\)\s*$', line)
    if m2:
        indent = m2.group(1)
        args = m2.group(2)
        new_lines.append(f"{indent}async with db.execute({args}):\n")
        new_lines.append(f"{indent}    pass\n")
        i += 1
        continue

    new_lines.append(line)
    i += 1

with open("axiom/memory/memory_async.py", "w") as f:
    f.writelines(new_lines)
