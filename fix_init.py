with open("axiom/memory/memory_async.py", "r") as f:
    content = f.read()

content = content.replace(
    "await self._db.execute('PRAGMA user_version = 2')",
    "async with self._db.execute('PRAGMA user_version = 2'): pass"
)
content = content.replace(
    "await self._db.execute('ALTER TABLE memories ADD COLUMN retrieval_count INTEGER DEFAULT 0')",
    "async with self._db.execute('ALTER TABLE memories ADD COLUMN retrieval_count INTEGER DEFAULT 0'): pass"
)
content = content.replace(
    "await self._db.execute('ALTER TABLE memories ADD COLUMN confidence_weight REAL DEFAULT 1.0')",
    "async with self._db.execute('ALTER TABLE memories ADD COLUMN confidence_weight REAL DEFAULT 1.0'): pass"
)

with open("axiom/memory/memory_async.py", "w") as f:
    f.write(content)
