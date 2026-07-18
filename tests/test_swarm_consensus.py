"""Tests for the Multi-Agent Swarm Orchestration & Consensus Protocol."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from axiom.core.events import EventBus, Event
from axiom.agents.swarm.consensus import ConsensusEngine, ProposalState
from axiom.agents.swarm.coder_agent import CoderAgent
from axiom.agents.swarm.test_runner_agent import TestRunnerAgent


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def tool_registry():
    registry = Mock()
    mock_write = AsyncMock(return_value="File written")
    registry.get_tool.return_value = mock_write
    return registry


@pytest.mark.asyncio
async def test_consensus_approval(event_bus, tool_registry):
    # Setup agents
    coder = CoderAgent(event_bus=event_bus, tool_registry=tool_registry)
    reviewer = TestRunnerAgent(event_bus=event_bus, tool_registry=tool_registry)
    
    # Coder attempts to write a python file. The reviewer should approve it.
    result = await coder.write_code("test_file.py", "print('hello')")
    
    assert "error" not in result["result"]
    assert result["result"] == "File written"
    
    # Verify the tool was actually executed
    tool = tool_registry.get_tool("write_file")
    tool.assert_called_once_with(path="test_file.py", content="print('hello')")


@pytest.mark.asyncio
async def test_consensus_rejection(event_bus, tool_registry):
    # Setup agents
    coder = CoderAgent(event_bus=event_bus, tool_registry=tool_registry)
    reviewer = TestRunnerAgent(event_bus=event_bus, tool_registry=tool_registry)
    
    # Coder attempts to write a non-python file. The reviewer should reject it.
    result = await coder.write_code("evil_script.sh", "rm -rf /")
    
    assert "error" in result["result"]
    assert "Execution blocked" in result["result"]["error"]
    
    # Verify the tool was NOT executed
    tool = tool_registry.get_tool("write_file")
    tool.assert_not_called()


@pytest.mark.asyncio
async def test_consensus_deadlock_timeout(event_bus, tool_registry):
    # Setup ONLY the coder. No reviewer exists to vote.
    coder = CoderAgent(event_bus=event_bus, tool_registry=tool_registry)
    
    # Mock the timeout to be very short for the test
    with patch("axiom.agents.swarm.base_subagent.ConsensusEngine.propose") as mock_propose:
        # Instead of actually timing out (which we test below), we can just force the return
        mock_propose.return_value = False
        
        result = await coder.write_code("test_file.py", "print('hello')")
        assert "error" in result["result"]


def test_consensus_engine_deadlock_mitigation(event_bus):
    engine = ConsensusEngine(event_bus)
    
    # Propose with a 0.1s timeout and no voters
    approved = engine.propose(
        agent_name="GhostAgent",
        tool_name="write_file",
        arguments={"path": "test.py"},
        timeout=0.1
    )
    
    assert approved is False
    
    # Find the proposal and verify its state is REJECTED
    assert len(engine._proposals) == 1
    proposal_id = list(engine._proposals.keys())[0]
    assert engine._proposals[proposal_id]["state"] == ProposalState.REJECTED
