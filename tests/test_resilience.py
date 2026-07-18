import time
import asyncio
from pathlib import Path
from axiom.agents.orchestrator_agent import OrchestratorAgent, Plan
from axiom.core.engine import Engine
from axiom.memory import SyncMemoryStore
from axiom.core.events import EventBus

class MockLoopingLLM:
    """An LLM that constantly calls the same tool, ignoring instructions unless an override appears."""
    def __init__(self):
        self.call_count = 0
        
    def chat_with_tools(self, messages, tools, **kwargs):
        self.call_count += 1
        
        print(f"\n--- MockLoopingLLM called (Round {self.call_count}) ---")
        for m in messages:
            print(f"Role: {m.get('role')} | Content: {m.get('content')[:100]}")
        
        # Check for system override
        for msg in messages:
            if msg.get("role") == "system" and "You are repeating yourself" in msg.get("content", ""):
                return {"role": "assistant", "content": "I apologize, I am stuck in a loop. Aborting."}
                
        # Check if it's a reflection prompt
        for msg in messages:
            if msg.get("role") == "system" and "reflection agent" in msg.get("content", ""):
                return {"role": "assistant", "content": '{"complete": false, "answer": "Keep going"}'}
                
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "name": "shell",
                    "arguments": {"command": "echo loop"}
                }
            ]
        }
        
    def chat(self, messages, **kwargs):
        return self.chat_with_tools(messages, [], **kwargs).get("content", "")

def test_recursive_tool_loop(tmp_path):
    """Verify that a recursive tool loop is detected and overridden after 3 iterations."""
    db_path = str(tmp_path / "test.db")
    memory = SyncMemoryStore(db_path)
    engine = Engine(memory=memory)
    engine.initialize()
    
    import axiom.agents.orchestrator_agent
    axiom.agents.orchestrator_agent.MAX_TOOL_ROUNDS = 20
    
    agent = OrchestratorAgent(registry=engine.registry, bus=engine.event_bus, memory=memory)
    llm = MockLoopingLLM()
    agent.set_llm(llm)
    
    # We must register a dummy shell tool so it doesn't fail on "Tool not found"
    class DummyShell:
        name = "shell"
        schema = {"type": "object", "properties": {"command": {"type": "string"}}}
        def execute(self, args):
            return {"output": "loop", "success": True}
    engine.registry.register_tool("shell", DummyShell())
    
    start = time.time()
    result = agent.run("Do a task forever")
    end = time.time()
    
    engine.shutdown()
    
    # The loop should have been broken by the override prompt.
    assert "Aborting" in result.output.get("response", "")
    assert llm.call_count <= 5  # It should abort at round 3 or 4, well before MAX_TOOL_ROUNDS=10
    assert (end - start) < 5.0  # Should abort deterministically within 5 seconds


class MockThrashingLLM:
    """An LLM that returns a huge observation request to thrash context."""
    def __init__(self):
        self.call_count = 0
        
    def chat_with_tools(self, messages, tools, **kwargs):
        self.call_count += 1
        
        print(f"\n--- MockThrashingLLM called (Round {self.call_count}) ---")
        for m in messages:
            print(f"Role: {m.get('role')} | Content: {m.get('content')[:100]}")
        
        # Check if adaptive compression ran (we see the truncation string)
        for msg in messages:
            if msg.get("role") == "system" and "Output truncated due to context limits" in msg.get("content", ""):
                return {"role": "assistant", "content": "Context was successfully compressed!"}
                
        # Check if it's a reflection prompt
        for msg in messages:
            if msg.get("role") == "system" and "reflection agent" in msg.get("content", ""):
                return {"role": "assistant", "content": '{"complete": false, "answer": "Keep going"}'}
                
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "name": "read_huge_file",
                    "arguments": {"path": "huge.txt"}
                }
            ]
        }
        
    def chat(self, messages, **kwargs):
        return self.chat_with_tools(messages, [], **kwargs).get("content", "")

def test_context_thrashing(tmp_path):
    """Verify that observations are truncated when they exceed 85% of budget."""
    db_path = str(tmp_path / "test2.db")
    memory = SyncMemoryStore(db_path)
    engine = Engine(memory=memory)
    engine.initialize()
    
    import axiom.agents.orchestrator_agent
    axiom.agents.orchestrator_agent.MAX_TOOL_ROUNDS = 20
    
    agent = OrchestratorAgent(registry=engine.registry, bus=engine.event_bus, memory=memory)
    llm = MockThrashingLLM()
    agent.set_llm(llm)
    
    class DummyHugeReader:
        name = "read_huge_file"
        schema = {"type": "object", "properties": {"path": {"type": "string"}}}
        def execute(self, args):
            # Return something so large it takes up 90% of the 6144 max_tokens
            return {"output": "word " * 5000, "success": True}
            
    engine.registry.register_tool("read_huge_file", DummyHugeReader())
    
    result = agent.run("Read the huge file")
    engine.shutdown()
    
    assert "Context was successfully compressed!" in result.output.get("response", "")


def test_background_loop_starvation(tmp_path):
    """Verify that a blocking CPU task doesn't permanently deadlock the async bridge or event bus."""
    # The EventBus is synchronous, but let's test if the engine can shutdown gracefully
    # and if the FlightRecorder processed events despite a simulated delay.
    db_path = str(tmp_path / "test3.db")
    memory = SyncMemoryStore(db_path)
    engine = Engine(memory=memory)
    engine.initialize()
    
    bus = engine.event_bus
    events_received = []
    
    def slow_handler(event):
        events_received.append(event)
        time.sleep(0.5) # Simulate blocking CPU task
        
    bus.subscribe("test.blocking", slow_handler)
    
    start = time.time()
    bus.publish_sync("test.blocking", {"hello": "world"})
    bus.publish_sync("test.blocking", {"hello": "world2"})
    end = time.time()
    
    engine.shutdown()
    
    # Assert that it did block (synchronous bus) but recovered successfully
    assert len(events_received) == 2
    assert (end - start) >= 1.0 # 2 * 0.5s delays
    
    # Ensure FlightRecorder flushed
    trace_file = Path.home() / ".axiom" / "traces" / "flight_recorder.jsonl"
    if trace_file.exists():
        content = trace_file.read_text()
        assert "test.blocking" in content
