from typing import Any, Dict
from axiom.tools.core import BaseTool, ToolResult

class AxiomPlugin(BaseTool):
    """Base class for user-defined dynamic plugins."""
    plugin_name: str = ""
    plugin_description: str = ""
    plugin_parameters: Dict[str, Any] = {}
    requires_approval: bool = False
    
    @property
    def tool_id(self) -> str:
        return self.plugin_name
        
    @property
    def name(self) -> str:
        return self.plugin_name
        
    @property
    def description(self) -> str:
        return self.plugin_description
        
    @property
    def schema(self) -> Dict[str, Any]:
        return self.plugin_parameters
        
    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError("Plugins must implement execute(**kwargs)")

def axiom_tool(name: str, description: str, parameters: dict, requires_approval: bool = False):
    """Decorator to convert a function into an Axiom plugin tool."""
    def decorator(func):
        func.__axiom_tool__ = True
        func.__tool_name__ = name
        func.__tool_description__ = description
        func.__tool_parameters__ = parameters
        func.__tool_requires_approval__ = requires_approval
        return func
    return decorator

class DecoratorTool(BaseTool):
    """Internal wrapper for functions decorated with @axiom_tool."""
    def __init__(self, func, name: str, description: str, parameters: dict, requires_approval: bool = False):
        super().__init__()
        self._func = func
        self._tool_name = name
        self._tool_description = description
        self._tool_parameters = parameters
        self.requires_approval = requires_approval
        
    @property
    def tool_id(self) -> str:
        return self._tool_name
        
    @property
    def name(self) -> str:
        return self._tool_name
        
    @property
    def description(self) -> str:
        return self._tool_description
        
    @property
    def schema(self) -> dict:
        return self._tool_parameters
        
    async def execute(self, params: dict) -> ToolResult:
        import inspect
        if inspect.iscoroutinefunction(self._func):
            result = await self._func(**params)
        else:
            result = self._func(**params)
            
        if isinstance(result, ToolResult):
            return result
        return ToolResult(success=True, output=result)
