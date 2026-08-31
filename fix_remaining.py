with open("axiom/memory/memory_async.py", "r") as f:
    content = f.read()

content = content.replace(
    "await db.execute('INSERT OR REPLACE INTO memories\\n            (key, value_json, tags_json, created_at, updated_at, ttl_seconds)\\n            VALUES (?, ?, ?, ?, ?, ?)', (key, value_json, tags_json, created_at, now, ttl))",
    "async with db.execute('INSERT OR REPLACE INTO memories\\n            (key, value_json, tags_json, created_at, updated_at, ttl_seconds)\\n            VALUES (?, ?, ?, ?, ?, ?)', (key, value_json, tags_json, created_at, now, ttl)): pass"
)

content = content.replace(
    "await db.execute('UPDATE memories SET retrieval_count = retrieval_count + 1 WHERE key = ?', (key,))",
    "async with db.execute('UPDATE memories SET retrieval_count = retrieval_count + 1 WHERE key = ?', (key,)): pass"
)

with open("axiom/memory/memory_async.py", "w") as f:
    f.write(content)
