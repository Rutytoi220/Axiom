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
    import numpy as np
    
    if len(a) != len(b) or not a:
        return 0.0
        
    vec_a = np.array(a, dtype=np.float32)
    vec_b = np.array(b, dtype=np.float32)
    
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


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
        """Find most similar entries by cosine similarity, applying time decay and confidence weight."""
        import time
        from datetime import datetime
        
        now = time.time()
        
        # Left join with memories to get confidence_weight, created_at, and tags_json
        # if the embedding is a memory. Otherwise these fields will be NULL.
        query = (
            "SELECT e.id, e.owner_id, e.owner_type, e.embedding_json, e.model, "
            "e.created_at as emb_created_at, m.created_at as mem_created_at, "
            "m.confidence_weight, m.tags_json "
            "FROM embeddings e "
            "LEFT JOIN memories m ON e.owner_id = m.key AND e.owner_type = 'memory'"
        )
        
        if owner_type:
            query += " WHERE e.owner_type = ?"
            params: tuple = (owner_type,)
        else:
            params = ()
            
        try:
            cursor = await db.execute(query, params)
        except Exception:
            # Fallback if memories table does not exist (e.g., standalone SemanticIndex usage)
            query = (
                "SELECT id, owner_id, owner_type, embedding_json, model, "
                "created_at as emb_created_at, NULL as mem_created_at, "
                "1.0 as confidence_weight, NULL as tags_json "
                "FROM embeddings"
            )
            if owner_type:
                query += " WHERE owner_type = ?"
            cursor = await db.execute(query, params)
            
        rows = await cursor.fetchall()
        if not rows:
            return []
            
        import numpy as np
        
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
            
        scored = []
        for row in rows:
            stored = json.loads(row["embedding_json"])
            s_vec = np.array(stored, dtype=np.float32)
            s_norm = np.linalg.norm(s_vec)
            base_sim = float(np.dot(q_vec, s_vec) / (q_norm * s_norm)) if s_norm > 0 else 0.0
            
            # Apply Temporal Decay and Confidence Weight
            decay_factor = 1.0
            confidence_weight = row["confidence_weight"] if row["confidence_weight"] is not None else 1.0
            
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            if "core_belief" not in tags:
                # Calculate age in days
                created_at_str = row["mem_created_at"] or row["emb_created_at"]
                if created_at_str:
                    try:
                        # SQLite CURRENT_TIMESTAMP is in format 'YYYY-MM-DD HH:MM:SS'
                        created_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                        age_seconds = now - created_dt.timestamp()
                        age_days = max(0.0, age_seconds / 86400.0)
                        
                        # Decay rate: ~1% per day (0.01)
                        decay_rate = 0.01
                        decay_factor = math.exp(-decay_rate * age_days)
                    except Exception:
                        pass
                        
            final_score = base_sim * decay_factor * confidence_weight
            
            scored.append(
                {
                    "id": row["id"],
                    "owner_id": row["owner_id"],
                    "owner_type": row["owner_type"],
                    "model": row["model"],
                    "similarity": final_score,
                    "base_similarity": base_sim,
                    "decay_factor": decay_factor,
                    "confidence_weight": confidence_weight,
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
