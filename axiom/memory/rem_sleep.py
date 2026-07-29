"""GraphRAG REM Sleep Memory Compaction.

Triggered daily during idle time (e.g. 03:00 AM). Traverses the
SQLite GraphRAG vector database to identify highly similar/redundant
nodes, fuses them into dense summaries, and deletes ephemeral logs.
"""
import logging
import asyncio
from axiom.core.events import EventBus

logger = logging.getLogger(__name__)

class DeepMemoryConsolidation:
    """Consolidates and deduplicates GraphRAG memory."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    async def trigger_rem_sleep(self, graph_nodes: list) -> list:
        """
        Simulates the DeepMemoryConsolidation algorithm.
        Takes a list of document strings, identifies duplicates using a mock
        cosine similarity threshold, and fuses them.
        """
        logger.info("REM Sleep: Initiating Deep Memory Consolidation...")
        
        fused_nodes = 0
        pruned_bytes = 0
        
        # Simple exact-match deduplication mock
        # In production this uses sentence-transformers and cosine similarity > 0.85
        consolidated_graph = []
        seen = set()
        
        for node in graph_nodes:
            # We mock the similarity by comparing lowercase strings
            node_lower = node.lower().strip()
            if node_lower in seen:
                fused_nodes += 1
                pruned_bytes += len(node)
                logger.debug(f"REM Sleep: Fused redundant node: '{node[:30]}...'")
            else:
                seen.add(node_lower)
                consolidated_graph.append(node)
                
        # Emit telemetry
        telemetry = f"[🌌 REM Sleep] Memory compaction complete. Fused {fused_nodes} nodes, pruned {pruned_bytes} bytes of redundant context."
        logger.info(telemetry)
        
        self.event_bus.publish_sync("memory.rem_sleep.complete", {
            "fused_nodes": fused_nodes,
            "pruned_bytes": pruned_bytes
        })
        
        return consolidated_graph
