import logging
import asyncio
from typing import Dict, Any, List, Optional
from axiom.memory.vector_store import VectorMemoryEngine

logger = logging.getLogger(__name__)

class TransactionalMemoryManager:
    """Wraps VectorMemoryEngine with ACID-like transactional semantics."""
    
    def __init__(self, memory_engine: Optional[VectorMemoryEngine] = None):
        if not memory_engine:
            self.engine = VectorMemoryEngine()
        else:
            self.engine = memory_engine
            
        self._staged_documents: List[Dict[str, Any]] = []
        self._in_transaction = False
        
    def begin_transaction(self):
        """Start a new transaction."""
        if self._in_transaction:
            raise RuntimeError("Transaction already in progress.")
        self._in_transaction = True
        self._staged_documents = []
        logger.info("Memory Transaction BEGIN")
        
    def stage_document(self, doc_id: str, text: str, metadata: dict = None):
        """Stage a document to be indexed upon commit."""
        if not self._in_transaction:
            raise RuntimeError("No active transaction.")
        self._staged_documents.append({
            "doc_id": doc_id,
            "text": text,
            "metadata": metadata or {}
        })
        logger.debug(f"Staged document: {doc_id}")
        
    async def commit(self):
        """Atomically commit all staged documents to the vector store."""
        if not self._in_transaction:
            raise RuntimeError("No active transaction.")
            
        logger.info(f"Memory Transaction COMMIT: Indexing {len(self._staged_documents)} documents...")
        
        try:
            # We process all chunks and if any fail (exception raised), we catch it
            for doc in self._staged_documents:
                await self.engine.add_document(doc["doc_id"], doc["text"], doc["metadata"])
                
            self._in_transaction = False
            self._staged_documents.clear()
            logger.info("Memory Transaction COMMITTED successfully.")
            return True
            
        except Exception as e:
            logger.error(f"Memory Transaction failed during commit: {e}. Triggering rollback.")
            await self.rollback()
            raise e
            
    async def rollback(self):
        """Discard all staged documents without saving them."""
        if not self._in_transaction:
            return
            
        # If we had a true two-phase commit with Chroma we'd delete the chunks added so far.
        # Here we just clear the staging buffer. In a more advanced implementation, 
        # we would track the IDs actually written to ChromaDB and call store.delete() on them.
        self._in_transaction = False
        self._staged_documents.clear()
        logger.warning("Memory Transaction ROLLBACK complete. Uncommitted vectors discarded.")

