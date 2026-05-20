"""Base tool class for AXIOM tool system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata or {}
        }


class BaseTool(ABC):
    """Base class for all AXIOM tools."""
    
    def __init__(self, tool_id: str, name: str, description: str):
        self.tool_id = tool_id
        self.name = name
        self.description = description
        self.parameters: List[ToolParameter] = []
        self._execution_count = 0
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def validate_parameters(self, **kwargs) -> bool:
        """Validate input parameters."""
        required_params = {p.name for p in self.parameters if p.required}
        provided_params = set(kwargs.keys())
        
        if not required_params.issubset(provided_params):
            missing = required_params - provided_params
            logger.error(f"Missing required parameters: {missing}")
            return False
        
        return True
    
    def add_parameter(self, param: ToolParameter) -> None:
        """Add a parameter definition."""
        self.parameters.append(param)
    
    def get_info(self) -> Dict[str, Any]:
        """Get tool information."""
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default
                }
                for p in self.parameters
            ],
            "execution_count": self._execution_count
        }
    
    def __call__(self, **kwargs) -> ToolResult:
        """Allow tool to be called as a function."""
        if not self.validate_parameters(**kwargs):
            return ToolResult(
                success=False,
                output=None,
                error="Invalid parameters"
            )
        
        try:
            self._execution_count += 1
            return self.execute(**kwargs)
        except Exception as e:
            logger.error(f"Error executing tool {self.tool_id}: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
