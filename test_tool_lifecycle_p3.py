"""Unit and integration test suite for Phase 3:
Dynamic Tool Lifecycle Management & REPL Inspection.

Verifies:
1. Programmatic ToolManager listing dynamic tools with metadata.
2. Safe updating of dynamic tools: validation, atomic write, hot-reload, and capability superseding.
3. Malformed code rejection on update: existing tool file remains untouched.
4. Privilege escalation guard on update: candidate tools with REQUIRED_RING = 0 are rejected.
5. Tool deletion: removes file from tools.d, unregisters from runtime schemas, and soft-deletes in MemoryStore.
6. Protected tool defense: core built-ins (execute_command, create_tool, etc.) cannot be deleted or updated.
7. manage_tools.py dynamic tool actuator actions: list, update, delete.
8. REPL /tools and /tools remove <name> command handling.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from axiom.core.plugins import get_tool_schemas, load_plugins, unregister_plugin
from axiom.db.memory import MemoryStore
from axiom.tools.tool_crafter import craft_tool
from axiom.tools.tool_manager import (
    PROTECTED_TOOLS,
    ToolManager,
    delete_dynamic_tool,
    list_dynamic_tools,
    update_dynamic_tool,
)

SAMPLE_TOOL_V1 = """
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "sample_calc",
        "description": "Adds numbers v1.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number"},
                "b": {"type": "integer", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    }
}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "➕ Calculating v1..."

async def execute(a: int = 0, b: int = 0, **kwargs) -> str:
    return str(a + b)
"""

SAMPLE_TOOL_V2 = """
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "sample_calc",
        "description": "Adds numbers v2 with multiplier.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First number"},
                "b": {"type": "integer", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    }
}
REQUIRED_RING = 2
TIER = 1
TUI_HINT = "➕ Calculating v2..."

async def execute(a: int = 0, b: int = 0, **kwargs) -> str:
    return str((a + b) * 2)
"""


class TestToolLifecycleP3(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_lifecycle.db")
        self.tools_dir = Path(self.temp_dir.name) / "tools.d"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(db_path=self.db_path)
        os.environ["AXIOM_MEMORY_DB"] = self.db_path

    def tearDown(self):
        self.temp_dir.cleanup()
        if "AXIOM_MEMORY_DB" in os.environ:
            del os.environ["AXIOM_MEMORY_DB"]

    async def test_1_list_dynamic_tools(self):
        """Verify list_dynamic_tools extracts metadata accurately."""
        # Create a tool in tools_dir
        tool_file = self.tools_dir / "sample_calc.py"
        tool_file.write_text(SAMPLE_TOOL_V1, encoding="utf-8")

        tools = list_dynamic_tools(tools_dir=self.tools_dir)
        self.assertEqual(len(tools), 1)
        item = tools[0]
        self.assertEqual(item["name"], "sample_calc")
        self.assertEqual(item["description"], "Adds numbers v1.")
        self.assertEqual(item["tier"], 1)
        self.assertEqual(item["ring"], 1)
        self.assertFalse(item["is_protected"])

    async def test_2_update_dynamic_tool_success_and_supersede(self):
        """Verify update_dynamic_tool hot-reloads and supersedes capability in MemoryStore."""
        # Step 1: Craft v1
        craft_res = await craft_tool(
            name="sample_calc",
            code=SAMPLE_TOOL_V1,
            test_params={"a": 1, "b": 2},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )
        self.assertTrue(craft_res.success)

        # Initial capability check
        cap_v1 = self.store.get_by_key("tool.sample_calc")
        self.assertIsNotNone(cap_v1)
        self.assertIn("v1", cap_v1["content"])
        old_id = cap_v1["id"]

        # Step 2: Update to v2
        up_res = await update_dynamic_tool(
            name="sample_calc",
            code=SAMPLE_TOOL_V2,
            test_params={"a": 1, "b": 2},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertTrue(up_res.success, f"update failed: {up_res.error}")
        self.assertEqual(up_res.output["ring"], 2)

        # Verify file content on disk was updated
        tool_file = self.tools_dir / "sample_calc.py"
        self.assertIn("v2 with multiplier", tool_file.read_text(encoding="utf-8"))

        # Verify capability was superseded in MemoryStore
        cap_v2 = self.store.get_by_key("tool.sample_calc")
        self.assertIsNotNone(cap_v2)
        self.assertIn("v2 with multiplier", cap_v2["content"])
        self.assertNotEqual(cap_v2["id"], old_id)

        # Verify old capability entry is inactive
        with self.store._get_conn() as conn:
            row = conn.execute("SELECT is_active, superseded_by FROM memories WHERE id = ?", (old_id,)).fetchone()
            self.assertEqual(row["is_active"], 0)
            self.assertEqual(row["superseded_by"], cap_v2["id"])

    async def test_3_update_malformed_code_rejected(self):
        """Verify updating with invalid code leaves existing tool untouched."""
        # Craft v1
        await craft_tool(
            name="sample_calc",
            code=SAMPLE_TOOL_V1,
            test_params={"a": 1, "b": 2},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        bad_code = "def syntax_err(:\n    pass\n"
        up_res = await update_dynamic_tool(
            name="sample_calc",
            code=bad_code,
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertFalse(up_res.success)
        self.assertIn("Validation failed", up_res.error)

        # Existing file must remain untouched
        tool_file = self.tools_dir / "sample_calc.py"
        self.assertIn("Adds numbers v1.", tool_file.read_text(encoding="utf-8"))

    async def test_4_update_ring0_privilege_escalation_rejected(self):
        """Verify attempt to update dynamic tool to Ring 0 is rejected."""
        await craft_tool(
            name="sample_calc",
            code=SAMPLE_TOOL_V1,
            test_params={"a": 1, "b": 2},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        ring0_code = SAMPLE_TOOL_V1.replace("REQUIRED_RING = 1", "REQUIRED_RING = 0")
        up_res = await update_dynamic_tool(
            name="sample_calc",
            code=ring0_code,
            test_params={"a": 1, "b": 2},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertFalse(up_res.success)
        self.assertIn("Privilege escalation rejected", up_res.error)

    async def test_5_delete_dynamic_tool_and_soft_delete(self):
        """Verify delete_dynamic_tool deletes file, unregisters schema, and soft-deletes capability."""
        # Craft tool
        await craft_tool(
            name="sample_calc",
            code=SAMPLE_TOOL_V1,
            test_params={"a": 1, "b": 2},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        tool_file = self.tools_dir / "sample_calc.py"
        self.assertTrue(tool_file.exists())
        cap = self.store.get_by_key("tool.sample_calc")
        self.assertIsNotNone(cap)

        # Delete tool
        del_res = delete_dynamic_tool(
            name="sample_calc",
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertTrue(del_res.success, f"delete failed: {del_res.error}")

        # File is gone
        self.assertFalse(tool_file.exists())

        # Unregistered from schemas
        schemas = get_tool_schemas(0)
        tool_names = [s.get("function", {}).get("name") or s.get("name") for s in schemas]
        self.assertNotIn("sample_calc", tool_names)

        # Soft-deleted in MemoryStore (get_by_key returns None for inactive)
        self.assertIsNone(self.store.get_by_key("tool.sample_calc"))
        with self.store._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM memories WHERE id = ?", (cap["id"],)).fetchone()
            self.assertEqual(row["is_active"], 0)

    async def test_6_protected_tool_defense(self):
        """Verify core built-in tools cannot be deleted or updated."""
        for protected in ["execute_command", "create_tool", "manage_tools", "remember_fact"]:
            self.assertIn(protected, PROTECTED_TOOLS)

            # Deletion attempt fails
            del_res = delete_dynamic_tool(
                name=protected,
                tools_dir=self.tools_dir,
                db_path=self.db_path,
            )
            self.assertFalse(del_res.success)
            self.assertIn("Permission denied", del_res.error)

            # Update attempt fails
            up_res = await update_dynamic_tool(
                name=protected,
                code=SAMPLE_TOOL_V1,
                tools_dir=self.tools_dir,
                db_path=self.db_path,
            )
            self.assertFalse(up_res.success)
            self.assertIn("Permission denied", up_res.error)

    async def test_7_manage_tools_actuator(self):
        """Verify ~/.config/axiom/tools.d/manage_tools.py wrapper execution."""
        from importlib.util import module_from_spec, spec_from_file_location
        manage_path = Path.home() / ".config" / "axiom" / "tools.d" / "manage_tools.py"
        self.assertTrue(manage_path.exists())

        spec = spec_from_file_location("axiom.dynamic_tools.manage_tools", manage_path)
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 1. Action list
        out_list = await mod.execute(action="list")
        data_list = json.loads(out_list)
        self.assertTrue(data_list["success"])
        self.assertIn("tools", data_list["result"])

        # 2. Action delete protected tool
        out_del = await mod.execute(action="delete", name="execute_command")
        data_del = json.loads(out_del)
        self.assertFalse(data_del["success"])
        self.assertIn("Permission denied", data_del["error"])

        # 3. Action invalid action
        out_inv = await mod.execute(action="invalid_action")
        data_inv = json.loads(out_inv)
        self.assertFalse(data_inv["success"])

    async def test_8_repl_tools_command_integration(self):
        """Verify /tools and /tools remove <name> REPL slash command handling."""
        with patch("axiom.cli.repl.ensure_ollama_running"):
            from axiom.cli.repl import InlineRepl
            repl = InlineRepl(session_id="test_lifecycle_session")

            # Test /tools listing
            res = repl.handle_command("/tools")
            self.assertTrue(res)

            # Test /tools remove on protected tool (rejected gracefully)
            res_prot = repl.handle_command("/tools remove execute_command")
            self.assertTrue(res_prot)

            # Test /tools remove on non-existent tool
            res_nonexistent = repl.handle_command("/tools remove non_existent_dynamic_tool_xyz")
            self.assertTrue(res_nonexistent)


if __name__ == "__main__":
    unittest.main()
