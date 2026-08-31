import logging
from abc import ABC
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

class ToolResult:
    """Represents the result of a tool execution."""

    def __init__(self, success: bool, output: Any=None, error: Optional[str]=None, metadata: Optional[Dict]=None):
        """Auto-generated docstring.

Args:
    success: Argument.
    output: Argument.
    error: Argument.
    metadata: Argument.

Returns:
    Return value.
"""
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}

    def __repr__(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if self.success:
            return f'ToolResult(success={self.success}, output={self.output!r})'
        return f'ToolResult(success={self.success}, error={self.error!r})'

    def to_dict(self, tool: str='', arguments: Optional[Dict[str, Any]]=None) -> Dict[str, Any]:
        """Return the strict AXIOM tool-result envelope."""
        result = {'output': self.output, 'error': self.error, 'metadata': self.metadata}
        return {'tool': tool, 'arguments': arguments or {}, 'result': result, 'success': bool(self.success)}

class ToolParameter:
    """Parameter definition for a tool."""

    def __init__(self, name: str, type: str, description: str, required: bool=True, default: Any=None):
        """Auto-generated docstring.

Args:
    name: Argument.
    type: Argument.
    description: Argument.
    required: Argument.
    default: Argument.

Returns:
    Return value.
"""
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default

class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self, tool_id: str | None = None, name: str | None = None, description: str | None = None):
        """Auto-generated docstring.

Args:
    tool_id: Argument.
    name: Argument.
    description: Argument.

Returns:
    Return value.
"""
        self._tool_id = tool_id
        self._name = name
        self._description = description
        self.parameters: List[ToolParameter] = []
        self._execution_count = 0

    @property
    def tool_id(self) -> str:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return self._tool_id or ""

    @property
    def name(self) -> str:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return self._name or ""

    @property
    def description(self) -> str:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return self._description or ""

    @property
    def schema(self) -> Dict[str, Any]:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if hasattr(self, 'parameters') and self.parameters:
            properties = {}
            required = []
            for p in self.parameters:
                properties[p.name] = {'type': p.type, 'description': p.description}
                if p.required:
                    required.append(p.name)
            return {'type': 'object', 'properties': properties, 'required': required}
        return {}

    def add_parameter(self, param: ToolParameter) -> None:
        """Auto-generated docstring.

Args:
    param: Argument.

Returns:
    Return value.
"""
        self.parameters.append(param)

    def get_info(self) -> Dict[str, Any]:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        return {'tool_id': self.tool_id, 'name': self.name, 'description': self.description, 'parameters': [{'name': p.name, 'type': p.type, 'description': p.description, 'required': p.required, 'default': p.default} for p in self.parameters], 'execution_count': self._execution_count}

    def validate_parameters(self, **kwargs) -> bool:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if not hasattr(self, 'parameters') or not self.parameters:
            return True
        required_params = {p.name for p in self.parameters if p.required}
        provided_params = set(kwargs.keys())
        if not required_params.issubset(provided_params):
            missing = required_params - provided_params
            logger.error(f'Missing required parameters: {missing}')
            return False
        return True

    def __call__(self, *args, **kwargs) -> ToolResult:
        """Invoke the tool, adapting kwargs to whichever calling convention
        ``execute`` uses (a single ``params``/``arguments`` dict, or explicit
        keyword arguments), and bridging async ``execute`` implementations
        onto a synchronous return value.

        The single-dict-parameter adaptation is determined purely from the
        ``execute`` signature and applies whether ``execute`` is sync or
        async, so callers do not need to know a tool's implementation style.
        """
        self._execution_count += 1
        if hasattr(self, 'parameters') and self.parameters:
            if not self.validate_parameters(**kwargs):
                return ToolResult(success=False, output=None, error='Invalid parameters')
        import inspect
        import asyncio
        sig = inspect.signature(self.execute)
        params_list = list(sig.parameters.values())
        single_dict_param = len(params_list) == 1 and (params_list[0].annotation == Dict[str, Any] or params_list[0].name in ('params', 'arguments', 'kwargs'))
        if single_dict_param:
            execute_args = args if args else (kwargs,)
            execute_kwargs = {}
        else:
            execute_args = args
            execute_kwargs = kwargs
        result = self.execute(*execute_args, **execute_kwargs)
        if not asyncio.iscoroutine(result):
            return result
        from axiom.core.async_bridge import run_sync
        return run_sync(result)

    def execute(self, *args, **kwargs) -> ToolResult:  # type: ignore[override]
        """Execute the tool implementation."""
        raise NotImplementedError(f'{self.__class__.__name__} must implement execute()')

