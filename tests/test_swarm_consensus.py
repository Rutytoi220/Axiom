"""Tests for Swarm Blackboard and Consensus."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from axiom.swarm.blackboard import Blackboard, Proposal, Critique, Vote
from axiom.swarm.consensus import ConsensusEngine

@pytest.mark.asyncio
async def test_blackboard_state():
    bb = Blackboard()
    
    # Test proposal
    p = Proposal(author="agent1", content="My plan")
    await bb.post_proposal(p)
    
    fetched_p = await bb.get_proposal(p.id)
    assert fetched_p is not None
    assert fetched_p.content == "My plan"
    
    # Test critique
    c = Critique(target_proposal_id=p.id, author="agent2", content="Looks good")
    await bb.post_critique(c)
    
    critiques = await bb.get_critiques(p.id)
    assert len(critiques) == 1
    assert critiques[0].author == "agent2"
    
    # Test vote
    v = Vote(target_proposal_id=p.id, author="agent3", decision=True)
    await bb.post_vote(v)
    
    votes = await bb.get_votes(p.id)
    assert len(votes) == 1
    assert votes[0].decision is True
    
    # Test clear
    await bb.clear()
    assert await bb.get_proposal(p.id) is None


@pytest.mark.asyncio
@patch("axiom.swarm.consensus.OllamaClient")
async def test_consensus_engine_reaches_consensus(MockOllamaClient):
    # Setup mocks
    proposer_mock = MagicMock()
    critic_mock = MagicMock()
    
    def side_effect(*args, **kwargs):
        # We need distinct mock instances to return different values
        if "qwen3-coder" in args[0].model:
            return proposer_mock
        return critic_mock

    MockOllamaClient.side_effect = side_effect
    
    # Proposer returns a plan
    proposer_mock.chat.return_value = "I will write the file safely."
    # Critic approves
    critic_mock.chat.return_value = "This is safe. CONSENSUS_REACHED"
    
    bus = MagicMock()
    engine = ConsensusEngine(bus)
    
    # Run debate
    tools = [{"name": "delete_file", "arguments": {"path": "test.txt"}}]
    result = await engine.run_debate("delete this file", "context", tools)
    
    assert result is True
    
    # Verify bus events
    bus.publish_sync.assert_any_call("swarm.debate.started", {"task": "delete this file", "tool_count": 1})
    bus.publish_sync.assert_any_call("swarm.consensus.reached", {"consensus": True, "revisions": 0})
    
    # Verify blackboard state
    proposals = list(engine.blackboard.proposals.values())
    assert len(proposals) == 1
    
    critiques = await engine.blackboard.get_critiques(proposals[0].id)
    assert len(critiques) == 1
    assert critiques[0].consensus_reached is True


@pytest.mark.asyncio
@patch("axiom.swarm.consensus.OllamaClient")
async def test_consensus_engine_rejects(MockOllamaClient):
    proposer_mock = MagicMock()
    critic_mock = MagicMock()
    
    def side_effect(*args, **kwargs):
        if "qwen3-coder" in args[0].model:
            return proposer_mock
        return critic_mock

    MockOllamaClient.side_effect = side_effect
    
    proposer_mock.chat.return_value = "Plan 1"
    # Critic never says CONSENSUS_REACHED
    critic_mock.chat.return_value = "This is dangerous, do not proceed."
    
    bus = MagicMock()
    engine = ConsensusEngine(bus)
    
    tools = [{"name": "delete_file", "arguments": {"path": "test.txt"}}]
    result = await engine.run_debate("delete this file", "context", tools)
    
    assert result is False
    
    # Should have forced 1 revision round
    assert proposer_mock.chat.call_count == 2
    assert critic_mock.chat.call_count == 2
    
    bus.publish_sync.assert_any_call("swarm.consensus.failed", {"consensus": False, "revisions": 2})
