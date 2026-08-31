import asyncio
from axiom.core.events import EventBus
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.llm.universal_client import UniversalLLMClient
from axiom.memory.semantic import SemanticIndex
import time

class MockLLMClient(UniversalLLMClient):
    async def chat(self, messages, **kwargs):
        return "I am a fast mock response doing mock tool stuff."
    def list_models(self): return ["qwen3"]
    def is_available(self): return True

async def main():
    bus = EventBus()
    client = MockLLMClient()
    agent = OrchestratorAgent(bus=bus, llm=client)
    idx = SemanticIndex()
    idx._vector_store = None
    
    start = time.time()
    for i in range(1, 501):  # Just 500
        agent.run(f"Hello turn {i}")
    end = time.time()
    
    print(f"500 turns took {end - start:.2f} seconds")
    print(f"Estimated 5000 turns: {(end - start) * 10:.2f} seconds")

asyncio.run(main())
