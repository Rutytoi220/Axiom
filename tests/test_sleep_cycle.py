import pytest
import json
from unittest.mock import MagicMock, patch
from axiom.memory.sleep_cycle import SleepCycleDaemon

@pytest.fixture
def mock_memory_store():
    store = MagicMock()
    # Mock conversation history
    store.get_conversation_history.return_value = [
        {"role": "user", "content": "I like python and I want to build an OS."},
        {"role": "assistant", "content": "That is a great project."},
        {"role": "user", "content": "Always format your code with black."},
        {"role": "assistant", "content": "Understood."},
    ]
    return store

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    # Mock LLM response for chat
    mock_summary = {
        "key_facts": ["User wants to build an OS", "User likes python"],
        "user_preferences": ["Format code with black"]
    }
    llm.chat.return_value = json.dumps(mock_summary)
    llm.chat_with_tools.return_value = {"content": json.dumps(mock_summary)}
    return llm

def test_run_consolidation_success(mock_memory_store, mock_llm):
    daemon = SleepCycleDaemon(bus=MagicMock(), memory_store=mock_memory_store, llm=mock_llm)
    
    # Run consolidation manually
    daemon._run_consolidation()
    
    # Check if memory store was called to set the episodic summary
    assert mock_memory_store.set.called
    args, kwargs = mock_memory_store.set.call_args
    assert "episodic_summary" in kwargs["tags"]
    assert "key_facts" in kwargs["value"]
    
    # Check if context was rotated
    mock_memory_store.create_conversation.assert_called_with("Continued Session")

def test_run_consolidation_not_enough_history(mock_memory_store, mock_llm):
    # Only 3 messages
    mock_memory_store.get_conversation_history.return_value = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Bye"}
    ]
    
    daemon = SleepCycleDaemon(bus=MagicMock(), memory_store=mock_memory_store, llm=mock_llm)
    daemon._run_consolidation()
    
    # Should exit early
    mock_memory_store.set.assert_not_called()
    mock_memory_store.create_conversation.assert_not_called()

def test_run_consolidation_no_llm(mock_memory_store):
    # No LLM provided
    daemon = SleepCycleDaemon(bus=MagicMock(), memory_store=mock_memory_store, llm=None)
    daemon._run_consolidation()
    
    # Should exit early
    mock_memory_store.set.assert_not_called()
    mock_memory_store.create_conversation.assert_not_called()
