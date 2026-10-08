"""Unit and integration test suite for Phase 2:
Autonomous Tool Creation Engine (create_tool & craft_tool).

Verifies:
1. Successful tool creation, validation, atomic write, hot-reload, and capability registration.
2. Syntax error rejection: malformed code aborted before writing, tools.d remains untouched.
3. Privilege escalation rejection: candidate tools with REQUIRED_RING = 0 are rejected.
4. Runtime error rejection in staging: code raising errors during dry-run is aborted and not registered.
5. Duplicate capability prevention: rejects duplicate tool names or identical semantic descriptions.
6. Execution of create_tool.py wrapper tool.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from axiom.db.memory import MemoryStore
from axiom.tools.tool_crafter import craft_tool
from axiom.core.plugins import get_tool_schemas, load_plugins


VALID_MOCK_TOOL = '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rot13_cipher",
        "description": "Encodes text using the rot13 substitution cipher.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to encode"}
            },
            "required": ["text"]
        }
    }
}
REQUIRED_RING = 1
TIER = 1
TUI_HINT = "🔄 Encoding ROT13..."

async def execute(text: str = "", **kwargs) -> str:
    import codecs
    return codecs.encode(text, "rot_13")
'''


class TestCreateToolP2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test_create_tool.db")
        self.tools_dir = Path(self.temp_dir.name) / "tools.d"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(db_path=self.db_path)
        os.environ["AXIOM_MEMORY_DB"] = self.db_path

    def tearDown(self):
        self.temp_dir.cleanup()
        if "AXIOM_MEMORY_DB" in os.environ:
            del os.environ["AXIOM_MEMORY_DB"]

    async def test_1_successful_tool_creation_and_registration(self):
        """Verify craft_tool validates, writes, hot-reloads, and registers new tool."""
        res = await craft_tool(
            name="rot13_cipher",
            code=VALID_MOCK_TOOL,
            test_params={"text": "hello"},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        self.assertTrue(res.success, f"craft_tool failed: {res.error}")
        self.assertEqual(res.output["tool_name"], "rot13_cipher")
        self.assertEqual(res.output["status"], "installed_and_reloaded")
        self.assertEqual(res.output["ring"], 1)

        # Check file was written to tools.d
        tool_file = self.tools_dir / "rot13_cipher.py"
        self.assertTrue(tool_file.exists())

        # Check capability was indexed in MemoryStore
        cap = self.store.get_by_key("tool.rot13_cipher")
        self.assertIsNotNone(cap)
        self.assertEqual(cap["category"], "capability")
        self.assertIn("rot13_cipher", cap["content"])

    async def test_2_syntax_error_rejection(self):
        """Verify malformed Python code is rejected without touching tools.d."""
        bad_code = "def broken_syntax(:\n    pass\n"
        res = await craft_tool(
            name="bad_syntax_tool",
            code=bad_code,
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        self.assertFalse(res.success)
        self.assertIn("Validation failed: Syntax error", res.error)

        # File must not exist
        self.assertFalse((self.tools_dir / "bad_syntax_tool.py").exists())
        self.assertIsNone(self.store.get_by_key("tool.bad_syntax_tool"))

    async def test_3_privilege_escalation_rejection(self):
        """Verify tools requesting REQUIRED_RING = 0 are rejected."""
        ring0_code = '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "escalation_tool",
        "description": "Attempts to claim root ring 0.",
        "parameters": {"type": "object", "properties": {}}
    }
}
REQUIRED_RING = 0
TIER = 1
TUI_HINT = "💥 Escalating..."

async def execute(**kwargs) -> str:
    return "root"
'''
        res = await craft_tool(
            name="escalation_tool",
            code=ring0_code,
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        self.assertFalse(res.success)
        self.assertIn("Privilege escalation rejected", res.error)
        self.assertIn("REQUIRED_RING = 0", res.error)
        self.assertFalse((self.tools_dir / "escalation_tool.py").exists())

    async def test_4_staging_runtime_exception_rejection(self):
        """Verify tool that throws runtime error during dry-run is rejected."""
        crashing_code = '''
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crashing_tool",
        "description": "Crashes on invocation.",
        "parameters": {"type": "object", "properties": {}}
    }
}
REQUIRED_RING = 2
TIER = 1
TUI_HINT = "💥 Crashing..."

async def execute(**kwargs) -> str:
    raise ZeroDivisionError("division by zero in execute()")
'''
        res = await craft_tool(
            name="crashing_tool",
            code=crashing_code,
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )

        self.assertFalse(res.success)
        self.assertIn("Validation failed", res.error)
        self.assertIn("division by zero", res.error)
        self.assertFalse((self.tools_dir / "crashing_tool.py").exists())

    async def test_5_duplicate_capability_prevention(self):
        """Verify craft_tool rejects duplicate tool name and duplicate purpose."""
        # 1. Install first tool
        res1 = await craft_tool(
            name="rot13_cipher",
            code=VALID_MOCK_TOOL,
            test_params={"text": "hello"},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )
        self.assertTrue(res1.success)

        # 2. Duplicate name
        res_dup_name = await craft_tool(
            name="rot13_cipher",
            code=VALID_MOCK_TOOL,
            test_params={"text": "hello"},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )
        self.assertFalse(res_dup_name.success)
        self.assertIn("Duplicate capability rejected", res_dup_name.error)
        self.assertIn("already exists", res_dup_name.error)

        # 3. Duplicate description with different name
        dup_desc_code = VALID_MOCK_TOOL.replace('"rot13_cipher"', '"rot13_alt"')
        res_dup_desc = await craft_tool(
            name="rot13_alt",
            code=dup_desc_code,
            test_params={"text": "hello"},
            db_path=self.db_path,
            tools_dir=self.tools_dir,
        )
        self.assertFalse(res_dup_desc.success)
        self.assertIn("Duplicate capability rejected", res_dup_desc.error)

    async def test_6_create_tool_wrapper_execution(self):
        """Verify ~/.config/axiom/tools.d/create_tool.py executes and returns JSON envelope."""
        from importlib.machinery import SourceFileLoader
        tool_path = Path.home() / ".config" / "axiom" / "tools.d" / "create_tool.py"
        self.assertTrue(tool_path.exists())

        mod = SourceFileLoader("create_tool_test_mod", str(tool_path)).load_module()

        # Execute create_tool with invalid code to verify JSON envelope error output
        out_str = await mod.execute(name="invalid_tool", code="def broken(")
        out = json.loads(out_str)

        self.assertFalse(out["success"])
        self.assertIn("Validation failed", out["result"]["error"])


if __name__ == "__main__":
    unittest.main()
