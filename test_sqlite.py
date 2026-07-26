import asyncio
import aiosqlite
from axiom.memory.semantic import SemanticIndex

async def main():
    idx = SemanticIndex()
    idx._vector_store = None
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE embeddings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "owner_id TEXT, owner_type TEXT,"
            "embedding_json TEXT, model TEXT, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            f"INSERT INTO embeddings (owner_id, owner_type, embedding_json, model) VALUES ('m1', 'message', '{[1,0,0] + [0]*765}', '')"
        )
        await conn.commit()
        
        cursor = await conn.execute("SELECT * FROM embeddings")
        rows = await cursor.fetchall()
        print("Rows in DB:", len(rows))
        
        results = await idx.search(conn, [1.0, 0.0, 0.0] + [0.0] * 765, owner_type="message")
        print("Results:", len(results))

asyncio.run(main())
