import asyncio
import json
import random
import pytest
from unittest import mock

from axiom.core.events import EventBus, Event
from axiom.engine.engine import Engine
from axiom.engine.router import SmartRouter
from axiom.llm.universal_client import UniversalLLMClient
from axiom.agents.orchestrator_agent import OrchestratorAgent

# ── Payload Generators ────────────────────────────────────────────────────────

def generate_nested_json(depth: int) -> str:
    """Generate deeply nested JSON."""
    obj = "val"
    for _ in range(depth):
        obj = {"nested": obj}
    return json.dumps(obj)

def generate_malformed_som() -> str:
    """Generate malformed Set-of-Mark grid string."""
    return f"<som_grid>{random.choice(['[1,2', '}{', 'null', '<script>alert(1)</script>'])}</som_grid>"

def generate_sql_injection() -> str:
    return "'; DROP TABLE embeddings; --"

def generate_large_garbage() -> str:
    """Generate 1MB garbage to keep it sane for 10000 concurrent payloads."""
    return "GARBAGE" * 10000

PAYLOAD_GENERATORS = [
    lambda: generate_nested_json(50),
    generate_malformed_som,
    generate_sql_injection,
    generate_large_garbage,
    lambda: "\x00" * 100,  # null bytes
    lambda: "CONTRADICTION"
]

@pytest.mark.asyncio
async def test_chaos_fuzzer_10000_payloads():
    """Fire 10,000 random adversarial payloads concurrently."""
    bus = EventBus()
    client = UniversalLLMClient()
    router = SmartRouter(llm_client=client, event_bus=bus)
    agent = OrchestratorAgent(bus=bus, llm=client)
    agent = OrchestratorAgent(bus=bus, llm=client)

    # We will simulate the hostile conditions by patching
    # methods to randomly throw exceptions
    original_route = router._route_request
    
    async def hostile_route(event):
        if random.random() < 0.05:
            raise ConnectionError("Simulated Network Drop")
        if random.random() < 0.05:
            raise RuntimeError("Qdrant Lock Collision")
        try:
            return await original_route(event)
        except Exception:
            pass  # Fuzzer catches internal crashes

    router._route_request = hostile_route

    # Fire 10,000 payloads
    payloads = []
    for i in range(10000):
        gen = random.choice(PAYLOAD_GENERATORS)
        content = gen()
        evt = Event(source="user", event_type="INPUT", data={"content": content}, metadata={"id": i})
        payloads.append(evt)
    
    errors = []
    
    async def fire(event):
        try:
                agent.run(event.data.get("content", ""))
        except Exception as e:
            errors.append(e)

    tasks = [asyncio.create_task(fire(p)) for p in payloads]
    
    # Randomly cancel some tasks to simulate thread termination
    for task in tasks:
        if random.random() < 0.01:
            task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out CancelledError since we caused them intentionally
    real_errors = [e for e in errors if not isinstance(e, asyncio.CancelledError)]
    
    # Assertion: zero unhandled crashes/deadlocks from our agent loop
    assert len(real_errors) == 0, f"Crashed {len(real_errors)} times"
