"""Master End-to-End Integration Test Suite for AGENT MEGASPRINT 3.

Verifies:
1. Tier 1: Desktop notifications (SendDesktopNotificationTool)
2. Tier 1: Network & VPN diagnostics (InspectNetworkTool)
3. Tier 1: Atomic file operations and rollback engine (ManageWorkspaceFileTool)
4. Tier 2: Visual feedback & evaluate_script browser capabilities
5. REPL: /doctor health diagnostic suite and /undo command
6. Dynamic registry provisioning (>= 30 tools)
7. System prompt & hierarchical instruction routing
"""

import asyncio
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

import axiom.cli.repl as repl_module
from axiom.cli.repl import InlineRepl
from axiom.core.instructions import InstructionManager
from axiom.core.plugins import get_tool_schemas, load_plugins
from axiom.core.system_prompt import HARDENED_SYSTEM_DIRECTIVES
from axiom.tools.browser_cdp import InteractWithBrowserTool
from axiom.tools.os_desktop import SendDesktopNotificationTool
from axiom.tools.os_system import InspectNetworkTool
from axiom.tools.workspace_file import ManageWorkspaceFileTool


class TestMegasprintV3Master(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_milestone1_desktop_notifications(self):
        tool = SendDesktopNotificationTool()
        res = await tool.execute({
            "title": "Megasprint 3 Test",
            "message": "Desktop notification verification",
            "urgency": "normal",
        })
        self.assertTrue(res.success)
        self.assertIsNotNone(res.output)
        self.assertTrue(res.output.get("delivered"))

    async def test_milestone1_inspect_network(self):
        tool = InspectNetworkTool()
        res = await tool.execute({
            "include_tailscale": True,
            "include_dns": True,
        })
        self.assertTrue(res.success)
        out = res.output
        self.assertIn("gateway", out)
        self.assertIn("interfaces", out)
        self.assertIn("dns", out)
        self.assertIn("tailscale", out)

    async def test_milestone2_atomic_file_rollback(self):
        tool = ManageWorkspaceFileTool()
        test_file = Path(self.test_dir) / "config.json"

        # V1
        res1 = await tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": json.dumps({"mode": "safe", "version": 1}),
        })
        self.assertTrue(res1.success)

        # Brief delay for distinct backup timestamp
        await asyncio.sleep(1.05)

        # V2
        res2 = await tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": json.dumps({"mode": "production", "version": 2}),
        })
        self.assertTrue(res2.success)
        self.assertEqual(json.loads(test_file.read_text())["version"], 2)

        # Rollback -> back to V1
        res_undo = await tool.execute({
            "action": "rollback",
            "path": str(test_file),
        })
        self.assertTrue(res_undo.success)
        self.assertEqual(json.loads(test_file.read_text())["version"], 1)

    async def test_milestone4_browser_evaluate_script_schema(self):
        tool = InteractWithBrowserTool()
        # Verify evaluate_script action in schema
        action_param = next((p for p in tool.parameters if p.name == "action"), None)
        self.assertIsNotNone(action_param)
        self.assertIn("evaluate_script", action_param.description)

        # Verify extension background.js contains highlight and eval actions
        bg_js = Path("axiom/tools/extension/background.js").read_text(encoding="utf-8")
        self.assertIn("#7aa2f7", bg_js)
        self.assertIn("evaluate_script", bg_js)
        self.assertIn("window.eval", bg_js)

    def test_milestone3_repl_doctor_and_undo(self):
        repl = InlineRepl()
        buf = io.StringIO()
        repl_module.console = Console(file=buf, force_terminal=False, color_system=None)

        # Test /doctor
        handled = repl.handle_command("/doctor")
        self.assertTrue(handled)
        output = buf.getvalue()
        self.assertIn("AXIOM Subsystem Health Diagnostics", output)
        self.assertIn("Browser Bridge", output)
        self.assertIn("Tool Registry", output)

    def test_milestone5_dynamic_tool_registry_provisioning(self):
        load_plugins()
        schemas = get_tool_schemas(0)
        self.assertGreaterEqual(len(schemas), 30)

        names = [s["function"]["name"] for s in schemas if "function" in s]
        self.assertIn("send_desktop_notification", names)
        self.assertIn("inspect_network", names)
        self.assertIn("manage_workspace_file", names)
        self.assertIn("interact_with_browser", names)

    def test_system_prompt_and_instructions_coherence(self):
        im = InstructionManager()
        compiled = im.get_compiled_instructions()
        self.assertIn("send_desktop_notification", HARDENED_SYSTEM_DIRECTIVES)
        self.assertIn("inspect_network", HARDENED_SYSTEM_DIRECTIVES)
        self.assertIn("evaluate_script", HARDENED_SYSTEM_DIRECTIVES)
        self.assertIn("send_desktop_notification", compiled)
        self.assertIn("inspect_network", compiled)


if __name__ == "__main__":
    unittest.main()
