import asyncio
import os
import psutil
import tracemalloc
import pytest
import gc

from axiom.core.events import EventBus, Event
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.llm.universal_client import UniversalLLMClient
from axiom.memory.sleep_cycle import SleepCycleDaemon
from axiom.perception.watcher import OSWatcher
from axiom.perception.audio_queue import AudioDaemon
from axiom.memory.semantic import SemanticIndex

class MockLLMClient(UniversalLLMClient):
    async def chat(self, messages, **kwargs):
        # Deterministic local stub to bypass LLM latency
        return "I am a fast mock response doing mock tool stuff."

@pytest.mark.asyncio
async def test_memory_leaks_5000_turns():
    tracemalloc.start()
    
    bus = EventBus()
    client = MockLLMClient()
    agent = OrchestratorAgent(bus=bus, llm=client)
    idx = SemanticIndex()
    idx._vector_store = None  # Force memory sqlite
    
    # Initialize long-running daemons
    sleep_daemon = SleepCycleDaemon(bus, memory_store=idx)
    watcher = OSWatcher(bus)
    audio = AudioDaemon()
    
    # Start daemons (mock start to prevent real thread blocking if needed)
    # We will just instantiate them to see if they hold memory
    
    process = psutil.Process(os.getpid())
    
    initial_mem = process.memory_info().rss
    initial_fds = process.num_fds() if hasattr(process, 'num_fds') else 0
    
    mem_at_500 = None
    fd_at_500 = None
    
    TURNS = 5000
    
    for i in range(1, TURNS + 1):
        agent.run(f"Hello turn {i}")
        await idx.store_text(None, f"t{i}", "memory", f"Turn {i}")
        
        if i % 100 == 0:
            gc.collect()
            current_mem = process.memory_info().rss
            current_fds = process.num_fds() if hasattr(process, 'num_fds') else 0
            
            if i == 500:
                mem_at_500 = current_mem
                fd_at_500 = current_fds
            elif i > 500:
                mem_growth = (current_mem - mem_at_500) / mem_at_500
                assert mem_growth < 0.15, f"Memory leak detected: growth is {mem_growth*100:.1f}% at turn {i}"
                assert current_fds <= fd_at_500 + 5, f"File descriptor leak detected at turn {i}"
                
    tracemalloc.stop()
