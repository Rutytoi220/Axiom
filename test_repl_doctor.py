"""Test suite for REPL /doctor diagnostic health suite and /undo command."""

import asyncio
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

import axiom.cli.repl as repl_module
from axiom.cli.repl import InlineRepl
from axiom.tools.workspace_file import ManageWorkspaceFileTool


class TestReplDoctorAndUndo(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repl = InlineRepl()
        # Redirect repl console to capture output
        self.string_io = io.StringIO()
        repl_module.console = Console(file=self.string_io, force_terminal=False, color_system=None)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_repl_doctor_command(self):
        handled = self.repl.handle_command("/doctor")
        self.assertTrue(handled)
        output = self.string_io.getvalue()
        
        # Verify subsystem presence in output
        self.assertIn("AXIOM Subsystem Health Diagnostics", output)
        self.assertIn("Ollama Engine", output)
        self.assertIn("Compositor", output)
        self.assertIn("Clipboard", output)
        self.assertIn("Media (MPRIS)", output)
        self.assertIn("Browser Bridge", output)
        self.assertIn("Tool Registry", output)

    def test_repl_undo_with_explicit_path(self):
        test_file = Path(self.test_dir) / "doc.txt"
        tool = ManageWorkspaceFileTool()

        # Step 1: write initial
        asyncio.run(tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "Original Content",
        }))

        # Step 2: overwrite (creates backup)
        asyncio.run(tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "Modified Content",
        }))

        self.assertEqual(test_file.read_text(encoding="utf-8"), "Modified Content")

        # Step 3: Run /undo with explicit path
        handled = self.repl.handle_command(f"/undo {test_file}")
        self.assertTrue(handled)
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Original Content")
        output = self.string_io.getvalue()
        self.assertIn("Rollback Successful", output)

    def test_repl_undo_with_implicit_session_path(self):
        test_file = Path(self.test_dir) / "implicit_doc.txt"
        tool = ManageWorkspaceFileTool()

        asyncio.run(tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "Before Change",
        }))
        asyncio.run(tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "After Change",
        }))

        # Run /undo without path - should deduce implicit_doc.txt
        handled = self.repl.handle_command("/undo")
        self.assertTrue(handled)
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Before Change")
        output = self.string_io.getvalue()
        self.assertIn("Rollback Successful", output)


if __name__ == "__main__":
    unittest.main()
