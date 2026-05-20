"""Base tool classes and interfaces for AXIOM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self) -> str:
        return (
            f"ToolResult(success={self.success}, "
            f"output={self.output!r}, "
            f"error={self.error!r})"
        )


class BaseTool(ABC):
    """
    Abstract base class for all tools in AXIOM.
    
    Tools are reusable components that perform specific operations
    and return structured results.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Name of the tool.
        
        Returns:
            Unique identifier for this tool
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what the tool does.
        
        Returns:
            Description string
        """
        pass
    
    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """
        JSON Schema describing the expected input parameters.
        
        Returns:
            Dict with JSON Schema format for parameters
            Example:
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 30}
                },
                "required": ["command"]
            }
        """
        pass
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            params: Dictionary of parameters matching the schema
        
        Returns:
            ToolResult with success status and output/error
        """
        pass
