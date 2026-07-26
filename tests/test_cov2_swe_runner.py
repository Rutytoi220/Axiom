import pytest
import os
import json
from pathlib import Path
from axiom.evals.swe_runner import SWERunner, BenchmarkProblem
from axiom.core.engine import Engine
from axiom.core.events import EventBus
from unittest.mock import Mock

@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    engine = Mock(spec=Engine)
    engine.event_bus = EventBus()
    engine.registry = Mock()
    return SWERunner(engine)

@pytest.mark.asyncio
async def test_swe_runner_run_eval(runner, tmp_path, monkeypatch):
    import subprocess
    from axiom.llm.ollama_client import OllamaClient
    from axiom.swarm.consensus import ConsensusEngine
    
    # 1. repo not found
    prob1 = BenchmarkProblem("", str(tmp_path / "nope"), "pytest")
    res = await runner.run_evaluation(prob1)
    assert not res['success']
    
    # Setup target
    target = tmp_path / "target"
    target.mkdir()
    p = target / "test.py"
    p.touch()
    
    prob2 = BenchmarkProblem("", str(target), "pytest")
    
    # 2. File read error
    def mock_read(*args, **kwargs): raise Exception("read")
    monkeypatch.setattr(Path, "read_text", mock_read)
    
    # 3. JSON parsing error
    def mock_chat(*args, **kwargs): return "not json"
    monkeypatch.setattr(OllamaClient, "chat", mock_chat)
    
    res = await runner.run_evaluation(prob2)
    assert not res['success']
    
    # 4. No edits
    def mock_chat2(*args, **kwargs): return "[]"
    monkeypatch.setattr(OllamaClient, "chat", mock_chat2)
    res = await runner.run_evaluation(prob2)
    assert not res['success']
    
    # 5. Patch write exception
    def mock_chat3(*args, **kwargs):
        return '[{"name": "write_file", "arguments": {"path": "a", "content": "b"}}]'
    monkeypatch.setattr(OllamaClient, "chat", mock_chat3)
    
    def mock_write(*args, **kwargs): raise Exception("write")
    monkeypatch.setattr(Path, "write_text", mock_write)
    
    res = await runner.run_evaluation(prob2)
    assert not res['success']
