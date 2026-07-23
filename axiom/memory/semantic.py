"""Semantic search index for AXIOM memory.

Stores embedding vectors and performs cosine similarity search.
Uses local vector database (Qdrant) if available, falling back
to in-memory NumPy + SQLite.
"""

import json
import math
import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

class EmbeddingProvider(Protocol):
    """Protocol for embedding generation. OllamaClient satisfies this."""

    def embed(self, text: str, model: Optional[str] = None) -> List[float]: ...


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors (legacy fallback)."""
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
    """Embedding storage and similarity search.
    
    Automatically prefers QdrantLocalStore if `qdrant-client` is installed,
    otherwise falls back to SQLite + NumPy array computations.
    """

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider
        
        # Try to initialize the vector store adapter
        self._vector_store = None
        try:
            from axiom.memory.vector_store import QdrantLocalStore
            import sys
            if "pytest" in sys.modules:
                self._vector_store = QdrantLocalStore(location=":memory:")
            else:
                self._vector_store = QdrantLocalStore()
        except ImportError:
            logger.warning("qdrant-client not installed. SemanticIndex falling back to NumPy+SQLite.")
        except Exception as e:
            if "lock" in str(e).lower() or "accessed by another instance" in str(e).lower():
                import os
                from pathlib import Path
                lock_file = Path.home() / ".axiom" / "vector_db" / ".lock"
                if lock_file.exists():
                    try:
                        os.remove(lock_file)
                        logger.info("Cleared dangling Qdrant lock file.")
                        self._vector_store = QdrantLocalStore()
                        return
                    except Exception as lock_err:
                        logger.warning("Could not clear Qdrant lock file: %s", lock_err)
            logger.warning("Failed to initialize QdrantLocalStore: %s. Falling back to NumPy+SQLite.", e)

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
        
        # Always store in SQLite as a permanent backup / source of truth
        await db.execute(
            "INSERT INTO embeddings "
            "(owner_id, owner_type, embedding_json, model) VALUES (?, ?, ?, ?)",
            (owner_id, owner_type, json.dumps(embedding), model),
        )
        await db.commit()
        
        # Async push to Vector Store if available
        if self._vector_store:
            try:
                # We await the thread so that we don't have race conditions between write and read.
                await asyncio.to_thread(
                    self._vector_store.upsert,
                    owner_id,
                    owner_type,
                    embedding,
                    {"model": model}
                )
            except Exception as e:
                logger.error("Failed to asynchronously upsert to Qdrant: %s", e)

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
            
        try:
            # Embedding might be a slow network call, run in thread
            embedding = await asyncio.to_thread(self._provider.embed, text, model)
        except Exception as e:
            logger.error("Failed to generate embedding: %s", e)
            return False
            
        if not embedding:
            return False
            
        await self.store(db, owner_id, owner_type, embedding, model=model or "")
        return True

    def _apply_decay(self, base_sim: float, row: dict, now: float) -> dict:
        """Apply temporal decay and confidence weight to a score."""
        import math
        from datetime import datetime
        
        decay_factor = 1.0
        confidence_weight = row["confidence_weight"] if row["confidence_weight"] is not None else 1.0
        
        tags = json.loads(row["tags_json"]) if row["tags_json"] else []
        if "core_belief" not in tags:
            # Calculate age in days
            created_at_str = row["mem_created_at"] or row["emb_created_at"]
            if created_at_str:
                try:
                    created_dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                    age_seconds = now - created_dt.timestamp()
                    age_days = max(0.0, age_seconds / 86400.0)
                    
                    decay_rate = 0.01
                    decay_factor = math.exp(-decay_rate * age_days)
                except Exception:
                    pass
                    
        final_score = base_sim * decay_factor * confidence_weight
        return {
            "similarity": final_score,
            "base_similarity": base_sim,
            "decay_factor": decay_factor,
            "confidence_weight": confidence_weight,
        }

    async def search(
        self,
        db: Any,
        query_embedding: List[float],
        owner_type: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find most similar entries."""
        import time
        now = time.time()
        
        # --- FAST PATH: Qdrant Local Vector DB ---
        if self._vector_store:
            try:
                # Query vector database in a separate thread
                qdrant_results = await asyncio.to_thread(
                    self._vector_store.search,
                    query_embedding,
                    owner_type,
                    top_k * 2  # Oversample slightly to account for decay re-ranking
                )
                
                if not qdrant_results:
                    return []
                    
                # We need to join with SQLite to get `created_at` and `confidence_weight`
                owner_ids = [hit["owner_id"] for hit in qdrant_results]
                placeholders = ",".join(["?"] * len(owner_ids))
                
                query = (
                    f"SELECT e.id, e.owner_id, e.owner_type, e.model, "
                    f"e.created_at as emb_created_at, m.created_at as mem_created_at, "
                    f"m.confidence_weight, m.tags_json "
                    f"FROM embeddings e "
                    f"LEFT JOIN memories m ON e.owner_id = m.key AND e.owner_type = 'memory' "
                    f"WHERE e.owner_id IN ({placeholders})"
                )
                
                try:
                    cursor = await db.execute(query, tuple(owner_ids))
                except Exception:
                    # Fallback if memories table missing
                    query = (
                        f"SELECT id, owner_id, owner_type, model, "
                        f"created_at as emb_created_at, NULL as mem_created_at, "
                        f"1.0 as confidence_weight, NULL as tags_json "
                        f"FROM embeddings WHERE owner_id IN ({placeholders})"
                    )
                    cursor = await db.execute(query, tuple(owner_ids))
                    
                db_rows = await cursor.fetchall()
                db_lookup = {row["owner_id"]: row for row in db_rows}
                
                scored = []
                for hit in qdrant_results:
                    owner_id = hit["owner_id"]
                    if owner_id not in db_lookup:
                        continue
                    
                    row = db_lookup[owner_id]
                    base_sim = hit["score"]
                    
                    metrics = self._apply_decay(base_sim, row, now)
                    
                    scored.append({
                        "id": row["id"],
                        "owner_id": row["owner_id"],
                        "owner_type": row["owner_type"],
                        "model": row["model"],
                        **metrics
                    })
                    
                scored.sort(key=lambda x: x["similarity"], reverse=True)
                return scored[:top_k]
                
            except Exception as e:
                logger.error("Qdrant search failed, falling back to SQLite: %s", e)
                # Fall through to SQLite/NumPy approach


        # --- SLOW PATH: SQLite + NumPy ---
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
            
            metrics = self._apply_decay(base_sim, row, now)
            
            scored.append({
                "id": row["id"],
                "owner_id": row["owner_id"],
                "owner_type": row["owner_type"],
                "model": row["model"],
                **metrics
            })
            
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    async def search_text(
        self,
        db: Any,
        text: str,
        owner_type: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search by text using the embedding provider."""
        if not self._provider:
            return []
            
        try:
            embedding = await asyncio.to_thread(self._provider.embed, text)
        except Exception as e:
            logger.error("Failed to generate embedding for search: %s", e)
            return []
            
        if not embedding:
            return []
        return await self.search(db, embedding, owner_type=owner_type, top_k=top_k)
