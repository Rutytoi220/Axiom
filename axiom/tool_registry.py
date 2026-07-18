"""Type-safe registry and invocation surface for AXIOM tools.

``axiom.tools`` defines two calling conventions for tool implementations:

- The dict-parameter family (``EchoTool``, ``ShellTool``, ``FileReadTool``,
  ``FileWriteTool``, ``SystemInfoTool``, ``FileTool``) whose ``execute``
  methods are ``async def execute(self, params: Dict[str, Any])``.
- The legacy keyword-argument family (``ShellCommandTool``, ``ReadFileTool``,
  ``WriteFileTool``, ``PythonExecTool``) whose ``execute`` methods are
  synchronous and accept explicit keyword parameters.

Callers that invoke ``tool.execute(...)`` directly must know which calling
convention a given tool uses. ``ToolRegistry`` removes that burden: it
validates registrations against the real :class:`axiom.tools.BaseTool`,
tracks tools by their ``tool_id``, generates OpenAI-compatible
function-calling schemas for LLM tool-calling loops, and exposes a single
``execute()`` entry point that works for both tool families by delegating to
``BaseTool.__call__`` (which already performs the signature-based dispatch
and sync/async bridging).

``ToolRegistry`` acts as a specialized View/Adapter over
``axiom.core.registry.Registry``.  When a ``core_registry`` is injected,
all storage operations delegate to it so that tools registered through
the Engine's registry are immediately visible through this adapter, and
vice-versa.  When no ``core_registry`` is provided, an isolated instance
is created for backwards compatibility.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from axiom.tools import BaseTool, ToolResult


class ToolRegistryError(Exception):
    """Raised when a tool registry operation is invalid."""


class ToolRegistry:
    """Thread-safe registry and invocation surface for AXIOM tools.

    When *core_registry* is provided, ``ToolRegistry`` delegates all
    storage to it and adds schema generation and safe execution on top.
    When omitted, an isolated ``core.registry.Registry`` is created so
    that existing ``ToolRegistry()`` call-sites continue to work.
    """

    def __init__(self, core_registry=None) -> None:
        from axiom.core.registry import Registry as CoreRegistry
        self._core_registry = core_registry or CoreRegistry()
        self._lock = threading.RLock()

    def register(self, tool: BaseTool) -> None:
        """Register ``tool`` using its own ``tool_id`` as the registry key."""
        if not isinstance(tool, BaseTool):
            raise ToolRegistryError(
                f"Component must be an instance of BaseTool, got {type(tool).__name__}"
            )
        tool_id = tool.tool_id
        if not tool_id:
            raise ToolRegistryError("Tool must define a non-empty tool_id")
        self.register_tool(tool_id, tool)

    def register_tool(self, tool_id: str, tool: BaseTool) -> None:
        """Register ``tool`` under an explicit ``tool_id``.

        Mirrors :meth:`axiom.core.registry.Registry.register_tool` so this
        registry can act as a drop-in replacement for existing tool-storage
        callers such as the CLI.
        """
        if not tool_id:
            raise ToolRegistryError("tool_id cannot be empty")
        if not isinstance(tool, BaseTool):
            raise ToolRegistryError(
                f"Component must be an instance of BaseTool, got {type(tool).__name__}"
            )
        with self._lock:
            if self._core_registry.has_tool(tool_id):
                raise ToolRegistryError(f"Tool '{tool_id}' is already registered")
            self._core_registry.register_tool(tool_id, tool)

    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a registered tool. Returns False if it was not registered."""
        with self._lock:
            if not self._core_registry.has_tool(tool_id):
                return False
            self._core_registry.unregister_tool(tool_id)
            return True

    def get_tool(self, tool_id: str) -> Optional[BaseTool]:
        """Return the tool registered under ``tool_id``, or ``None``."""
        return self._core_registry.get_tool(tool_id)

    def list_tools(self) -> Dict[str, BaseTool]:
        """Return a shallow copy of all registered tools keyed by ``tool_id``."""
        return self._core_registry.list_tools()

    def __contains__(self, tool_id: str) -> bool:
        return self._core_registry.has_tool(tool_id)

    def __len__(self) -> int:
        return len(self._core_registry.list_tools())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible function-calling schemas for every tool."""
        schemas: List[Dict[str, Any]] = []
        for tool_id, tool in self.list_tools().items():
            if not hasattr(tool, "description") or not hasattr(tool, "schema"):
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_id,
                        "description": tool.description or tool_id,
                        "parameters": tool.schema or {"type": "object", "properties": {}},
                    },
                }
            )
        return schemas

    def execute(self, tool_id: str, **arguments: Any) -> ToolResult:
        """Execute a registered tool safely, regardless of its calling convention.

        Delegates to :meth:`BaseTool.__call__`, which adapts to both the
        dict-parameter async tool family and the legacy synchronous
        keyword-argument family, and bridges async ``execute`` implementations
        onto a synchronous call. Errors raised by the tool are captured and
        returned as a failed :class:`ToolResult` rather than propagating.
        """
        tool = self.get_tool(tool_id)
        if tool is None:
            return ToolResult(success=False, error=f"Tool not found: {tool_id}")
        try:
            return tool(**arguments)
        except Exception as exc:  # Defensive: tools must not crash the registry.
            return ToolResult(success=False, error=str(exc))

    async def execute_async(self, tool_id: str, **arguments: Any) -> ToolResult:
        """Async version of execute.

        Directly invokes the tool's execute method and awaits it if it is
        asynchronous, bypassing the sync-bridging logic in __call__.
        """
        import asyncio
        import inspect
        from axiom.tools import ToolResult

        tool = self.get_tool(tool_id)
        if tool is None:
            return ToolResult(success=False, error=f"Tool not found: {tool_id}")

        try:
            # Handle parameter adaptation similar to BaseTool.__call__
            sig = inspect.signature(tool.execute)
            params_list = list(sig.parameters.values())
            single_dict_param = len(params_list) == 1 and (
                params_list[0].annotation == Dict[str, Any]
                or params_list[0].name in ("params", "arguments", "kwargs")
            )
            
            if single_dict_param:
                result = tool.execute(arguments)
            else:
                result = tool.execute(**arguments)

            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
