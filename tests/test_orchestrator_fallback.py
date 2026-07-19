"""Tests for OrchestratorAgent fallback mechanisms."""

import pytest
from unittest.mock import Mock, patch
from axiom.agents.orchestrator_agent import OrchestratorAgent, AgentState

def test_orchestrator_empty_response_conversational():
    # Mock LLM to return empty content and no tool calls
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm.chat_with_tools.return_value = {"content": ""}
    mock_llm.chat.return_value = ""
    mock_llm.capabilities = {"models": ["qwen3:0.6b", "llama3.1:latest", "qwen3-coder:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = []
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    
    # We want to run one loop where THINK -> REFLECT -> EXIT happens
    result = agent.run("say nothing", use_tools=True)
    
    assert result.success is True
    assert "[!] The model returned an empty response. Try rephrasing or typing /help." in result.output["response"]
    assert "Task completed." not in result.output["response"]

def test_orchestrator_scrub_reasoning_and_prefixes():
    # Mock LLM to return a <think> block and a prefix
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "<think>\nThinking about this...\n</think>\n\nFinal Answer: Hello!"
    mock_llm.chat_with_tools.return_value = {"content": raw_response}
    mock_llm.chat.return_value = raw_response
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = []
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    
    result = agent.run("say hello", use_tools=True)
    
    assert result.success is True
    assert result.output["response"] == "Hello!"

def test_orchestrator_empty_response_with_tools():
    # If tools ran, it should say Task finished
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    # We can't easily mock the exact internal execution without more setup,
    # but we can test the specific block in a controlled way.
    pass

def test_orchestrator_plaintext_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "I need to read this file.\nread_document_content('/path/to/test.pdf')"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished reading."} 
    ]
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{
        "function": {
            "name": "read_document_content",
            "parameters": {
                "properties": {
                    "file_path": {"type": "string"}
                }
            }
        }
    }]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"content": "mock text"}
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    result = agent.run("read my file", use_tools=True)
    
    assert result.success is True
    # Verify execute was called with correct arguments
    mock_registry.execute.assert_called()
    assert "Finished reading." in result.output["response"]

def test_orchestrator_markdown_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "Here is the tool call:\n\n**read_document_content**\n```\n/path/to/test.pdf\n```"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished reading md."} 
    ]
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{
        "function": {
            "name": "read_document_content",
            "parameters": {
                "properties": {
                    "file_path": {"type": "string"}
                }
            }
        }
    }]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"content": "mock text"}
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    result = agent.run("read my file", use_tools=True)
    
    assert result.success is True
    mock_registry.execute.assert_called()
    assert "Finished reading md." in result.output["response"]

def test_orchestrator_colon_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "Action: read_document_content\n /path/to/test.pdf"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished reading colon."} 
    ]
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{
        "function": {
            "name": "read_document_content",
            "parameters": {
                "properties": {
                    "file_path": {"type": "string"}
                }
            }
        }
    }]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"content": "mock text"}
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    result = agent.run("read my file", use_tools=True)
    
    assert result.success is True
    mock_registry.execute.assert_called()
    assert "Finished reading colon." in result.output["response"]

def test_orchestrator_link_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "I will open it: [file_opener](/path/to/test.pdf)"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished opening link."} 
    ]
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{
        "function": {
            "name": "file_opener",
            "parameters": {
                "properties": {
                    "file_path": {"type": "string"}
                }
            }
        }
    }]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"message": "Opened file."}
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    result = agent.run("open file", use_tools=True)
    
    assert result.success is True
    mock_registry.execute.assert_called()
    assert "Finished opening link." in result.output["response"]

def test_orchestrator_chat_persona():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm._classify_task.return_value = "chat"
    mock_llm.chat.return_value = "Hello! I am AXIOM."
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    
    agent = OrchestratorAgent(registry=Mock(), bus=Mock(), llm=mock_llm)
    result = agent.run("hello", use_tools=False)
    
    assert result.success is True
    
    # We can inspect what was sent to chat
    calls = mock_llm.chat.call_args_list
    assert len(calls) > 0
    messages = calls[0].args[0]
    
    # Check that system prompt is clean and doesn't contain FORBIDDEN
    system_prompts = [m["content"] for m in messages if m["role"] == "system"]
    assert len(system_prompts) > 0
    assert "You are AXIOM" in system_prompts[0]
    assert "FORBIDDEN" not in system_prompts[0]
    assert "[Available System Capabilities]" not in system_prompts[0]
