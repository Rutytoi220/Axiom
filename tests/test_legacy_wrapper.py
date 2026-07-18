"""Tests for axiom.legacy_wrapper — LegacyActionTool and create_legacy_tools."""

import pytest
from unittest.mock import patch, MagicMock

from axiom.legacy_wrapper import LegacyActionTool, create_legacy_tools
from axiom.tools import ToolResult


class TestLegacyActionTool:
    """Tests for the LegacyActionTool adapter."""

    def _make_handler(self, success=True, message="ok"):
        def handler(params):
            return success, message
        return handler

    def test_tool_id_prefix(self):
        tool = LegacyActionTool("search", self._make_handler())
        assert tool.tool_id == "legacy_search"

    def test_name_matches_action(self):
        tool = LegacyActionTool("go_to", self._make_handler())
        assert tool.name == "go_to"

    def test_description_contains_action_name(self):
        tool = LegacyActionTool("new_tab", self._make_handler())
        assert "new_tab" in tool.description

    def test_schema_has_params(self):
        tool = LegacyActionTool("search", self._make_handler())
        schema = tool.schema
        assert "params" in schema["properties"]
        assert schema["properties"]["params"]["type"] == "string"

    def test_execute_with_string_params(self):
        handler = self._make_handler(True, "searched")
        tool = LegacyActionTool("search", handler)
        result = tool.execute("query=test")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.output == "searched"

    def test_execute_with_dict_params(self):
        """Orchestrator passes a dict; wrapper must extract the string."""
        handler = self._make_handler(True, "navigated")
        tool = LegacyActionTool("go_to", handler)
        result = tool.execute({"params": "url=https://example.com"})
        assert result.success is True
        assert result.output == "navigated"

    def test_execute_with_dict_missing_params_key(self):
        handler = MagicMock(return_value=(True, "done"))
        tool = LegacyActionTool("go_to", handler)
        result = tool.execute({"wrong_key": "val"})
        assert result.success is True
        handler.assert_called_with("")

    def test_execute_with_non_string_params(self):
        handler = MagicMock(return_value=(True, "ok"))
        tool = LegacyActionTool("search", handler)
        result = tool.execute(12345)
        assert result.success is True
        handler.assert_called_with("12345")

    def test_execute_handler_returns_none_success(self):
        """Handler returning (None, msg) signals 'not handled'."""
        def handler(params):
            return None, "not handled"
        tool = LegacyActionTool("unknown", handler)
        result = tool.execute("x")
        assert result.success is False
        assert "not handled" in result.error

    def test_execute_handler_exception(self):
        def handler(params):
            raise RuntimeError("boom")
        tool = LegacyActionTool("bad", handler)
        result = tool.execute("x")
        assert result.success is False
        assert "boom" in result.error

    def test_execute_handler_returns_false(self):
        handler = self._make_handler(False, "failed")
        tool = LegacyActionTool("fail", handler)
        result = tool.execute("x")
        assert result.success is False
        assert result.output == "failed"


class TestCreateLegacyTools:
    """Tests for the create_legacy_tools factory."""

    def test_returns_empty_list_when_brain_missing(self):
        with patch.dict("sys.modules", {"brain": None, "brain.action_registry": None}):
            tools = create_legacy_tools()
        assert tools == []

    def test_returns_legacy_tools_from_registry(self):
        mock_registry = MagicMock()
        mock_registry.actions = {
            "search": lambda p: (True, "found"),
            "go_to": lambda p: (True, "went"),
        }
        mock_module = MagicMock()
        mock_module.get_action_registry.return_value = mock_registry

        with patch.dict("sys.modules", {"brain.action_registry": mock_module}):
            tools = create_legacy_tools()

        assert len(tools) == 2
        ids = {t.tool_id for t in tools}
        assert "legacy_search" in ids
        assert "legacy_go_to" in ids

    def test_factory_returns_empty_on_import_error(self):
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def block_brain_import(name, *args, **kwargs):
            if name == "brain.action_registry":
                raise ImportError("blocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=block_brain_import):
            tools = create_legacy_tools()
        assert tools == []
