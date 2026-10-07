"""Test suite for ManageWorkspaceFileTool rollback / undo engine."""

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from axiom.tools.workspace_file import BACKUP_DIR, ManageWorkspaceFileTool, get_last_modified_file


class TestWorkspaceUndo(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.tool = ManageWorkspaceFileTool()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_write_patch_rollback_workflow(self):
        test_file = Path(self.test_dir) / "test_doc.txt"

        # 1. First write (initial file)
        res1 = await self.tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "Initial Line 1\nInitial Line 2\n",
        })
        self.assertTrue(res1.success)
        self.assertEqual(get_last_modified_file(), test_file)

        # Brief sleep to ensure distinct timestamps for backup files
        await asyncio.sleep(1.05)

        # 2. Second write (should create backup of initial content)
        res2 = await self.tool.execute({
            "action": "write",
            "path": str(test_file),
            "content": "Modified Line 1\nModified Line 2\n",
        })
        self.assertTrue(res2.success)
        self.assertIsNotNone(res2.output.get("backup"))
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Modified Line 1\nModified Line 2\n")

        await asyncio.sleep(1.05)

        # 3. Patch operation (should create backup of modified content)
        res3 = await self.tool.execute({
            "action": "patch",
            "path": str(test_file),
            "search_text": "Modified Line 1",
            "replace_text": "Patched Line 1",
        })
        self.assertTrue(res3.success)
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Patched Line 1\nModified Line 2\n")

        # 4. Rollback should restore the latest backup (which had 'Modified Line 1\nModified Line 2\n')
        res_undo = await self.tool.execute({
            "action": "rollback",
            "path": str(test_file),
        })
        self.assertTrue(res_undo.success)
        self.assertIn("restored_path", res_undo.output)
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Modified Line 1\nModified Line 2\n")
        self.assertEqual(get_last_modified_file(), test_file)

    async def test_rollback_no_backup_error(self):
        unbacked_file = Path(self.test_dir) / "never_backed_up.xyz"
        unbacked_file.write_text("random content", encoding="utf-8")

        res = await self.tool.execute({
            "action": "rollback",
            "path": str(unbacked_file),
        })
        self.assertFalse(res.success)
        self.assertIn("No backup found", res.error)


if __name__ == "__main__":
    unittest.main()
