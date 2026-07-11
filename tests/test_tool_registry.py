"""Tests for the type-safe ToolRegistry subsystem."""

import pytest

from axiom.tool_registry import ToolRegistry, ToolRegistryError
from axiom.tools import BaseTool, EchoTool, PythonExecTool, ShellTool, ToolResult


class NotATool:
    """A plain object that does not extend BaseTool."""


def test_register_uses_tool_id_as_key():
    registry = ToolRegistry()
    tool = EchoTool()

    registry.register(tool)

    assert registry.get_tool("echo") is tool
    assert registry.list_tools() == {"echo": tool}


def test_register_tool_with_explicit_id():
    registry = ToolRegistry()
    tool = EchoTool()

    registry.register_tool("custom_echo", tool)

    assert registry.get_tool("custom_echo") is tool
    assert "echo" not in registry.list_tools()


def test_duplicate_registration_raises():
    registry = ToolRegistry()
    registry.register(EchoTool())

    with pytest.raises(ToolRegistryError, match="already registered"):
        registry.register(EchoTool())


def test_register_rejects_non_basetool_instances():
    registry = ToolRegistry()

    with pytest.raises(ToolRegistryError, match="BaseTool"):
        registry.register_tool("bogus", NotATool())


def test_register_rejects_empty_tool_id():
    registry = ToolRegistry()

    with pytest.raises(ToolRegistryError, match="tool_id"):
        registry.register_tool("", EchoTool())


def test_unregister_returns_true_when_present_and_false_otherwise():
    registry = ToolRegistry()
    registry.register(EchoTool())

    assert registry.unregister_tool("echo") is True
    assert registry.unregister_tool("echo") is False
    assert registry.get_tool("echo") is None


def test_list_tools_returns_independent_copy():
    registry = ToolRegistry()
    registry.register(EchoTool())

    snapshot = registry.list_tools()
    snapshot["intruder"] = "not-a-real-tool"

    assert "intruder" not in registry.list_tools()


def test_contains_and_len():
    registry = ToolRegistry()
    assert len(registry) == 0
    assert "echo" not in registry

    registry.register(EchoTool())

    assert len(registry) == 1
    assert "echo" in registry


def test_get_schemas_produces_openai_function_calling_format():
    registry = ToolRegistry()
    registry.register(ShellTool())

    schemas = registry.get_schemas()

    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "shell"
    assert "command" in schema["function"]["parameters"]["properties"]


def test_execute_dict_parameter_family_tool():
    """EchoTool.execute() is async and takes a single params dict."""
    registry = ToolRegistry()
    registry.register(EchoTool())

    result = registry.execute("echo", text="hello world")

    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.output == "hello world"


def test_execute_legacy_keyword_argument_family_tool():
    """PythonExecTool.execute() is sync and takes explicit keyword args.

    Calling ``tool.execute({"code": ...})`` directly (as a naive dict-based
    dispatcher would) is broken for this family because the dict would bind
    to the ``code`` positional parameter itself. ToolRegistry.execute() must
    route through BaseTool.__call__ so both families work correctly.
    """
    registry = ToolRegistry()
    registry.register(PythonExecTool())

    result = registry.execute("python_exec", code="print('hi')")

    assert result.success is True
    assert "hi" in result.output["stdout"]


def test_execute_missing_tool_returns_failed_result_without_raising():
    registry = ToolRegistry()

    result = registry.execute("does_not_exist", text="x")

    assert result.success is False
    assert "not found" in result.error.lower()


def test_execute_captures_tool_exceptions_as_failed_result():
    class ExplodingTool(BaseTool):
        @property
        def tool_id(self) -> str:
            return "exploding"

        @property
        def name(self) -> str:
            return "exploding"

        @property
        def description(self) -> str:
            return "Always raises."

        def execute(self, *args, **kwargs) -> ToolResult:
            raise RuntimeError("boom")

    registry = ToolRegistry()
    registry.register(ExplodingTool())

    result = registry.execute("exploding")

    assert result.success is False
    assert "boom" in result.error
