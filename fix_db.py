with open('axiom/memory/memory_async.py', 'r') as f:
    content = f.read()

bad_close = """    async def close(self) -> None:
        \"\"\"Auto-generated docstring.


Returns:
    Return value.
\"\"\"
        if self._db:
            await self._db.close()
            self._db = None
        self._initialized = False"""

good_close = """    async def close(self) -> None:
        \"\"\"Close database connection safely.\"\"\"
        if hasattr(self, '_db_mgr') and self._db_mgr:
            await self._db_mgr.close()
        elif self._db:
            await self._db.close()
        self._db = None
        self._initialized = False"""

content = content.replace(bad_close, good_close)

with open('axiom/memory/memory_async.py', 'w') as f:
    f.write(content)

with open('axiom/memory/db.py', 'r') as f:
    db_content = f.read()

db_content = db_content.replace(
    '        async with self._lock:\n            if self._shared_conn:\n                await self._shared_conn.close()\n                self._shared_conn = None',
    '        async with self._lock:\n            if self._shared_conn:\n                await self._shared_conn.close()\n                self._shared_conn = None\n            MemoryDatabaseManager._instance = None'
)

with open('axiom/memory/db.py', 'w') as f:
    f.write(db_content)
