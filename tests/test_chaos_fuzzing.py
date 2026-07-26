import pytest
import asyncio
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.config import get_config

@pytest.mark.asyncio
async def test_chaos_fuzzing():
    agent = OrchestratorAgent()
    # Mock LLM client to simulate chaos
    # This is a placeholder test that runs 10 random inputs
    pass
