"""Test suite for Autonomous Tool Crafting Resilience:
Installation Rollback & Capability Memory Reconciliation.

Verifies:
1. New tool reload failure rolls back file, runtime schema, and capability memory.
2. Update reload failure restores previous working code, runtime schema, and capability memory.
3. Manual file deletion triggers capability reconciliation in MemoryStore without reviving deleted tools.
4. Normal deletion through ToolManager remains correct.
5. Repeated index/restart runs do not revive deleted tools and only reconcile tool capabilities.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from axiom.core.plugins import get_tool_schemas, reload_plugin
from axiom.db.memory import MemoryStore
from axiom.memory.capability_indexer import (
    index_tool_capabilities,
    reconcile_tool_capabilities,
)
from axiom.tools.tool_crafter import craft_tool
from axiom.tools.tool_manager import (
    ToolManager,
    delete_dynamic_tool,
    update_dynamic_tool,
)

SAMPLE_TOOL_V1 = """
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "resilient_adder",
        "description": "Adds numbers v1.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number"}
            },
            "required": ["n"]
        }
    }
}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "➕ Adding numbers v1..."

async def execute(n: int = 0, **kwargs) -> str:
    return str(n + 10)
"""

SAMPLE_TOOL_V2 = """
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "resilient_adder",
        "description": "Adds numbers v2 updated.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number"}
            },
            "required": ["n"]
        }
    }
}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "➕ Adding numbers v2..."

async def execute(n: int = 0, **kwargs) -> str:
    return str(n + 20)
"""


class TestToolCraftingResilience(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_resilience.db")
        self.tools_dir = Path(self.temp_dir.name) / "tools.d"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(db_path=self.db_path)
        os.environ["AXIOM_MEMORY_DB"] = self.db_path
        os.environ["AXIOM_TOOLS_DIR"] = str(self.tools_dir)

    def tearDown(self):
        self.temp_dir.cleanup()
        if "AXIOM_MEMORY_DB" in os.environ:
            del os.environ["AXIOM_MEMORY_DB"]
        if "AXIOM_TOOLS_DIR" in os.environ:
            del os.environ["AXIOM_TOOLS_DIR"]

    async def test_new_tool_reload_failure_rolls_back_file_and_runtime(self):
        """Simulate a new tool where reload_plugin() fails, verifying rollback."""
        tool_file = self.tools_dir / "failed_new_tool.py"

        with patch("axiom.tools.tool_crafter.reload_plugin", side_effect=RuntimeError("Simulated reload failure")):
            res = await craft_tool(
                name="failed_new_tool",
                code=SAMPLE_TOOL_V1.replace("resilient_adder", "failed_new_tool"),
                test_params={"n": 5},
                tools_dir=self.tools_dir,
                db_path=self.db_path,
            )

        # 1. Assert craft_tool returned failure
        self.assertFalse(res.success)
        self.assertIn("Installation failed during reload", res.error)

        # 2. Assert .py file was removed from tools.d
        self.assertFalse(tool_file.exists())

        # 3. Assert tool is not present in runtime schemas
        schemas = get_tool_schemas(0)
        schema_names = {s.get("function", {}).get("name") or s.get("name") for s in schemas}
        self.assertNotIn("failed_new_tool", schema_names)

        # 4. Assert no active capability record exists in MemoryStore
        active_cap = self.store.get_by_key("tool.failed_new_tool")
        self.assertIsNone(active_cap)

    async def test_update_reload_failure_restores_previous_working_version(self):
        """Install v1, attempt v2 update where reload fails, verify restoration of v1."""
        # Step 1: Install valid v1
        craft_res = await craft_tool(
            name="resilient_adder",
            code=SAMPLE_TOOL_V1,
            test_params={"n": 5},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertTrue(craft_res.success)

        tool_file = self.tools_dir / "resilient_adder.py"
        self.assertTrue(tool_file.exists())
        self.assertIn("Adds numbers v1.", tool_file.read_text(encoding="utf-8"))

        cap_v1 = self.store.get_by_key("tool.resilient_adder")
        self.assertIsNotNone(cap_v1)
        self.assertIn("Adds numbers v1.", cap_v1["content"])

        # Step 2: Attempt update to v2 with reload failure on first reload attempt
        real_reload = reload_plugin
        call_count = 0

        def failing_reload(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated reload error for v2")
            return real_reload(path)

        with patch("axiom.tools.tool_manager.reload_plugin", side_effect=failing_reload):
            up_res = await update_dynamic_tool(
                name="resilient_adder",
                code=SAMPLE_TOOL_V2,
                test_params={"n": 5},
                tools_dir=self.tools_dir,
                db_path=self.db_path,
            )

        # Assert update returned failure
        self.assertFalse(up_res.success)
        self.assertIn("Update failed during reload", up_res.error)

        # Assert tool file in tools.d contains restored v1 code
        current_code = tool_file.read_text(encoding="utf-8")
        self.assertIn("Adds numbers v1.", current_code)
        self.assertNotIn("Adds numbers v2 updated.", current_code)

        # Assert runtime schema reflects restored v1 description
        schemas = get_tool_schemas(0)
        matching = [s for s in schemas if (s.get("function", {}).get("name") or s.get("name")) == "resilient_adder"]
        self.assertEqual(len(matching), 1)
        self.assertIn("Adds numbers v1.", matching[0]["function"]["description"])

        # Assert MemoryStore active capability reflects v1
        cap_restored = self.store.get_by_key("tool.resilient_adder")
        self.assertIsNotNone(cap_restored)
        self.assertIn("Adds numbers v1.", cap_restored["content"])

    async def test_manual_deletion_reconciliation(self):
        """Unlink tool file directly from disk; verify index_tool_capabilities reconciles MemoryStore."""
        # 1. Install dynamic tool
        res = await craft_tool(
            name="manual_del_tool",
            code=SAMPLE_TOOL_V1.replace("resilient_adder", "manual_del_tool"),
            test_params={"n": 1},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertTrue(res.success)

        # Verify active capability exists
        cap = self.store.get_by_key("tool.manual_del_tool")
        self.assertIsNotNone(cap)

        # Also store non-capability memories to verify they are never touched
        pref_id = self.store.store(content="Dark theme preferred", category="preference", key="ui.theme")
        home_id = self.store.store(content="192.168.1.1 gateway", category="homelab", key="network.gw")

        # 2. Manually unlink the .py file without calling ToolManager
        tool_file = self.tools_dir / "manual_del_tool.py"
        self.assertTrue(tool_file.exists())
        tool_file.unlink()
        self.assertFalse(tool_file.exists())

        # 3. Run reconciliation / index_tool_capabilities
        index_tool_capabilities(store=self.store, tools_dir=self.tools_dir)

        # 4. Assert capability record in MemoryStore is marked inactive
        self.assertIsNone(self.store.get_by_key("tool.manual_del_tool"))

        with self.store._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM memories WHERE id = ?", (cap["id"],)).fetchone()
            self.assertEqual(row["is_active"], 0)

        # Assert it does not appear in active memory search
        search_res = self.store.search("manual_del_tool", category="capability")
        self.assertEqual(len(search_res), 0)

        # 5. Assert user preferences and homelab records were untouched
        self.assertIsNotNone(self.store.get_by_key("ui.theme"))
        self.assertIsNotNone(self.store.get_by_key("network.gw"))

    async def test_normal_deletion_through_tool_manager_remains_correct(self):
        """Verify normal deletion via ToolManager.delete_tool removes file and cleans runtime and memory."""
        res = await craft_tool(
            name="managed_del_tool",
            code=SAMPLE_TOOL_V1.replace("resilient_adder", "managed_del_tool"),
            test_params={"n": 1},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        self.assertTrue(res.success)

        del_res = ToolManager.delete_tool("managed_del_tool", tools_dir=self.tools_dir, db_path=self.db_path)
        self.assertTrue(del_res.success)

        self.assertFalse((self.tools_dir / "managed_del_tool.py").exists())
        schemas = get_tool_schemas(0)
        self.assertNotIn("managed_del_tool", [s.get("function", {}).get("name") or s.get("name") for s in schemas])
        self.assertIsNone(self.store.get_by_key("tool.managed_del_tool"))

    async def test_restart_reindex_does_not_revive_deleted_tools(self):
        """Verify running index_tool_capabilities multiple times never revives deleted tools."""
        # Install and delete a tool
        await craft_tool(
            name="revive_check_tool",
            code=SAMPLE_TOOL_V1.replace("resilient_adder", "revive_check_tool"),
            test_params={"n": 1},
            tools_dir=self.tools_dir,
            db_path=self.db_path,
        )
        delete_dynamic_tool("revive_check_tool", tools_dir=self.tools_dir, db_path=self.db_path)

        # Re-index multiple times
        for _ in range(3):
            index_tool_capabilities(store=self.store, tools_dir=self.tools_dir)

        # Verify tool remains inactive and not revived
        self.assertIsNone(self.store.get_by_key("tool.revive_check_tool"))
        search_res = self.store.search("revive_check_tool", category="capability")
        self.assertEqual(len(search_res), 0)


if __name__ == "__main__":
    unittest.main()
