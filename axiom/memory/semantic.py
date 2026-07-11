"""Semantic search index for AXIOM memory.

Stores embedding vectors and performs cosine similarity search.
Composable with MemoryStore or usable independently.
"""

import json
import math
from typing import Any, Dict, List, Optional, Protocol


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation. OllamaClient satisfies this."""

    def embed(self, text: str, model: Optional[str] = None) -> List[float]: ...


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticIndex:
    """Embedding storage and similarity search over aiosqlite connection."""

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider

    @property
    def has_provider(self) -> bool:
        return self._provider is not None

    async def store(
        self,
        db: Any,
        owner_id: str,
        owner_type: str,
        embedding: List[float],
        model: str = "",
    ) -> None:
        """Persist an embedding vector."""
        await db.execute(
            "INSERT INTO embeddings "
            "(owner_id, owner_type, embedding_json, model) VALUES (?, ?, ?, ?)",
            (owner_id, owner_type, json.dumps(embedding), model),
        )
        await db.commit()

    async def store_text(
        self,
        db: Any,
        owner_id: str,
        owner_type: str,
        text: str,
        model: Optional[str] = None,
    ) -> bool:
        """Generate embedding from text via provider, then store. Returns False if no provider."""
        if not self._provider:
            return False
        embedding = self._provider.embed(text, model=model)
        if not embedding:
            return False
        await self.store(db, owner_id, owner_type, embedding, model=model or "")
        return True

    async def search(
        self,
        db: Any,
        query_embedding: List[float],
        owner_type: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find most similar entries by cosine similarity."""
        if owner_type:
            query = (
                "SELECT id, owner_id, owner_type, embedding_json, model "
                "FROM embeddings WHERE owner_type = ?"
            )
            params: tuple = (owner_type,)
        else:
            query = "SELECT id, owner_id, owner_type, embedding_json, model " "FROM embeddings"
            params = ()
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        scored = []
        for row in rows:
            stored = json.loads(row["embedding_json"])
            sim = _cosine_similarity(query_embedding, stored)
            scored.append(
                {
                    "id": row["id"],
                    "owner_id": row["owner_id"],
                    "owner_type": row["owner_type"],
                    "model": row["model"],
                    "similarity": sim,
                }
            )
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    async def search_text(
        self,
        db: Any,
        text: str,
        owner_type: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search by text using the embedding provider. Falls back to empty list."""
        if not self._provider:
            return []
        embedding = self._provider.embed(text)
        if not embedding:
            return []
        return await self.search(db, embedding, owner_type=owner_type, top_k=top_k)
