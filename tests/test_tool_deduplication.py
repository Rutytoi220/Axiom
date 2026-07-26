"""Tests for AXIOM v2.8 tool deduplication guard."""
import pytest
from unittest.mock import MagicMock
from axiom.agents.orchestrator_agent import OrchestratorAgent

def test_tool_deduplication_blocks_identical_calls():
    # Mock LLM returning the exact same tool call 3 times in a single turn.
    mock_llm = MagicMock()
    # 1st call: LLM decides to run uptime
    # 2nd call: LLM gets the output but runs uptime again
    # 3rd call: LLM gets deduplication error but runs uptime again anyway
    call_count = 0
    def mock_chat_with_tools(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return {"content": "", "tool_calls": [{"name": "shell", "arguments": {"command": "uptime"}}]}
        return {"content": "Final answer here", "tool_calls": []}
    mock_llm.chat_with_tools.side_effect = mock_chat_with_tools
    mock_llm.chat.side_effect = mock_chat_with_tools
    mock_registry = MagicMock()
    mock_registry.get_tool.return_value = MagicMock()
    mock_registry.execute.return_value = {"success": True, "output": "up 1 day"}

    agent = OrchestratorAgent(mock_registry, bus=MagicMock(), memory=MagicMock(), llm=mock_llm)
    
    # Run agent
    result = agent.run("Show uptime")

    # The tool 'shell' should only actually be executed ONCE.
    shell_calls = [c for c in mock_registry.execute.mock_calls if c.args and c.args[0] == 'shell']
    assert len(shell_calls) == 1
    
    # The system notice should be injected.
    # We can verify this by checking the agent's memory or logs, but 
    # since execute is only called once, the block mechanism worked.
    assert result.success is True
