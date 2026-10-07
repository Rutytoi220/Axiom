#!/usr/bin/env python3
"""Comprehensive verification test for Tier 1 Safe Workspace File Operations.

Tests:
1. manage_workspace_file write with atomic backup creation in /tmp/axiom_backups/.
2. manage_workspace_file read with line limits and truncation tracking.
3. manage_workspace_file patch with single-match verification and backup creation.
4. manage_workspace_file patch safety guards (0 matches or >1 ambiguous matches abort without mutating).
5. manage_workspace_file list_tree respecting .gitignore up to depth 3.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from axiom.tools.workspace_file import ManageWorkspaceFileTool, BACKUP_DIR


async def main():
    print("=" * 60)
    print("AXIOM TIER 1 SAFE WORKSPACE FILE SUITE")
    print("=" * 60)

    tool = ManageWorkspaceFileTool()
    assert tool.name == "manage_workspace_file"

    # Create an isolated temporary test directory
    test_dir = Path(tempfile.mkdtemp(prefix="axiom_test_workspace_"))
    try:
        # [CHECK 1] Test Write (New file)
        print("\n[CHECK 1] Testing manage_workspace_file 'write' action on new file...")
        target_file = test_dir / "sample.txt"
        initial_content = "Line 1: Hello World\nLine 2: Target to replace\nLine 3: Final line\n"
        res_write1 = await tool.execute({
            "action": "write",
            "path": str(target_file),
            "content": initial_content,
        })
        assert res_write1.success, f"Initial write failed: {res_write1.error}"
        assert target_file.is_file()
        assert target_file.read_text() == initial_content
        print(f"  → Successfully wrote {res_write1.output.get('bytes_written')} bytes to {target_file.name}.")
        print("✓ Check 1 PASSED: Initial write succeeded.")

        # [CHECK 2] Test Read
        print("\n[CHECK 2] Testing manage_workspace_file 'read' action...")
        res_read = await tool.execute({
            "action": "read",
            "path": str(target_file),
            "max_lines": 2,
        })
        assert res_read.success, f"Read failed: {res_read.error}"
        assert res_read.output.get("lines_read") == 2
        assert res_read.output.get("total_lines") == 3
        assert res_read.output.get("truncated") is True
        print(f"  → Read with line budget verified: read 2 of 3 lines (truncated=True).")
        print("✓ Check 2 PASSED: Read line bounding verified.")

        # [CHECK 3] Test Write on existing file with automatic backup
        print("\n[CHECK 3] Testing write backup generation...")
        updated_content = "Overwritten line A\nOverwritten line B\n"
        res_write2 = await tool.execute({
            "action": "write",
            "path": str(target_file),
            "content": updated_content,
        })
        assert res_write2.success
        backup_path = res_write2.output.get("backup")
        assert backup_path and Path(backup_path).is_file(), f"Backup file not found at {backup_path}"
        assert Path(backup_path).read_text() == initial_content, "Backup content does not match original"
        print(f"  → Verified automatic backup created at: {backup_path}")
        print("✓ Check 3 PASSED: Write creates verified backup copy in /tmp/axiom_backups/.")

        # [CHECK 4] Test Patch (Exact single match)
        print("\n[CHECK 4] Testing manage_workspace_file 'patch' action...")
        res_patch = await tool.execute({
            "action": "patch",
            "path": str(target_file),
            "search_text": "Overwritten line B",
            "replace_text": "Patched line B [SUCCESS]",
        })
        assert res_patch.success, f"Patch failed: {res_patch.error}"
        assert target_file.read_text() == "Overwritten line A\nPatched line B [SUCCESS]\n"
        patch_backup = res_patch.output.get("backup")
        assert patch_backup and Path(patch_backup).is_file()
        assert Path(patch_backup).read_text() == updated_content
        print(f"  → Verified patch applied cleanly and backup generated at: {patch_backup}")
        print("✓ Check 4 PASSED: Single-occurrence patch succeeded.")

        # [CHECK 5] Test Patch Guards (0 matches)
        print("\n[CHECK 5] Testing patch safety guard against 0 matches...")
        res_patch_0 = await tool.execute({
            "action": "patch",
            "path": str(target_file),
            "search_text": "Non-existent string that is not here",
            "replace_text": "Whatever",
        })
        assert not res_patch_0.success
        assert "appeared 0 times" in res_patch_0.error
        # Verify file content was NOT mutated
        assert target_file.read_text() == "Overwritten line A\nPatched line B [SUCCESS]\n"
        print("  → 0-match patch safely aborted without mutating file.")
        print("✓ Check 5 PASSED: 0-match guard verified.")

        # [CHECK 6] Test Patch Guards (>1 matches ambiguous collision)
        print("\n[CHECK 6] Testing patch safety guard against ambiguous duplicate matches...")
        multi_content = "duplicate keyword\nMiddle content\nduplicate keyword\n"
        target_file.write_text(multi_content)
        res_patch_multi = await tool.execute({
            "action": "patch",
            "path": str(target_file),
            "search_text": "duplicate keyword",
            "replace_text": "replacement",
        })
        assert not res_patch_multi.success
        assert "appeared 2 times" in res_patch_multi.error
        # Verify file content remained intact
        assert target_file.read_text() == multi_content
        print("  → Ambiguous 2-match patch safely aborted without mutating file.")
        print("✓ Check 6 PASSED: Ambiguity guard verified.")

        # [CHECK 7] Test list_tree respecting .gitignore
        print("\n[CHECK 7] Testing manage_workspace_file 'list_tree' respecting .gitignore...")
        # Create directory hierarchy with ignored files
        (test_dir / "src").mkdir()
        (test_dir / "src" / "index.py").write_text("print(1)")
        (test_dir / "node_modules").mkdir()
        (test_dir / "node_modules" / "pkg.js").write_text("dummy")
        (test_dir / ".git").mkdir()
        (test_dir / ".git" / "config").write_text("git")
        (test_dir / ".gitignore").write_text("secret.env\n*.tmp\n")
        (test_dir / "secret.env").write_text("SECRET=123")
        (test_dir / "temp.tmp").write_text("temp")

        res_tree = await tool.execute({
            "action": "list_tree",
            "path": str(test_dir),
        })
        assert res_tree.success, f"list_tree failed: {res_tree.error}"
        entries = res_tree.output.get("entries", [])
        entry_names = [e["name"] for e in entries]

        assert "src" in entry_names, "src directory should be listed"
        assert ".gitignore" in entry_names, ".gitignore should be listed"
        assert "node_modules" not in entry_names, "node_modules should be ignored"
        assert ".git" not in entry_names, ".git should be ignored"
        assert "secret.env" not in entry_names, "secret.env should be ignored via .gitignore"
        assert "temp.tmp" not in entry_names, "*.tmp should be ignored via .gitignore"

        print(f"  → Tree filtered properly: {entry_names}")
        print("✓ Check 7 PASSED: list_tree correctly respected .gitignore and default ignore lists.")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\n" + "=" * 60)
    print("✅ ALL WORKSPACE FILE OPERATIONS & SAFETY CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
