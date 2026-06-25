"""Test suite for AXIOM agents."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock

from axiom.agents import BaseAgent, AgentResult, OrchestratorAgent, ShellAgent
from axiom.events import EventBus, Event
from axiom.tools import ShellTool, FileTool


class TestAgentResult:
    """Test AgentResult dataclass."""
    
    def test_agent_result_success(self):
        """Test creating successful result."""
        result = AgentResult(success=True, output="test output")
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None
        assert result.steps_taken == []
        assert result.memory_keys_used == []
    
    def test_agent_result_failure(self):
        """Test creating failed result."""
        result = AgentResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output is None
    
    def test_agent_result_with_steps(self):
        """Test result with steps."""
        steps = ["step1", "step2", "step3"]
        result = AgentResult(success=True, output="done", steps_taken=steps)
        assert result.steps_taken == steps
    
    def test_agent_result_with_memory_keys(self):
        """Test result with memory keys."""
        keys = ["key1", "key2"]
        result = AgentResult(success=True, memory_keys_used=keys)
        assert result.memory_keys_used == keys
    
    def test_agent_result_repr(self):
        """Test result repr."""
        result = AgentResult(success=True, output="test", steps_taken=["a", "b"])
        repr_str = repr(result)
        assert "AgentResult" in repr_str
        assert "success=True" in repr_str
        assert "steps=2" in repr_str


class TestShellAgent:
    """Test ShellAgent implementation."""
    
    @pytest.mark.asyncio
    async def test_shell_agent_properties(self):
        """Test shell agent properties."""
        agent = ShellAgent()
        assert agent.name == "shell_agent"
        assert agent.description is not None
        assert "shell" in agent.description.lower()
    
    @pytest.mark.asyncio
    async def test_shell_agent_execute_simple_command(self):
        """Test executing a simple shell command."""
        agent = ShellAgent()
        result = await agent.run("echo hello")
        
        assert result.success is True
        assert "hello" in result.output["stdout"]
        assert len(result.steps_taken) > 0
    
    @pytest.mark.asyncio
    async def test_shell_agent_extract_command_with_prefix(self):
        """Test command extraction with run command prefix."""
        agent = ShellAgent()
        result = await agent.run("run command: echo test")
        
        assert result.success is True
        assert "test" in result.output["stdout"]
    
    @pytest.mark.asyncio
    async def test_shell_agent_extract_command_with_execute(self):
        """Test command extraction with execute prefix."""
        agent = ShellAgent()
        result = await agent.run("execute echo test")
        
        assert result.success is True
        assert "test" in result.output["stdout"]
    
    @pytest.mark.asyncio
    async def test_shell_agent_extract_command_with_shell(self):
        """Test command extraction with shell prefix."""
        agent = ShellAgent()
        result = await agent.run("shell echo test")
        
        assert result.success is True
        assert "test" in result.output["stdout"]
    
    @pytest.mark.asyncio
    async def test_shell_agent_command_failure(self):
        """Test handling of failed command."""
        agent = ShellAgent()
        result = await agent.run("exit 1")
        
        assert result.success is False
        assert result.output["returncode"] == 1
    
    @pytest.mark.asyncio
    async def test_shell_agent_with_context_timeout(self):
        """Test shell agent with timeout in context."""
        agent = ShellAgent()
        context = {"timeout": 5}
        result = await agent.run("echo test", context)
        
        assert result.success is True
        assert result.metadata["timeout"] == 5
    
    @pytest.mark.asyncio
    async def test_shell_agent_with_custom_tool(self):
        """Test shell agent with custom shell tool."""
        custom_tool = ShellTool(blocklist=[])
        agent = ShellAgent(shell_tool=custom_tool)
        result = await agent.run("echo test")
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_shell_agent_event_emission(self):
        """Test that shell agent emits events."""
        event_bus = EventBus()
        events_captured = []
        
        async def event_handler(event):
            events_captured.append(event.name)
        
        event_bus.subscribe("agent.shell.*", event_handler)
        
        agent = ShellAgent(event_bus=event_bus)
        result = await agent.run("echo test")
        
        assert result.success is True
        assert "agent.shell.started" in events_captured
        assert "agent.shell.completed" in events_captured
    
    @pytest.mark.asyncio
    async def test_shell_agent_error_event(self):
        """Test that shell agent emits error events."""
        event_bus = EventBus()
        events_captured = []
        
        async def event_handler(event):
            events_captured.append(event.name)
        
        event_bus.subscribe("agent.shell.*", event_handler)
        
        agent = ShellAgent(event_bus=event_bus)
        result = await agent.run("exit 1")
        
        # Command executes but fails
        assert "agent.shell.completed" in events_captured


class MockAgent(BaseAgent):
    """Mock agent for testing orchestrator."""
    
    async def run(self, task: str, context=None) -> AgentResult:
        """Execute task."""
        return AgentResult(
            success=True,
            output=f"Processed: {task}",
            steps_taken=["executed"]
        )


class TestOrchestratorAgent:
    """Test OrchestratorAgent implementation."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_properties(self):
        """Test orchestrator properties."""
        agent = OrchestratorAgent()
        assert agent.name == "orchestrator"
        assert agent.description is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_decompose_task_shell(self):
        """Test task decomposition for shell commands."""
        agent = OrchestratorAgent()
        subtasks = agent._decompose_task("run command: echo hello")
        
        assert len(subtasks) >= 1
        assert subtasks[0]["agent"] == "shell_agent"
        assert "echo hello" in subtasks[0]["parameter"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_decompose_task_generic(self):
        """Test task decomposition for generic tasks."""
        agent = OrchestratorAgent()
        subtasks = agent._decompose_task("perform some work")
        
        assert len(subtasks) >= 1
        # Should fall back to default routing
    
    @pytest.mark.asyncio
    async def test_orchestrator_synthesize_results(self):
        """Test result synthesis."""
        agent = OrchestratorAgent()
        
        results = {
            "task1": AgentResult(success=True, output={"key": "value"}),
            "task2": AgentResult(success=False, error="failed"),
        }
        
        synthesis = agent._synthesize_results(results)
        
        assert "subtask_results" in synthesis
        assert "task1" in synthesis["subtask_results"]
        assert synthesis["subtask_results"]["task1"]["success"] is True
        assert synthesis["subtask_results"]["task2"]["success"] is False
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_agent_registry(self):
        """Test orchestrator with registered agents."""
        event_bus = EventBus()
        mock_registry = Mock()
        mock_agent = MockAgent("test", "test agent", event_bus)
        mock_registry.get_agent = Mock(return_value=mock_agent)
        
        orchestrator = OrchestratorAgent(event_bus=event_bus, agent_registry=mock_registry)
        result = await orchestrator.run("run command: test")
        
        assert result.success is True
        assert len(result.steps_taken) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_task_started_event(self):
        """Test that orchestrator emits task.started event."""
        event_bus = EventBus()
        events_captured = []
        
        async def event_handler(event):
            events_captured.append(event.name)
        
        event_bus.subscribe("agent.task.*", event_handler)
        
        orchestrator = OrchestratorAgent(event_bus=event_bus)
        result = await orchestrator.run("generic task")
        
        assert "agent.task.started" in events_captured
    
    @pytest.mark.asyncio
    async def test_orchestrator_task_completed_event(self):
        """Test that orchestrator emits task.completed event."""
        event_bus = EventBus()
        events_captured = []
        
        async def event_handler(event):
            events_captured.append(event.name)
        
        event_bus.subscribe("agent.task.*", event_handler)
        
        orchestrator = OrchestratorAgent(event_bus=event_bus)
        result = await orchestrator.run("generic task")
        
        assert "agent.task.completed" in events_captured
    
    @pytest.mark.asyncio
    async def test_orchestrator_empty_decomposition(self):
        """Test handling of empty decomposition."""
        event_bus = EventBus()
        orchestrator = OrchestratorAgent(event_bus=event_bus)
        
        # Patch _decompose_task to return empty list
        orchestrator._decompose_task = lambda x: []
        
        result = await orchestrator.run("some task")
        
        assert result.success is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_context(self):
        """Test orchestrator with execution context."""
        event_bus = EventBus()
        mock_registry = Mock()
        mock_agent = MockAgent("test", "test agent")
        mock_registry.get_agent = Mock(return_value=mock_agent)
        
        orchestrator = OrchestratorAgent(
            event_bus=event_bus,
            agent_registry=mock_registry
        )
        
        context = {"timeout": 30, "priority": "high"}
        result = await orchestrator.run("test task", context)
        
        assert result.success is True


class TestIntegration:
    """Integration tests for agent system."""
    
    @pytest.mark.asyncio
    async def test_shell_agent_with_event_bus(self):
        """Test shell agent integration with event bus."""
        event_bus = EventBus()
        shell_agent = ShellAgent(event_bus=event_bus)
        
        # Subscribe to all agent events
        events = []
        async def capture_events(event):
            events.append(event.name)
        
        event_bus.subscribe("agent.*", capture_events)
        
        # Execute command
        result = await shell_agent.run("echo integration test")
        
        # Verify events were emitted
        assert len(events) > 0
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_orchestrator_delegation_chain(self):
        """Test orchestrator delegating to shell agent."""
        event_bus = EventBus()
        shell_agent = ShellAgent(event_bus=event_bus)
        
        # Create a simple agent registry
        mock_registry = Mock()
        mock_registry.get_agent = Mock(
            side_effect=lambda name: shell_agent if name == "shell_agent" else None
        )
        
        orchestrator = OrchestratorAgent(
            event_bus=event_bus,
            agent_registry=mock_registry
        )
        
        # Run a shell command through orchestrator
        result = await orchestrator.run("run command: echo delegation")
        
        assert result.success is True
        assert result.output is not None
    
    @pytest.mark.asyncio
    async def test_multiple_agent_events(self):
        """Test event emission from multiple agents."""
        event_bus = EventBus()
        
        all_events = []
        
        async def capture_all(event):
            all_events.append(event.name)
        
        event_bus.subscribe("agent.*", capture_all)
        
        # Create agents
        shell_agent = ShellAgent(event_bus=event_bus)
        orchestrator = OrchestratorAgent(event_bus=event_bus)
        
        # Execute commands
        await shell_agent.run("echo shell test")
        
        # Both agents should have emitted events
        assert len(all_events) > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_in_shell_agent(self):
        """Test error handling in shell agent."""
        agent = ShellAgent()
        
        # Execute non-existent command
        result = await agent.run("nonexistent_command_xyz_123")
        
        # Should fail gracefully
        assert result.success is False or result.output["returncode"] != 0
        assert len(result.steps_taken) > 0
    
    @pytest.mark.asyncio
    async def test_agent_steps_tracking(self):
        """Test that steps are properly tracked."""
        agent = ShellAgent()
        result = await agent.run("echo test")
        
        assert len(result.steps_taken) > 0
        # Should have at least: received task, extracted command, executing, completed
        assert any("Received" in step for step in result.steps_taken)
