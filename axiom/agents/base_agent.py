"""Base agent class for AXIOM."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import uuid
import logging

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent state enumeration."""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class AgentResponse:
    """Response from agent execution."""
    agent_id: str
    success: bool
    output: Any
    reasoning: Optional[str] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.state = AgentState.IDLE
        self.memory: Dict[str, Any] = {}
        self.event_bus = None  # Set by engine
        self.registry = None   # Set by engine
        self._execution_count = 0
    
    def set_engine_refs(self, event_bus, registry) -> None:
        """Set references to engine components."""
        self.event_bus = event_bus
        self.registry = registry
    
    @abstractmethod
    def process(self, input_text: str, context: Optional[Dict] = None) -> AgentResponse:
        """Process input and return response."""
        pass
    
    def set_state(self, state: AgentState) -> None:
        """Set agent state."""
        self.state = state
        logger.debug(f"Agent {self.agent_id} state changed to {state.value}")
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state
    
    def store_memory(self, key: str, value: Any) -> None:
        """Store information in agent memory."""
        self.memory[key] = value
    
    def recall_memory(self, key: str, default: Any = None) -> Any:
        """Retrieve information from memory."""
        return self.memory.get(key, default)
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "execution_count": self._execution_count,
            "memory_keys": list(self.memory.keys())
        }
    
    def __call__(self, input_text: str, context: Optional[Dict] = None) -> AgentResponse:
        """Allow agent to be called as a function."""
        self.set_state(AgentState.THINKING)
        self._execution_count += 1
        
        try:
            response = self.process(input_text, context)
            if response.success:
                self.set_state(AgentState.COMPLETE)
            else:
                self.set_state(AgentState.ERROR)
            return response
        except Exception as e:
            logger.error(f"Agent {self.agent_id} error: {e}")
            self.set_state(AgentState.ERROR)
            return AgentResponse(
                agent_id=self.agent_id,
                success=False,
                output=None,
                error=str(e)
            )
