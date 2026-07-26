"""Vector Database Storage Adapters for Semantic Memory.

Provides a unified interface for connecting to dedicated local vector
databases like Qdrant or Chroma, replacing the legacy NumPy+SQLite approach.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path
logger = logging.getLogger(__name__)

class BaseVectorStore(Protocol):
    """Protocol defining the required interface for a vector storage backend."""

    def upsert(self, owner_id: str, owner_type: str, embedding: List[float], payload: Optional[Dict[str, Any]]=None) -> None:
        """Insert or update a vector embedding with associated metadata payload."""
        ...

    def search(self, query_embedding: List[float], owner_type: Optional[str]=None, top_k: int=5) -> List[Dict[str, Any]]:
        """Search for similar vectors.
        
        Returns a list of dicts containing:
        - id: The original owner_id
        - owner_type: The type of the owner
        - score: The similarity score (cosine distance)
        - payload: Any stored metadata
        """
        ...

    def delete(self, owner_id: str) -> None:
        """Delete a vector by its owner_id."""
        ...

    def count(self) -> int:
        """Return the total number of vectors in the store."""
        ...

class QdrantLocalStore:
    """Local, embedded Qdrant vector database store.
    
    Persists data to ~/.axiom/vector_db/ or runs entirely in-memory if
    location=":memory:" is provided.
    """
    COLLECTION_NAME = 'axiom_semantic_memory'

    def __init__(self, location: Optional[str]=None):
        """Auto-generated docstring.

Args:
    location: Argument.

Returns:
    Return value.
"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError:
            raise ImportError('qdrant-client is not installed. Run `pip install qdrant-client`.')
        self.Distance = Distance
        self.VectorParams = VectorParams
        if location == ':memory:':
            self.client = QdrantClient(location=':memory:')
            logger.info('QdrantLocalStore initialized in memory.')
        else:
            if location is None:
                db_dir = Path.home() / '.axiom' / 'vector_db'
            else:
                db_dir = Path(location)
            db_dir.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(db_dir))
            logger.info(f'QdrantLocalStore initialized at {db_dir}')
        self._collection_initialized = False
        try:
            collections = self.client.get_collections().collections
            if any((c.name == self.COLLECTION_NAME for c in collections)):
                self._collection_initialized = True
        except Exception as e:
            logger.warning(f'Failed to check Qdrant collections: {e}')

    def _ensure_collection(self, dimension: int):
        """Ensure the collection exists with the correct vector dimension."""
        if self._collection_initialized:
            return
        from qdrant_client.models import Distance, VectorParams
        try:
            self.client.create_collection(collection_name=self.COLLECTION_NAME, vectors_config=VectorParams(size=dimension, distance=Distance.COSINE))
            self._collection_initialized = True
            logger.info(f"Created Qdrant collection '{self.COLLECTION_NAME}' with dim={dimension}.")
        except Exception as e:
            if 'already exists' in str(e).lower():
                self._collection_initialized = True
            else:
                logger.error(f'Failed to create Qdrant collection: {e}')

    def _generate_uuid_from_string(self, s: str) -> str:
        """Qdrant requires UUIDs or integers for point IDs."""
        import hashlib
        m = hashlib.md5()
        m.update(s.encode('utf-8'))
        return str(uuid.UUID(m.hexdigest()))

    def upsert(self, owner_id: str, owner_type: str, embedding: List[float], payload: Optional[Dict[str, Any]]=None) -> None:
        """Insert or update a vector."""
        if not embedding:
            return
        self._ensure_collection(dimension=len(embedding))
        from qdrant_client.models import PointStruct
        point_id = self._generate_uuid_from_string(f'{owner_type}:{owner_id}')
        full_payload = payload or {}
        full_payload['owner_id'] = owner_id
        full_payload['owner_type'] = owner_type
        try:
            self.client.upsert(collection_name=self.COLLECTION_NAME, points=[PointStruct(id=point_id, vector=embedding, payload=full_payload)])
        except Exception as e:
            logger.error(f'Failed to upsert to Qdrant: {e}')

    def search(self, query_embedding: List[float], owner_type: Optional[str]=None, top_k: int=5) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        if not query_embedding:
            return []
        if not self._collection_initialized:
            return []
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        query_filter = None
        if owner_type:
            query_filter = Filter(must=[FieldCondition(key='owner_type', match=MatchValue(value=owner_type))])
        try:
            results = self.client.query_points(collection_name=self.COLLECTION_NAME, query=query_embedding, query_filter=query_filter, limit=top_k, with_payload=True).points
            formatted_results = []
            for hit in results:
                payload = hit.payload or {}
                formatted_results.append({'id': payload.get('owner_id', str(hit.id)), 'owner_id': payload.get('owner_id', str(hit.id)), 'owner_type': payload.get('owner_type', ''), 'score': hit.score, 'payload': payload})
            return formatted_results
        except Exception as e:
            logger.error(f'Failed to query Qdrant points: {e}')
            return []

    def delete(self, owner_id: str) -> None:
        """Delete a vector. Requires iterating or using a filter."""
        if not self._collection_initialized:
            return
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        try:
            self.client.delete(collection_name=self.COLLECTION_NAME, points_selector=Filter(must=[FieldCondition(key='owner_id', match=MatchValue(value=owner_id))]))
        except Exception as e:
            logger.error(f'Failed to delete from Qdrant: {e}')

    def count(self) -> int:
        """Return the number of vectors in the collection."""
        if not self._collection_initialized:
            return 0
        try:
            response = self.client.count(collection_name=self.COLLECTION_NAME)
            return response.count
        except Exception as e:
            logger.error(f'Failed to count Qdrant collection: {e}')
            return 0
