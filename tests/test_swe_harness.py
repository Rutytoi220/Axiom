"""Tests for SWE-Bench Evaluation Harness."""

import pytest
import asyncio
from unittest.mock import Mock, patch

from axiom.core.engine import Engine
from axiom.core.events import EventBus, Event
from axiom.evals.swe_harness import SWEBenchHarness


@pytest.fixture
def engine():
    engine = Mock(spec=Engine)
    engine.event_bus = EventBus()
    engine.registry = Mock()
    # Mock the registry's get_tool to return an async mock
    from unittest.mock import AsyncMock
    engine.registry.get_tool.return_value = AsyncMock()
    return engine


@pytest.fixture
def harness(engine):
    return SWEBenchHarness(engine)


def test_harness_sandbox_creation(harness):
    sandbox_path = harness.setup_sandbox()
    
    assert sandbox_path.exists()
    assert sandbox_path.is_dir()
    
    logic_py = sandbox_path / "logic.py"
    test_logic_py = sandbox_path / "test_logic.py"
    
    assert logic_py.exists()
    assert test_logic_py.exists()
    
    content = logic_py.read_text()
    assert "return a - b" in content
    
    harness.cleanup_sandbox()
    assert not sandbox_path.exists()


@pytest.mark.asyncio
async def test_harness_run_scenario_success(harness):
    # This simulates a successful run
    metrics = await harness.run_scenario("test-scenario")
    
    assert metrics.scenario_name == "test-scenario"
    assert metrics.success is True
    assert metrics.time_elapsed_sec > 0


def test_harness_metric_tracking_events(harness):
    # Simulate events that the harness should be tracking
    harness.event_bus.publish(Event("swarm.proposal", "test", data={"proposal_id": "1"}))
    harness.event_bus.publish(Event("swarm.vote", "test", data={"vote": "APPROVED"}))
    harness.event_bus.publish(Event("swarm.vote", "test", data={"vote": "REJECTED"}))
    harness.event_bus.publish(Event("transaction.rolled_back", "test", data={}))
    
    assert harness.metrics.total_rounds == 1
    assert harness.metrics.proposals_approved == 1
    assert harness.metrics.proposals_rejected == 1
    assert harness.metrics.rollbacks_triggered == 1


@pytest.mark.asyncio
async def test_run_suite_generates_markdown(harness):
    report = await harness.run_suite()
    
    assert "AXIOM Swarm Autonomous SWE-Bench Scorecard" in report
    assert "off-by-one-error" in report
    assert "syntax-error" in report
    assert "✅" in report or "❌" in report


@pytest.mark.asyncio
@patch("subprocess.run")
@patch("axiom.evals.swe_harness.OllamaClient")
@patch("axiom.evals.swe_harness.ConsensusEngine")
async def test_repair_success(MockConsensusEngine, MockOllamaClient, mock_run, harness, tmp_path):
    # Setup test directory
    test_dir = tmp_path / "buggy_project"
    test_dir.mkdir()
    
    file_path = test_dir / "math.py"
    file_path.write_text("def add(a, b): return a - b")
    
    # Mock LLM to return valid JSON tool call
    llm_mock = Mock()
    llm_mock.chat.return_value = f'[{{"name": "write_file", "arguments": {{"path": "{file_path}", "content": "def add(a, b): return a + b"}}}}]'
    MockOllamaClient.return_value = llm_mock
    
    # Mock ConsensusEngine to approve
    consensus_mock = Mock()
    # run_debate is async
    from unittest.mock import AsyncMock
    consensus_mock.run_debate = AsyncMock(return_value=True)
    MockConsensusEngine.return_value = consensus_mock
    
    # Mock subprocess.run for pytest
    # First call: fail, Second call (verify): success
    mock_run_fail = Mock()
    mock_run_fail.returncode = 1
    mock_run_fail.stdout = "FAILED test_add"
    mock_run_fail.stderr = "assert 2 == 5"
    
    mock_run_success = Mock()
    mock_run_success.returncode = 0
    mock_run_success.stdout = "PASSED"
    mock_run_success.stderr = ""
    
    mock_run.side_effect = [mock_run_fail, mock_run_success]
    
    # Track publishes
    harness.event_bus.publish_sync = Mock()
    
    result = await harness.repair(str(test_dir))
    
    assert result is True
    
    # The file should be updated
    assert file_path.read_text() == "def add(a, b): return a + b"
    
    # EventBus should broadcast success
    harness.event_bus.publish_sync.assert_called_with("harness.repair.success", {"target": str(test_dir.resolve()), "attempts": 1})


@pytest.mark.asyncio
@patch("subprocess.run")
@patch("axiom.evals.swe_harness.OllamaClient")
@patch("axiom.evals.swe_harness.ConsensusEngine")
async def test_repair_rollback_on_failure(MockConsensusEngine, MockOllamaClient, mock_run, harness, tmp_path):
    test_dir = tmp_path / "buggy_project2"
    test_dir.mkdir()
    
    file_path = test_dir / "math.py"
    file_path.write_text("def add(a, b): return a - b")
    
    # Mock LLM
    llm_mock = Mock()
    llm_mock.chat.return_value = f'[{{"name": "write_file", "arguments": {{"path": "{file_path}", "content": "def add(a, b): return a * b"}}}}]'
    MockOllamaClient.return_value = llm_mock
    
    # Mock ConsensusEngine to approve
    consensus_mock = Mock()
    from unittest.mock import AsyncMock
    consensus_mock.run_debate = AsyncMock(return_value=True)
    MockConsensusEngine.return_value = consensus_mock
    
    # Mock subprocess.run for pytest
    # ALWAYS fail
    mock_run_fail = Mock()
    mock_run_fail.returncode = 1
    mock_run_fail.stdout = "FAILED"
    mock_run_fail.stderr = ""
    
    mock_run.return_value = mock_run_fail
    
    harness.event_bus.publish_sync = Mock()
    
    result = await harness.repair(str(test_dir))
    
    # Should fail after 3 attempts
    assert result is False
    
    # The file should be rolled back to original
    assert file_path.read_text() == "def add(a, b): return a - b"
    
    # EventBus should broadcast failure
    harness.event_bus.publish_sync.assert_called_with("harness.repair.failed", {"target": str(test_dir.resolve())})
