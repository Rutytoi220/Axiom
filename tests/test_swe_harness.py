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
