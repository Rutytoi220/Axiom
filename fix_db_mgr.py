import re

def fix_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Remove self._db_mgr = await ... from __init__
    content = re.sub(r'        self\._db_mgr = await MemoryDatabaseManager\.get_instance\(self\.db_path\)\n', '', content)

    # Add it to _conn()
    conn_func = """    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db_mgr = await MemoryDatabaseManager.get_instance(self.db_path)
            self._db = await self._db_mgr.get_connection()
        return self._db"""
        
    content = re.sub(r'    async def _conn\(self\) -> aiosqlite\.Connection:\n        if self\._db is None:\n            self\._db = await self\._db_mgr\.get_connection\(\)\n        return self\._db', conn_func, content)

    with open(file_path, 'w') as f:
        f.write(content)

fix_file('axiom/memory/sessions.py')
fix_file('axiom/memory/schedules.py')
