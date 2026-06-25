"""Echo agent implementation."""

from axiom.agents.base import AgentResult
from typing import Dict, Any, List


class SimpleBaseAgent:
    """Simplified base agent for sync execution."""

    def __init__(self, name: str, registry=None, bus=None, memory=None):
        """Initialize base agent.

        Args:
            name: Agent name
            registry: Component registry (optional)
            bus: Event bus for publishing events (optional)
            memory: Optional memory store
        """
        self.name = name
        self.registry = registry
        self.bus = bus
        self.memory = memory

    def run(self, task: str) -> AgentResult:
        """Execute a task. Must be overridden by subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")

    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        """Emit an event via the event bus (if available and callable)."""
        if self.bus and hasattr(self.bus, 'publish_sync'):
            try:
                self.bus.publish_sync(event, data)
            except Exception:
                pass  # Silently ignore if publish fails

    def _log(self, msg: str, steps: List[str]) -> None:
        """Add a step to the log."""
        steps.append(msg)


class EchoAgent(SimpleBaseAgent):
    """Agent that echoes back the task string."""

    def run(self, task: str) -> AgentResult:
        """Execute task by echoing it back.

        Args:
            task: Task to echo

        Returns:
            AgentResult with task as output
        """
        self._emit("agent.started", {"agent": self.name, "task": task})
        steps = []
        self._log(f"Received task: {task}", steps)

        try:
            from axiom.tools import EchoTool

            tool = EchoTool()
            result = tool.execute({"text": task})

            self._log(f"EchoTool returned: {result.output}", steps)
            self._emit(
                "agent.completed",
                {"agent": self.name, "success": result.success}
            )

            return AgentResult(
                success=result.success,
                output=result.output,
                error=result.error,
                steps_taken=steps
            )
        except Exception as e:
            self._log(f"Error: {str(e)}", steps)
            self._emit(
                "agent.error",
                {"agent": self.name, "error": str(e)}
            )
            return AgentResult(
                success=False,
                output=None,
                error=str(e),
                steps_taken=steps
            )
