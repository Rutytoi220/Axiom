"""Comprehensive Test Suite for AXIOM Tier 1 OS Power Tools.

Tests:
1. manage_system_process: listing processes, PID inspection, and strict PID protection guards.
2. manage_system_clipboard: write/read roundtrip in Wayland/X11 environment.
3. query_system_journal: journalctl log retrieval and structured LLM envelope.
4. Dynamic plugin auto-discovery and per-tier execution budgets.
"""

import asyncio
import os
import sys
from axiom.tools.os_system import (
    ManageSystemProcessTool,
    ManageSystemClipboardTool,
    QuerySystemJournalTool,
)
from axiom.core.plugins import (
    load_plugins,
    get_tool_schemas,
    execute_tool,
    get_tier_timeout,
    TIER_TIMEOUTS,
)


async def test_os_tools_suite():
    print("=" * 60)
    print("AXIOM TIER 1 OS POWER TOOLS & LATENCY BUDGET VERIFICATION")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Check 1: manage_system_process listing and inspection
    # -----------------------------------------------------------------------
    print("\n[CHECK 1] Testing manage_system_process...")
    proc_tool = ManageSystemProcessTool()
    assert proc_tool.name == "manage_system_process"

    # Action: list
    res_list = await proc_tool.execute({"action": "list"})
    assert res_list.success is True, f"process list failed: {res_list.error}"
    assert "processes" in res_list.output, "Expected 'processes' key in output."
    assert res_list.output["count"] > 0, "Expected non-zero process count."
    first_proc = res_list.output["processes"][0]
    assert "pid" in first_proc and "comm" in first_proc, "Process dict missing pid or comm."
    print(f"  → Process listing succeeded: found {res_list.output['count']} top processes (Top: PID {first_proc['pid']} - {first_proc['comm']}).")

    # Action: inspect self PID
    self_pid = os.getpid()
    res_insp = await proc_tool.execute({"action": "inspect", "target": str(self_pid)})
    assert res_insp.success is True, f"process inspect failed: {res_insp.error}"
    assert res_insp.output["pid"] == self_pid, f"Expected PID {self_pid}, got {res_insp.output.get('pid')}"
    assert "comm" in res_insp.output and "args" in res_insp.output
    print(f"  → Inspect self PID ({self_pid}) succeeded: comm='{res_insp.output['comm']}'.")

    # Action: inspect by name
    res_name = await proc_tool.execute({"action": "inspect", "target": "python"})
    assert res_name.success is True, f"process inspect by name failed: {res_name.error}"
    assert "matches" in res_name.output and len(res_name.output["matches"]) > 0
    print(f"  → Inspect by name 'python' succeeded: {res_name.output['count']} matching processes.")

    # Action: inspect port (e.g. :41144 or port query)
    res_port = await proc_tool.execute({"action": "inspect", "target": ":41144"})
    # Either active process is found or structured error returned
    print(f"  → Port inspection for :41144 handled gracefully: success={res_port.success}.")
    print("✓ Check 1 PASSED: manage_system_process listing and inspection operational.")

    # -----------------------------------------------------------------------
    # Check 2: PID Protection Guards against termination
    # -----------------------------------------------------------------------
    print("\n[CHECK 2] Testing PID Protection Guards against accidental termination...")
    
    # 1. PID 1 protection
    res_kill_1 = await proc_tool.execute({"action": "kill", "target": "1"})
    assert res_kill_1.success is False, "PID 1 must NEVER be terminable!"
    assert "refused" in res_kill_1.error.lower() or "protected" in res_kill_1.error.lower()
    print(f"  → PID 1 termination correctly blocked: '{res_kill_1.error}'")

    # 2. Self PID protection
    res_kill_self = await proc_tool.execute({"action": "kill", "target": str(self_pid)})
    assert res_kill_self.success is False, "Current runtime process must NEVER be terminable!"
    assert "refused" in res_kill_self.error.lower() or "current" in res_kill_self.error.lower()
    print(f"  → Self PID termination correctly blocked: '{res_kill_self.error}'")

    # 3. Parent PID protection
    ppid = os.getppid()
    res_kill_parent = await proc_tool.execute({"action": "kill", "target": str(ppid)})
    assert res_kill_parent.success is False, "Parent process must NEVER be terminable!"
    assert "refused" in res_kill_parent.error.lower() or "parent" in res_kill_parent.error.lower()
    print(f"  → Parent PID termination correctly blocked: '{res_kill_parent.error}'")
    print("✓ Check 2 PASSED: Critical system processes strictly protected against termination.")

    # -----------------------------------------------------------------------
    # Check 3: manage_system_clipboard read/write roundtrip
    # -----------------------------------------------------------------------
    print("\n[CHECK 3] Testing manage_system_clipboard...")
    clip_tool = ManageSystemClipboardTool()
    assert clip_tool.name == "manage_system_clipboard"

    test_token = "axiom_test_token_sprint_verification_42"
    res_write = await clip_tool.execute({"action": "write", "content": test_token})
    assert res_write.success is True, f"clipboard write failed: {res_write.error}"
    assert res_write.output["content"] == test_token

    res_read = await clip_tool.execute({"action": "read"})
    assert res_read.success is True, f"clipboard read failed: {res_read.error}"
    assert res_read.output["content"] == test_token, f"Clipboard mismatch: expected '{test_token}', got '{res_read.output['content']}'"
    assert res_read.output["length"] == len(test_token)
    print(f"  → Clipboard roundtrip verified: successfully wrote and read token '{test_token}'.")
    print("✓ Check 3 PASSED: manage_system_clipboard read/write fully operational.")

    # -----------------------------------------------------------------------
    # Check 4: query_system_journal log retrieval
    # -----------------------------------------------------------------------
    print("\n[CHECK 4] Testing query_system_journal...")
    journal_tool = QuerySystemJournalTool()
    assert journal_tool.name == "query_system_journal"

    res_journal = await journal_tool.execute({"lines": 10})
    assert res_journal.success is True, f"journalctl query failed: {res_journal.error}"
    assert "logs" in res_journal.output, "Expected 'logs' in output."
    assert res_journal.output["lines"] == 10
    print(f"  → journalctl query succeeded: retrieved {res_journal.output['count']} log lines.")
    print("✓ Check 4 PASSED: query_system_journal queries systemd journal cleanly.")

    # -----------------------------------------------------------------------
    # Check 5: Dynamic Plugin Discovery & Per-Tier Execution Latency Budgets
    # -----------------------------------------------------------------------
    print("\n[CHECK 5] Testing Dynamic Plugin Registry & Per-Tier Execution Budgets...")
    load_plugins()
    schemas = get_tool_schemas(0)
    schema_names = {s["function"]["name"] for s in schemas}

    assert "manage_system_process" in schema_names, "manage_system_process missing from schemas"
    assert "manage_system_clipboard" in schema_names, "manage_system_clipboard missing from schemas"
    assert "query_system_journal" in schema_names, "query_system_journal missing from schemas"
    print(f"  → Verified all 3 new tools in dynamic registry ({len(schemas)} total tools active).")

    # Dynamic execution test
    res_dyn_clip = await execute_tool("manage_system_clipboard", action="read")
    assert test_token in res_dyn_clip, f"Dynamic tool execution failed: {res_dyn_clip}"
    print("  → Dynamic execute_tool('manage_system_clipboard') verified.")

    # Budget verification
    assert get_tier_timeout("manage_system_process") == 8.0, "Tier 1 timeout must be 8.0s"
    assert get_tier_timeout("manage_system_clipboard") == 8.0, "Tier 1 timeout must be 8.0s"
    assert get_tier_timeout("query_system_journal") == 8.0, "Tier 1 timeout must be 8.0s"
    assert get_tier_timeout("manage_desktop_window") == 8.0, "Tier 1 timeout must be 8.0s"
    assert get_tier_timeout("execute_command") == 8.0, "Tier 1 timeout must be 8.0s"
    assert get_tier_timeout("interact_with_browser") == 10.0, "Tier 2 timeout must be 10.0s"
    assert get_tier_timeout("interact_with_ui") == 35.0, "Tier 3 timeout must be 35.0s"
    assert get_tier_timeout("vision") == 35.0, "Tier 3 timeout must be 35.0s"
    print("  → Tier 1 (8s), Tier 2 (10s), Tier 3 (35s) timeout budgets strictly verified.")
    print("✓ Check 5 PASSED: Plugin auto-discovery and tier execution budgets verified.")

    print("\n" + "=" * 60)
    print("✅ ALL TIER 1 OS POWER TOOLS & BUDGET CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_os_tools_suite())
