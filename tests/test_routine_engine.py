import pytest
import asyncio
from axiom.core.routine import RoutineEngine

class MockOllama:
    def __init__(self):
        self.last_prompt = ""
        self.last_system = ""
        
    def generate(self, prompt, system_prompt=""):
        self.last_prompt = prompt
        self.last_system = system_prompt
        if "Friday" in prompt:
            return "0 17 * * 5"
        return "0 0 * * *"

class MockEventBus:
    def __init__(self):
        self.events = []
    def emit(self, event_name, payload):
        self.events.append((event_name, payload))

class MockEngine:
    def __init__(self):
        self.event_bus = MockEventBus()

class MockCLI:
    def __init__(self):
        self.ollama = MockOllama()
        self.memory = None
        self.orchestrator = None
        self.engine = MockEngine()

@pytest.mark.asyncio
async def test_parse_schedule_to_cron():
    cli = MockCLI()
    engine = RoutineEngine(cli)
    
    # Test valid natural language mapping
    cron = await engine.parse_schedule_to_cron("Organize my desktop every Friday at 5 PM")
    assert cron == "0 17 * * 5"

@pytest.mark.asyncio
async def test_parse_schedule_to_cron_fallback():
    cli = MockCLI()
    engine = RoutineEngine(cli)
    
    # Test fallback
    cron = await engine.parse_schedule_to_cron("random text")
    assert cron == "0 0 * * *"

class MockMemory:
    def __init__(self):
        self.data = {}
    def set(self, key, val, tags=None):
        self.data[key] = val
    def get(self, key):
        return self.data.get(key)
    def list_keys(self):
        return list(self.data.keys())
    def delete(self, key):
        if key in self.data:
            del self.data[key]
            return True
        return False

class MockOrchestrator:
    def run(self, prompt, use_tools=True, session_id=None):
        # We simulate blocking interactive input
        import builtins
        builtins.input("Test")
        return None # Unreachable due to error

class MockFullCLI(MockCLI):
    def __init__(self):
        super().__init__()
        self.memory = MockMemory()
        self.engine = MockEngine()
        self.orchestrator = MockOrchestrator()

@pytest.mark.asyncio
async def test_execute_routine_aborts_on_input():
    cli = MockFullCLI()
    engine = RoutineEngine(cli)
    
    # Inject a routine
    routine = {
        "id": "123",
        "prompt": "Test prompt",
        "cron_expression": "0 * * * *"
    }
    
    # Call _execute_routine directly
    await engine._execute_routine(routine)
    
    # Ensure it failed due to interaction
    events = cli.engine.event_bus.events
    assert len(events) >= 2
    assert events[0][0] == "routine.started"
    assert events[1][0] == "routine.requires_attention"
    assert events[1][1]["routine_id"] == "123"

