"""Tests targeting the highest-value coverage gaps identified by audit.

Covers:
- BaseTool.__call__ async bridge path (tools.py:122-163)
- ToolResult.to_dict serialization (tools.py:31-39)
- BaseTool parameter validation and schema generation (tools.py:74-120)
- Core Registry thread safety (core/registry.py)
- SemanticIndex cosine similarity and store/search (memory/semantic.py)
- ExecutionContext lifecycle (core/context.py)
"""

import asyncio
import threading
import math
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict

from axiom.tools import BaseTool, ToolResult, ToolParameter
from axiom.core.registry import Registry
from axiom.memory.semantic import SemanticIndex, _cosine_similarity
from axiom.core.context import ExecutionContext


# ── Helpers ───────────────────────────────────────────────────────────────────

class SyncEchoTool(BaseTool):
    """Concrete sync tool for testing BaseTool.__call__."""

    @property
    def tool_id(self) -> str:
        return "sync_echo"

    @property
    def name(self) -> str:
        return "sync_echo"

    @property
    def description(self) -> str:
        return "Sync echo."

    def execute(self, params: Dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=params.get("text", ""))


class AsyncEchoTool(BaseTool):
    """Concrete async tool for testing the bridge path in BaseTool.__call__."""

    @property
    def tool_id(self) -> str:
        return "async_echo"

    @property
    def name(self) -> str:
        return "async_echo"

    @property
    def description(self) -> str:
        return "Async echo."

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        await asyncio.sleep(0)
        return ToolResult(success=True, output=params.get("text", ""))


class RequiredParamTool(BaseTool):
    """Tool with required parameters for validation testing."""

    @property
    def tool_id(self) -> str:
        return "req"

    @property
    def name(self) -> str:
        return "req"

    @property
    def description(self) -> str:
        return "Requires name."

    def __init__(self):
        super().__init__()
        self.add_parameter(ToolParameter("name", "string", "A name", required=True))
        self.add_parameter(ToolParameter("color", "string", "A color", required=False, default="blue"))

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output=kwargs)


class NoParamTool(BaseTool):
    """Tool with no parameters."""

    @property
    def tool_id(self) -> str:
        return "noparam"

    @property
    def name(self) -> str:
        return "noparam"

    @property
    def description(self) -> str:
        return "No params."

    def execute(self) -> ToolResult:
        return ToolResult(success=True, output="ok")


# ── BaseTool.__call__ async bridge path ───────────────────────────────────────

class TestBaseToolCallBridge:
    def test_sync_execute_called_synchronously(self):
        tool = SyncEchoTool()
        result = tool(text="hello")
        assert result.success is True
        assert result.output == "hello"

    def test_async_execute_routed_through_bridge(self):
        tool = AsyncEchoTool()
        result = tool(text="bridged")
        assert result.success is True
        assert result.output == "bridged"

    def test_async_execute_exception_propagated(self):
        class FailingAsyncTool(BaseTool):
            @property
            def tool_id(self): return "fail"
            @property
            def name(self): return "fail"
            @property
            def description(self): return "fail"

            async def execute(self, params: Dict[str, Any]) -> ToolResult:
                raise ValueError("async boom")

        tool = FailingAsyncTool()
        with pytest.raises(ValueError, match="async boom"):
            tool(params={})

    def test_execution_count_increments(self):
        tool = SyncEchoTool()
        assert tool._execution_count == 0
        tool(text="a")
        assert tool._execution_count == 1
        tool(text="b")
        assert tool._execution_count == 2


# ── ToolResult.to_dict ────────────────────────────────────────────────────────

class TestToolResultToDict:
    def test_to_dict_success(self):
        r = ToolResult(success=True, output="done", metadata={"k": 1})
        d = r.to_dict(tool="my_tool", arguments={"x": 1})
        assert d["tool"] == "my_tool"
        assert d["arguments"] == {"x": 1}
        assert d["result"]["output"] == "done"
        assert d["result"]["metadata"] == {"k": 1}
        assert d["success"] is True

    def test_to_dict_failure(self):
        r = ToolResult(success=False, error="oops")
        d = r.to_dict(tool="t")
        assert d["success"] is False
        assert d["result"]["error"] == "oops"
        assert d["result"]["output"] is None

    def test_to_dict_defaults(self):
        r = ToolResult(success=True, output=42)
        d = r.to_dict()
        assert d["tool"] == ""
        assert d["arguments"] == {}


# ── BaseTool parameter validation & schema ────────────────────────────────────

class TestParameterValidation:
    def test_validate_no_parameters_always_passes(self):
        tool = NoParamTool()
        assert tool.validate_parameters() is True

    def test_validate_required_present(self):
        tool = RequiredParamTool()
        assert tool.validate_parameters(name="Alice") is True

    def test_validate_required_missing(self):
        tool = RequiredParamTool()
        assert tool.validate_parameters() is False

    def test_validate_optional_not_required(self):
        tool = RequiredParamTool()
        assert tool.validate_parameters(name="Bob") is True

    def test_schema_with_parameters(self):
        tool = RequiredParamTool()
        s = tool.schema
        assert s["type"] == "object"
        assert "name" in s["properties"]
        assert "name" in s["required"]
        assert "color" in s["properties"]
        assert "color" not in s["required"]

    def test_schema_without_parameters(self):
        tool = NoParamTool()
        assert tool.schema == {}

    def test_get_info_includes_execution_count(self):
        tool = SyncEchoTool()
        info = tool.get_info()
        assert info["tool_id"] == "sync_echo"
        assert info["execution_count"] == 0
        tool(text="x")
        info = tool.get_info()
        assert info["execution_count"] == 1

    def test_add_blocklist_pattern_empty_raises(self):
        from axiom.tools import ShellTool
        t = ShellTool(blocklist=[])
        with pytest.raises(ValueError, match="empty"):
            t.add_blocklist_pattern("  ")

    def test_remove_blocklist_nonexistent_noop(self):
        from axiom.tools import ShellTool
        t = ShellTool(blocklist=["a"])
        t.remove_blocklist_pattern("nonexistent")
        assert "a" in t._blocklist


# ── Core Registry thread safety ───────────────────────────────────────────────

class TestRegistryThreadSafety:
    def test_register_and_get_tool(self):
        reg = Registry()
        reg.register_tool("t1", "tool_obj")
        assert reg.get_tool("t1") == "tool_obj"

    def test_unregister_tool(self):
        reg = Registry()
        reg.register_tool("t1", "obj")
        reg.unregister_tool("t1")
        assert reg.get_tool("t1") is None

    def test_unregister_nonexistent_noop(self):
        reg = Registry()
        reg.unregister_tool("nonexistent")

    def test_has_tool(self):
        reg = Registry()
        assert reg.has_tool("t1") is False
        reg.register_tool("t1", "obj")
        assert reg.has_tool("t1") is True

    def test_list_tools_returns_copy(self):
        reg = Registry()
        reg.register_tool("t1", "obj")
        tools = reg.list_tools()
        tools["t2"] = "injected"
        assert reg.get_tool("t2") is None

    def test_register_and_get_agent(self):
        reg = Registry()
        reg.register_agent("a1", "agent_obj")
        assert reg.get_agent("a1") == "agent_obj"
        assert "a1" in reg.list_agents()

    def test_unregister_agent(self):
        reg = Registry()
        reg.register_agent("a1", "obj")
        reg.unregister_agent("a1")
        assert reg.get_agent("a1") is None

    def test_register_and_get_plugin(self):
        reg = Registry()
        reg.register_plugin("p1", "plugin_obj")
        assert reg.get_plugin("p1") == "plugin_obj"

    def test_unregister_plugin(self):
        reg = Registry()
        reg.register_plugin("p1", "obj")
        reg.unregister_plugin("p1")
        assert reg.get_plugin("p1") is None

    def test_register_and_get_handler(self):
        reg = Registry()
        reg.register_handler("h1", "handler_obj")
        assert reg.get_handler("h1") == "handler_obj"
        assert "h1" in reg.list_handlers()

    def test_list_handlers_returns_copy(self):
        reg = Registry()
        reg.register_handler("h1", "obj")
        handlers = reg.list_handlers()
        handlers["h2"] = "injected"
        assert reg.get_handler("h2") is None

    def test_clear_all(self):
        reg = Registry()
        reg.register_tool("t", "obj")
        reg.register_agent("a", "obj")
        reg.register_plugin("p", "obj")
        reg.register_handler("h", "obj")
        reg.clear_all()
        assert reg.list_tools() == {}
        assert reg.list_agents() == {}
        assert reg.list_plugins() == {}
        assert reg.list_handlers() == {}

    def test_concurrent_register_unregister(self):
        """Threads can register/unregister without corruption."""
        reg = Registry()
        errors = []

        def writer(prefix, n):
            try:
                for i in range(n):
                    key = f"{prefix}_{i}"
                    reg.register_tool(key, f"obj_{i}")
                for i in range(n):
                    key = f"{prefix}_{i}"
                    reg.unregister_tool(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(f"w{t}", 50)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        # All tools should have been unregistered
        assert reg.list_tools() == {}


# ── SemanticIndex ─────────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-9

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-9

    def test_different_lengths_returns_zero(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_empty_vectors_returns_zero(self):
        assert _cosine_similarity([], []) == 0.0

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestSemanticIndex:
    def test_has_provider_true(self):
        idx = SemanticIndex(provider=MagicMock())
        assert idx.has_provider is True

    def test_has_provider_false(self):
        idx = SemanticIndex()
        assert idx.has_provider is False

    def test_search_text_no_provider_returns_empty(self):
        idx = SemanticIndex()
        result = asyncio.run(idx.search_text(None, "query"))
        assert result == []

    def test_store_text_no_provider_returns_false(self):
        idx = SemanticIndex()
        result = asyncio.run(idx.store_text(None, "id1", "msg", "hello"))
        assert result is False

    def test_store_text_provider_failure_returns_false(self):
        provider = MagicMock()
        provider.embed.return_value = []
        idx = SemanticIndex(provider=provider)
        result = asyncio.run(idx.store_text(None, "id1", "msg", "hello"))
        assert result is False

    def test_store_and_search(self):
        """End-to-end: store embeddings, then find closest."""
        import aiosqlite

        provider = MagicMock()
        idx = SemanticIndex(provider=provider)

        async def run():
            async with aiosqlite.connect(":memory:") as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute(
                    "CREATE TABLE embeddings ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "owner_id TEXT, owner_type TEXT,"
                    "embedding_json TEXT, model TEXT, "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                )
                await conn.commit()

                await idx.store(conn, "doc1", "document", [1.0, 0.0, 0.0] + [0.0] * 765, model="test")
                await idx.store(conn, "doc2", "document", [0.0, 1.0, 0.0] + [0.0] * 765, model="test")

                results = await idx.search(conn, [0.9, 0.1, 0.0] + [0.0] * 765, owner_type="document", top_k=2)
                assert len(results) == 2
                assert results[0]["owner_id"] == "doc1"
                assert results[0]["similarity"] > results[1]["similarity"]

        asyncio.run(run())

    def test_search_filters_by_owner_type(self):
        import aiosqlite

        idx = SemanticIndex()
        idx._vector_store = None

        async def run():
            async with aiosqlite.connect(":memory:") as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute(
                    "CREATE TABLE embeddings ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "owner_id TEXT, owner_type TEXT,"
                    "embedding_json TEXT, model TEXT, "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                )
                await conn.execute(
                    f"INSERT INTO embeddings (owner_id, owner_type, embedding_json, model) VALUES ('m1', 'message', '{[1,0,0] + [0]*765}', '')"
                )
                await conn.execute(
                    f"INSERT INTO embeddings (owner_id, owner_type, embedding_json, model) VALUES ('d1', 'document', '{[1,0,0] + [0]*765}', '')"
                )
                await conn.commit()

                results = await idx.search(conn, [1.0, 0.0, 0.0] + [0.0] * 765, owner_type="message")
                assert len(results) == 1
                assert results[0]["owner_type"] == "message"

        asyncio.run(run())

    def test_search_empty_table(self):
        import aiosqlite

        idx = SemanticIndex()

        async def run():
            async with aiosqlite.connect(":memory:") as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute(
                    "CREATE TABLE embeddings ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "owner_id TEXT, owner_type TEXT,"
                    "embedding_json TEXT, model TEXT, "
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                )
                await conn.commit()

                results = await idx.search(conn, [1.0, 0.0] + [0.0] * 766)
                assert results == []

        asyncio.run(run())


# ── ExecutionContext ──────────────────────────────────────────────────────────

class TestExecutionContext:
    def test_default_context_id_is_unique(self):
        c1 = ExecutionContext()
        c2 = ExecutionContext()
        assert c1.context_id != c2.context_id

    def test_add_tool_result(self):
        ctx = ExecutionContext()
        ctx.add_tool_result("shell", {"output": "ok"})
        assert ctx.tool_results["shell"] == {"output": "ok"}

    def test_add_agent_output(self):
        ctx = ExecutionContext()
        ctx.add_agent_output("orchestrator", "done")
        assert ctx.agent_outputs["orchestrator"] == "done"

    def test_set_get_variable(self):
        ctx = ExecutionContext()
        ctx.set_variable("x", 42)
        assert ctx.get_variable("x") == 42
        assert ctx.get_variable("missing", default="d") == "d"

    def test_clear_results(self):
        ctx = ExecutionContext()
        ctx.add_tool_result("t", "r")
        ctx.add_agent_output("a", "o")
        ctx.clear_results()
        assert ctx.tool_results == {}
        assert ctx.agent_outputs == {}

    def test_to_dict_roundtrip_keys(self):
        ctx = ExecutionContext(user_input="hello")
        d = ctx.to_dict()
        assert d["user_input"] == "hello"
        assert d["context_id"] == ctx.context_id
        assert "tool_results" in d
        assert "agent_outputs" in d
        assert "variables" in d
        assert "metadata" in d
