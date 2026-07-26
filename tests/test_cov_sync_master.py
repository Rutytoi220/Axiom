import pytest
from unittest.mock import patch, MagicMock

def test_sync_master():
    from axiom.memory.memory_sync import SyncMemoryStore
    
    class ErrProv:
        def embed(self, *args): raise Exception("err")
        
    store = SyncMemoryStore(":memory:", embedding_provider=ErrProv())
    store.create_conversation("title")
    store.add_message("user", "hello")
    
    class StoreErrProv:
        def embed(self, *args): return [0.1]
    
    store2 = SyncMemoryStore(":memory:", embedding_provider=StoreErrProv())
    store2.create_conversation("title")
    with patch.object(store2._store, "store_embedding", side_effect=Exception("store err")):
        store2.add_message("user", "hello")
        
    store2.close()
    store.close()
