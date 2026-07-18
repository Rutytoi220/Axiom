"""Base Subagent class for the Multi-Agent Swarm."""

import logging
from typing import Any, Dict, Optional
from axiom.agents.base import BaseAgent, AgentResult
from axiom.agents.swarm.consensus import ConsensusEngine
from axiom.core.transaction import MUTATING_TOOL_NAMES

logger = logging.getLogger(__name__)


class BaseSubagent(BaseAgent):
    """A specialized lightweight agent for swarm architectures.
    
    Subscribes to specific EventBus topics and enforces consensus
    before executing destructive tool operations. Stores intermediate
    scratchpad state in an ephemeral Blackboard rather than the global
    SQLite memory store.
    """

    def __init__(
        self,
        name: str,
        description: str,
        topic: str,
        event_bus=None,
        tool_registry=None,
        llm_client=None,
        blackboard=None,
        session_id: Optional[str] = None,
    ):
        super().__init__(name, description, event_bus, tool_registry)
        self.topic = topic
        self.llm_client = llm_client
        self.consensus = ConsensusEngine(event_bus) if event_bus else None

        # Blackboard scratchpad — ephemeral, session-scoped, RAM-only
        self.blackboard = blackboard
        self.session_id = session_id or "default_session"

        # Subscribe to tasks matching this subagent's topic
        if self.event_bus:
            self.event_bus.subscribe(self.topic, self._handle_task_event)

    # ------------------------------------------------------------------
    # Blackboard helpers
    # ------------------------------------------------------------------

    def _write_to_blackboard(self, key: str, value: Any) -> None:
        """Write an intermediate artifact to the Blackboard scratchpad.

        Uses the canonical URI: blackboard://<session_id>/<agent_name>/<key>.
        No-ops silently if no Blackboard is attached.
        """
        if self.blackboard is None:
            return
        self.blackboard.write(self.session_id, self.name, key, value)
        logger.debug(
            "[%s] Blackboard WRITE %s",
            self.name,
            self.blackboard.uri(self.session_id, self.name, key),
        )

    def _read_from_blackboard(self, key: str, default: Any = None) -> Any:
        """Read a scratchpad artifact from this agent's Blackboard namespace."""
        if self.blackboard is None:
            return default
        return self.blackboard.read(self.session_id, self.name, key, default)

    def _read_agent_artifact(self, agent_id: str, key: str, default: Any = None) -> Any:
        """Read an artifact from another agent's Blackboard namespace (cross-agent read)."""
        if self.blackboard is None:
            return default
        return self.blackboard.read(self.session_id, agent_id, key, default)

    # ------------------------------------------------------------------
    # Task handler
    # ------------------------------------------------------------------

    def _handle_task_event(self, event) -> None:
        """Handle incoming tasks from the EventBus asynchronously."""
        task = event.data.get("task")
        logger.info(f"[{self.name}] Received task on topic '{self.topic}': {task}")

    async def _execute_tool_safely(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 5.0) -> Any:
        """Execute a tool, requiring consensus if it is destructive.
        
        After execution, the result is automatically written to the Blackboard
        scratchpad under the key ``last_tool_result``.

        Args:
            tool_name: The name of the tool to execute.
            arguments: The arguments for the tool.
            timeout: Consensus timeout in seconds.
            
        Returns:
            The tool's result, or an error dictionary if rejected/failed.
        """
        if not self.tool_registry:
            return {"error": "No tool registry available"}

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found."}

        # Consensus Guard for mutating tools
        if tool_name in MUTATING_TOOL_NAMES:
            if not self.consensus:
                return {"error": "Consensus engine required for mutating tools"}
                
            logger.info(f"[{self.name}] Tool '{tool_name}' is destructive. Proposing to swarm...")
            approved = self.consensus.propose(
                agent_name=self.name,
                tool_name=tool_name,
                arguments=arguments,
                timeout=timeout
            )
            
            if not approved:
                logger.warning(f"[{self.name}] Proposal for '{tool_name}' REJECTED or TIMED OUT.")
                return {"error": "Execution blocked: Swarm consensus rejected the proposal."}
                
            logger.info(f"[{self.name}] Proposal for '{tool_name}' APPROVED. Executing...")

        # Execute the tool
        try:
            result = await tool(**arguments) if getattr(tool, 'is_async', False) else tool(**arguments)
            # Write intermediate result to Blackboard scratchpad
            self._write_to_blackboard(f"{tool_name}_result", result)
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Tool execution failed: {e}")
            error = {"error": str(e)}
            self._write_to_blackboard(f"{tool_name}_error", error)
            return error

    async def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """Default run implementation to be overridden by subclasses."""
        return AgentResult(success=True, output=f"Executed task: {task}")


