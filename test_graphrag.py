import asyncio
from axiom.engine.memory_tx import TransactionalMemoryManager

async def test_graph():
    # Mock engine
    class MockVector:
        async def add_document(self, id, text, meta):
            pass
            
    tx = TransactionalMemoryManager(MockVector())
    tx.begin_transaction()
    tx.stage_document("doc1", "nginx.service failed due to port 80 conflict on network.target")
    await tx.commit()
    
    res = await tx.graph.query_graph_context("nginx.service")
    print("Graph Query Result:", res)

asyncio.run(test_graph())
