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
    
    raw_response = "<think>\nThinking about this...\n</think>\n\nFinal Answer: \ninvoke: assistant { \"answer\": \"Hello!\" }"
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
    # Tool-result fallback behavior is covered by the focused tests below.
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    # We can't easily mock the exact internal execution without more setup,
    # but we can test the specific block in a controlled way.
    pass


def test_empty_document_tool_result_uses_ocr_diagnostic():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    mock_llm.chat_with_tools.side_effect = [
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/scanned.pdf"}}}]},
        {"content": ""},
    ]
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{"function": {"name": "read_document_content", "parameters": {"properties": {"file_path": {"type": "string"}}}}}]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = None

    result = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm).run("read this PDF")

    assert "[Document Extraction Notice]: Zero selectable characters found in /tmp/scanned.pdf." in result.output["response"]


def test_echo_pruning_retries_conversational_response_before_persistence():
    class RecordingMemory:
        def __init__(self):
            self.records = []

        def get(self, key):
            return None

        def set(self, key, value, tags=None):
            self.records.append(value)

        def search(self, tags):
            return []

    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    mock_llm.chat.return_value = "Repeated answer"
    mock_llm.chat.side_effect = ["Repeated answer", "A fresh answer"]
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = []
    memory = RecordingMemory()
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), memory=memory, llm=mock_llm)
    agent._chat_history = [
        {"role": "user", "content": "previous task"},
        {"role": "assistant", "content": "Repeated answer"},
    ]

    result = agent.run("new task")

    assert result.output["response"] == "A fresh answer"
    assert mock_llm.chat.call_count == 2
    assert [{"role": message["role"], "content": message["content"]} for message in agent._chat_history] == [
        {"role": "user", "content": "previous task"},
        {"role": "assistant", "content": "Repeated answer"},
        {"role": "user", "content": "new task"},
        {"role": "assistant", "content": "A fresh answer"},
    ]
    reasoning_payloads = [record["payload"] for record in memory.records if record.get("kind") == "reasoning"]
    assert reasoning_payloads == [{"role": "assistant", "content": "A fresh answer"}]


def test_auto_unwrapper_skips_loop_breaker_notice_for_prior_tool_result():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    mock_llm.chat_with_tools.side_effect = [
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/report.pdf"}}}]},
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/report.pdf"}}}]},
        {"content": ""},
    ]
    mock_registry = Mock()
    mock_registry.get_schemas.return_value = [{"function": {"name": "read_document_content", "parameters": {"properties": {"file_path": {"type": "string"}}}}}]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"content": "Step 1 extracted content."}

    result = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm).run("read /tmp/report.pdf")

    assert "Step 1 extracted content." in result.output["response"]
    assert "[System Notice]" not in result.output["response"]


def test_direct_action_guard_is_first_system_instruction_and_blocks_greeting():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    mock_llm.capabilities = {"models": ["llama3.1:latest"]}
    mock_llm.config = Mock()
    mock_llm.config.model = "default"
    mock_llm.chat_with_tools.side_effect = [
        {"content": "I'm AXIOM, a conversational AI."},
        {"content": "", "tool_calls": [{"function": {"name": "file_read", "arguments": {"file_path": "/tmp/note.txt"}}}]},
        {"content": "The file is empty."},
    ]
    mock_registry = Mock()
    mock_registry.list_tools.return_value = {"file_read": Mock(description="read a file")}
    mock_registry.get_schemas.return_value = [{"function": {"name": "file_read", "parameters": {"properties": {"file_path": {"type": "string"}}}}}]
    mock_registry.execute.return_value.success = True
    mock_registry.execute.return_value.output = {"content": ""}
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)

    result = agent.run("check /tmp/note.txt")

    first_messages = mock_llm.chat_with_tools.call_args_list[0].args[0]
    first_system_message = next(message["content"] for message in first_messages if message["role"] == "system")
    assert first_system_message.startswith("CRITICAL EXECUTION RULE: You are operating in Direct Action Mode.")
    assert "I'm AXIOM" not in result.output["response"]
    assert result.output["response"] == "The file is empty."

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

def test_orchestrator_parenthesized_json_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "(read_document_content: {\"path\": \"/tmp/test.pdf\"})"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished reading paren json."} 
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
    assert "Finished reading paren json." in result.output["response"]
    
    # Verify the argument was successfully unwrapped and mapped to "file_path"
    call_args, call_kwargs = mock_registry.execute.call_args
    assert call_args[0] == "read_document_content"
    assert call_kwargs == {"file_path": "/tmp/test.pdf"}

def test_orchestrator_co_occurrence_tool_interceptor():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    raw_response = "I will use read_document_content on /tmp/test.pdf to read it. [Document content extracted]"
    
    mock_llm.chat_with_tools.side_effect = [
        {"content": raw_response}, 
        {"content": "Finished reading co-occurrence."} 
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
    assert "Finished reading co-occurrence." in result.output["response"]
    
    # Verify the argument was successfully unwrapped
    call_args, call_kwargs = mock_registry.execute.call_args
    assert call_args[0] == "read_document_content"
    assert call_kwargs == {"file_path": "/tmp/test.pdf"}
    
    # Verify the scrubber removed the bracketed placeholder
    # In this mock, the second turn was just "Finished reading co-occurrence." but if we returned it in the first turn, we could check final response.
    # We can check that the accumulated_response doesn't have the bracketed placeholder by looking at _chat_history.
    assert "[Document content extracted]" not in result.output["response"]

def test_orchestrator_in_turn_loop_breaker():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    # First it calls the tool normally
    # Second time it tries to call it again
    mock_llm.chat_with_tools.side_effect = [
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/test.pdf"}}}]},
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/test.pdf"}}}]},
        {"content": "Final response after being blocked."}
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
    # The registry should only be executed ONCE despite the LLM returning the tool call twice
    assert mock_registry.execute.call_count == 1
    assert "Final response after being blocked." in result.output["response"]

def test_orchestrator_silent_synthesis_auto_unwrap():
    mock_llm = Mock()
    mock_llm.is_available.return_value = True
    
    # 1. First turn returns a tool call
    # 2. Second turn (synthesis) returns an empty string despite the override prompt
    mock_llm.chat_with_tools.side_effect = [
        {"content": "", "tool_calls": [{"function": {"name": "read_document_content", "arguments": {"file_path": "/tmp/test.pdf"}}}]},
        {"content": ""}  # Silent synthesis!
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
    mock_registry.execute.return_value.output = {"content": "Here is the extracted PDF content..."}
    
    agent = OrchestratorAgent(registry=mock_registry, bus=Mock(), llm=mock_llm)
    result = agent.run("read my file", use_tools=True)
    
    assert result.success is True
    # The auto-unwrapper should kick in and print the observation directly
    assert "[Observation Result]:" in result.output["response"]
    assert "Here is the extracted PDF content..." in result.output["response"]
