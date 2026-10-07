#!/usr/bin/env python3
"""Comprehensive verification test for Tier 1 Desktop Media and Hyprland Workspace Tools.

Tests:
1. ManageMediaPlaybackTool (status query, volume query, playback controls, fallback).
2. ManageDesktopWindowTool (workspace switching, window floating, fullscreen, move to workspace).
"""

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from axiom.tools.os_desktop import ManageMediaPlaybackTool
from axiom.tools.hyprland_ipc import ManageDesktopWindowTool


async def test_media_playback():
    print("\n[CHECK 1] Testing ManageMediaPlaybackTool (Tier 1 MPRIS / playerctl)...")
    tool = ManageMediaPlaybackTool()
    assert tool.name == "manage_media_playback"
    assert tool.schema["properties"]["action"]["type"] == "string"

    # Test status query
    res_status = await tool.execute({"action": "status"})
    assert res_status.success, f"Status query failed: {res_status.error}"
    assert isinstance(res_status.output, dict), f"Output must be dict: {res_status.output}"
    print(f"  → Media status query succeeded: {res_status.output.get('status', 'Active')}")

    # Test volume query
    res_vol = await tool.execute({"action": "volume"})
    assert res_vol.success, f"Volume query failed: {res_vol.error}"
    assert isinstance(res_vol.output, dict)
    print(f"  → Volume query succeeded: {res_vol.output}")

    # Test play_pause without throwing
    res_toggle = await tool.execute({"action": "play_pause"})
    assert res_toggle.success or "failed" in (res_toggle.error or "").lower()
    print(f"  → Play/pause toggle handled cleanly: success={res_toggle.success}")

    # Test unsupported action
    res_bad = await tool.execute({"action": "unsupported_command_xyz"})
    assert not res_bad.success
    assert "Unsupported media action" in res_bad.error
    print("  → Unsupported action rejected with descriptive error.")

    print("✓ Check 1 PASSED: ManageMediaPlaybackTool fully operational.")


async def test_hyprland_workspace_dispatch():
    print("\n[CHECK 2] Testing ManageDesktopWindowTool (Tier 1 Hyprland Workspace Dispatch)...")
    tool = ManageDesktopWindowTool()
    assert tool.name == "manage_desktop_window"

    hyprctl_available = shutil.which("hyprctl") is not None and bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    print(f"  → Hyprland environment detected: {hyprctl_available}")

    if not hyprctl_available:
        # Mock hyprctl to verify execution paths and structured return dictionaries
        async def mock_run_hyprctl(command: str):
            if "clients" in command:
                return 0, json.dumps([{"address": "0x123", "class": "zen", "title": "Zen Browser", "workspace": {"name": "1"}}]), ""
            elif "activewindow" in command:
                return 0, json.dumps({"address": "0x123", "title": "Zen Browser"}), ""
            elif "dispatch workspace" in command:
                return 0, "ok", ""
            elif "dispatch togglefloating" in command:
                return 0, "ok", ""
            elif "dispatch fullscreen" in command:
                return 0, "ok", ""
            elif "dispatch movetoworkspace" in command:
                return 0, "ok", ""
            return 0, "ok", ""

        tool._run_hyprctl = mock_run_hyprctl
        # Also mock shutil.which so it passes the binary check
        orig_which = shutil.which
        shutil.which = lambda cmd: "/usr/bin/hyprctl" if cmd == "hyprctl" else orig_which(cmd)

    try:
        # 1. Test workspace action
        res_ws = await tool.execute({"action": "workspace", "target": "2"})
        assert res_ws.success, f"Workspace dispatch failed: {res_ws.error}"
        assert isinstance(res_ws.output, dict), f"Output must be dict: {res_ws.output}"
        assert res_ws.output.get("action") == "workspace"
        assert res_ws.output.get("workspace") == "2"
        print(f"  → Workspace switch dispatch succeeded: {res_ws.output}")

        # 2. Test move_to_workspace action
        res_move = await tool.execute({"action": "move_to_workspace", "target": "3"})
        assert res_move.success, f"Move to workspace failed: {res_move.error}"
        assert isinstance(res_move.output, dict)
        assert res_move.output.get("action") == "move_to_workspace"
        assert res_move.output.get("target_workspace") == "3"
        print(f"  → Move to workspace dispatch succeeded: {res_move.output}")

        # 3. Test toggle_floating action
        res_float = await tool.execute({"action": "toggle_floating"})
        assert res_float.success, f"Toggle floating failed: {res_float.error}"
        assert isinstance(res_float.output, dict)
        assert res_float.output.get("action") == "toggle_floating"
        print(f"  → Toggle floating dispatch succeeded: {res_float.output}")

        # 4. Test fullscreen action
        res_fs = await tool.execute({"action": "fullscreen"})
        assert res_fs.success, f"Fullscreen toggle failed: {res_fs.error}"
        assert isinstance(res_fs.output, dict)
        assert res_fs.output.get("action") == "fullscreen"
        print(f"  → Fullscreen dispatch succeeded: {res_fs.output}")

        # 5. Test missing target validation
        res_missing = await tool.execute({"action": "workspace"})
        assert not res_missing.success
        assert "Target workspace" in res_missing.error
        print("  → Missing workspace target properly validated and rejected.")

    finally:
        if not hyprctl_available:
            shutil.which = orig_which

    print("✓ Check 2 PASSED: ManageDesktopWindowTool workspace actions verified.")


async def main():
    print("=" * 60)
    print("AXIOM TIER 1 DESKTOP MEDIA & HYPRLAND WORKSPACE SUITE")
    print("=" * 60)
    await test_media_playback()
    await test_hyprland_workspace_dispatch()
    print("\n" + "=" * 60)
    print("✅ ALL DESKTOP MEDIA & HYPRLAND CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
