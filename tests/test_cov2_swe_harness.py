import pytest
import os
import json
from pathlib import Path
from axiom.evals.swe_harness import TracebackSanitizer, BenchmarkMetrics, SWEBenchHarness
from axiom.core.events import EventBus
from axiom.core.engine import Engine
from unittest.mock import Mock

def test_traceback_sanitizer():
    sanitizer = TracebackSanitizer()
    long_log = "\n".join([f"line {i}" for i in range(100)])
    res = sanitizer.sanitize(long_log)
    assert "line 99" in res
    
    ignore_log = "/pluggy/ test\n/pytest/ test\n/importlib/ test\n/site-packages/ test\nvalid line"
    res2 = sanitizer.sanitize(ignore_log)
    assert "valid line" in res2
    assert "/pytest/" not in res2
    
    res3 = sanitizer.sanitize("just some log")
    assert "just some log" in res3

@pytest.fixture
def harness():
    engine = Mock(spec=Engine)
    engine.event_bus = EventBus()
    engine.registry = Mock()
    return SWEBenchHarness(engine)

@pytest.mark.asyncio
async def test_swe_harness_run_scenario_exception(harness, monkeypatch):
    from axiom.agents.swarm.coder_agent import CoderAgent
    async def mock_write(*args, **kwargs):
        raise Exception("Code error")
    monkeypatch.setattr(CoderAgent, "write_code", mock_write)
    
    metrics = await harness.run_scenario("test_err")
    assert not metrics.success

@pytest.mark.asyncio
async def test_swe_harness_repair(harness, tmp_path, monkeypatch):
    import subprocess
    from axiom.llm.ollama_client import OllamaClient
    from axiom.swarm.consensus import ConsensusEngine
    
    res = await harness.repair(str(tmp_path / "nope"))
    assert not res
    
    target = tmp_path / "target"
    target.mkdir()
    
    class MockResult:
        def __init__(self, code):
            self.returncode = code
            self.stdout = "out"
            self.stderr = "err"
    
    def mock_run_pass(*args, **kwargs):
        return MockResult(0)
    
    monkeypatch.setattr(subprocess, "run", mock_run_pass)
    res = await harness.repair(str(target))
    assert res
    
    p = target / "test.py"
    p.touch()
    
    def mock_read(*args, **kwargs): raise Exception("read fail")
    monkeypatch.setattr(Path, "read_text", mock_read)
    
    def mock_run_fail(*args, **kwargs): return MockResult(1)
    monkeypatch.setattr(subprocess, "run", mock_run_fail)
    
    def mock_chat(*args, **kwargs):
        return "not json"
    monkeypatch.setattr(OllamaClient, "chat", mock_chat)
    
    res = await harness.repair(str(target))
    assert not res

    def mock_chat2(*args, **kwargs):
        return "[]"
    monkeypatch.setattr(OllamaClient, "chat", mock_chat2)
    res = await harness.repair(str(target))
    assert not res

    def mock_chat3(*args, **kwargs):
        return '[{"name": "write_file", "arguments": {"path": "a", "content": "b"}}]'
    monkeypatch.setattr(OllamaClient, "chat", mock_chat3)
    
    async def mock_debate(*args, **kwargs): return False
    monkeypatch.setattr(ConsensusEngine, "run_debate", mock_debate)
    res = await harness.repair(str(target))
    assert not res
    
    async def mock_debate2(*args, **kwargs): return True
    monkeypatch.setattr(ConsensusEngine, "run_debate", mock_debate2)
    
    # Do NOT undo monkeypatch. Just redefine mock_read
    def mock_read_ok(*args, **kwargs): return "ok"
    monkeypatch.setattr(Path, "read_text", mock_read_ok)
    
    def mock_run_patch(*args, **kwargs):
        return MockResult(1)
    monkeypatch.setattr(subprocess, "run", mock_run_patch)
    
    def mock_write(*args, **kwargs): raise Exception("write error")
    monkeypatch.setattr(Path, "write_text", mock_write)
    
    res = await harness.repair(str(target))
    assert not res
