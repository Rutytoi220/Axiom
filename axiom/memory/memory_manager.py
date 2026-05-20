"""Memory manager for AXIOM - conversation and state management."""

import uuid
from typing import Any, Dict, List, Optional
from axiom.memory.db import Database
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages all memory operations for AXIOM."""
    
    def __init__(self, db_path: str = "axiom.db"):
        self.db = Database(db_path)
        self._current_conversation: Optional[str] = None
    
    def create_conversation(self, title: str = "") -> str:
        """Create a new conversation."""
        conversation_id = str(uuid.uuid4())
        self.db.save_conversation(conversation_id, title)
        self._current_conversation = conversation_id
        logger.info(f"Created conversation {conversation_id}")
        return conversation_id
    
    def set_conversation(self, conversation_id: str) -> None:
        """Set the current conversation."""
        self._current_conversation = conversation_id
    
    def get_conversation(self) -> Optional[str]:
        """Get the current conversation ID."""
        return self._current_conversation
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        """Add a message to the current conversation."""
        if not self._current_conversation:
            raise RuntimeError("No active conversation")
        
        message_id = str(uuid.uuid4())
        self.db.add_message(
            self._current_conversation, 
            message_id, 
            role, 
            content, 
            metadata
        )
        logger.debug(f"Added message {message_id} to conversation")
        return message_id
    
    def get_conversation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get conversation history."""
        if not self._current_conversation:
            return []
        
        return self.db.get_messages(self._current_conversation, limit)
    
    def save_tool_execution(self, tool_name: str, input_data: Any, 
                           output_data: Any, context_id: Optional[str] = None) -> str:
        """Save tool execution result."""
        result_id = str(uuid.uuid4())
        self.db.save_tool_result(
            result_id,
            context_id or self._current_conversation or "unknown",
            tool_name,
            input_data,
            output_data
        )
        logger.debug(f"Saved tool result {result_id}")
        return result_id
    
    def save_agent_state(self, agent_id: str, state: Dict[str, Any]) -> None:
        """Save agent state."""
        for key, value in state.items():
            self.db.save_agent_memory(agent_id, key, value)
        logger.debug(f"Saved agent state for {agent_id}")
    
    def get_agent_state(self, agent_id: str, key: str, default: Any = None) -> Any:
        """Get agent state value."""
        value = self.db.get_agent_memory(agent_id, key)
        return value if value is not None else default
    
    def save_system_state(self, key: str, value: Any) -> None:
        """Save system state."""
        self.db.save_system_state(key, value)
        logger.debug(f"Saved system state {key}")
    
    def get_system_state(self, key: str, default: Any = None) -> Any:
        """Get system state."""
        value = self.db.get_system_state(key)
        return value if value is not None else default
