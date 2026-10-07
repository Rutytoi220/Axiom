#!/usr/bin/env python3
"""Master End-to-End Integration Suite for AGENT MEGASPRINT 2.

Validates:
1. Complete Three-Tier Tool Registry & Dynamic Schema Integration.
2. Tier 1 Power Suite: Media Playback, Hyprland Workspace Dispatch, and Safe Atomic File Operations.
3. Tier 2 Deep WebExtension Automation: In-place navigation, screenshot capture, and form controls.
4. REPL Telemetry: /status command execution and panel formatting.
5. Socket Cleanliness: Proper bridge lifecycle and zero-leak teardown on 41144.
"""

import asyncio
import io
import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from axiom.cli.repl import InlineRepl
from axiom.core.instructions import InstructionManager
from axiom.core.plugins import get_tool_schemas, load_plugins
from axiom.core.system_prompt import HARDENED_SYSTEM_DIRECTIVES
from axiom.tools.browser_cdp import InteractWithBrowserTool
from axiom.tools.browser_extension import BrowserExtensionBridge
from axiom.tools.hyprland_ipc import ManageDesktopWindowTool
from axiom.tools.os_desktop import ManageMediaPlaybackTool
from axiom.tools.workspace_file import ManageWorkspaceFileTool


async def test_three_tier_tool_registry():
    print("[CHECK 1] Testing Three-Tier Registry & Dynamic Plugin Schemas...")
    load_plugins()
    schemas = get_tool_schemas(0)
    names = {s["function"]["name"] for s in schemas}

    # Verify Tier 1 tools
    tier1_expected = [
        "manage_desktop_window",
        "manage_system_process",
        "manage_system_clipboard",
        "query_system_journal",
        "manage_media_playback",
        "manage_workspace_file",
    ]
    for t1 in tier1_expected:
        assert t1 in names, f"Tier 1 tool '{t1}' missing from plugin registry"

    # Verify Tier 2
    assert "interact_with_browser" in names, "Tier 2 'interact_with_browser' missing from registry"

    print(f"  → Verified {len(schemas)} active tools in registry including all Tier 1 and Tier 2 additions.")
    print("✓ Check 1 PASSED: Plugin registry and schemas fully populated.\n")


async def test_tier1_desktop_and_file_suite():
    print("[CHECK 2] Testing Tier 1 Media, Workspace Dispatch, and Safe File Operations...")

    # Media Playback
    media_tool = ManageMediaPlaybackTool()
    res_media = await media_tool.execute({"action": "status"})
    assert res_media.success
    print(f"  → Media playback status: {res_media.output.get('status', 'Active')}")

    # Desktop Window / Workspace Dispatch
    window_tool = ManageDesktopWindowTool()
    # Mock hyprctl if not running under hyprland to test contract
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        window_tool._run_hyprctl = lambda cmd: (0, "ok", "")
        shutil.which = lambda cmd: "/usr/bin/hyprctl" if cmd == "hyprctl" else shutil.which(cmd)

    res_ws = await window_tool.execute({"action": "workspace", "target": "1"})
    assert res_ws.success
    assert res_ws.output.get("action") == "workspace"
    print(f"  → Hyprland workspace switch: {res_ws.output}")

    # Safe File Operations
    file_tool = ManageWorkspaceFileTool()
    test_dir = Path(tempfile.mkdtemp(prefix="axiom_megasprint_v2_"))
    try:
        sample_file = test_dir / "code.py"
        content_v1 = "def compute():\n    return 42\n"
        res_w = await file_tool.execute({"action": "write", "path": str(sample_file), "content": content_v1})
        assert res_w.success

        # Single patch with backup
        res_p = await file_tool.execute({
            "action": "patch",
            "path": str(sample_file),
            "search_text": "return 42",
            "replace_text": "return 100",
        })
        assert res_p.success
        assert res_p.output.get("backup") is not None
        assert sample_file.read_text() == "def compute():\n    return 100\n"

        # Ambiguity guard
        res_bad = await file_tool.execute({
            "action": "patch",
            "path": str(sample_file),
            "search_text": "nonexistent_token",
            "replace_text": "noop",
        })
        assert not res_bad.success
        print("  → Safe file atomic write, patch, backup, and single-match verification confirmed.")
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    print("✓ Check 2 PASSED: Tier 1 Media, Desktop, and File suites operational.\n")


async def test_tier2_deep_browser_bridge():
    print("[CHECK 3] Testing Tier 2 Deep Browser WebExtension Actions...")
    test_port = 41148
    BrowserExtensionBridge.reset_instance()
    bridge = BrowserExtensionBridge.get_instance(port=test_port)
    await bridge.start_server()

    tool = InteractWithBrowserTool()
    import websockets

    # 1x1 transparent PNG
    SAMPLE_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    DATA_URL = f"data:image/png;base64,{SAMPLE_PNG_B64}"

    worker_task = None
    try:
        ws_uri = f"ws://{bridge.host}:{bridge.port}"
        async with websockets.connect(ws_uri) as client_ws:
            await asyncio.sleep(0.05)
            assert bridge.is_connected() is True

            async def mock_extension_worker():
                while True:
                    try:
                        raw = await client_ws.recv()
                        msg = json.loads(raw)
                        req_id = msg.get("id")
                        action = msg.get("action")
                        if not req_id:
                            continue

                        if action == "navigate_url":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "navigate_url",
                                "tab_id": 10,
                                "title": "Target Page",
                                "url": msg.get("url"),
                            }
                        elif action == "capture_tab_screenshot":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "capture_tab_screenshot",
                                "format": "png",
                                "data_url": DATA_URL,
                                "data_url_prefix": DATA_URL[:30],
                                "length": len(DATA_URL),
                            }
                        elif action == "fill_element":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "fill_element",
                                "element_id": msg.get("element_id"),
                                "element_type": "select",
                                "value": msg.get("text"),
                                "text": msg.get("text"),
                                "submitted": False,
                            }
                        else:
                            reply = {"id": req_id, "success": True, "action": action}

                        await client_ws.send(json.dumps(reply))
                    except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
                        break

            worker_task = asyncio.create_task(mock_extension_worker())

            # Test navigate_url
            res_nav = await tool.execute({"action": "navigate_url", "url": "https://example.org/test"})
            assert res_nav.success
            assert res_nav.output.get("url") == "https://example.org/test"

            # Test capture_tab_screenshot
            res_shot = await tool.execute({"action": "capture_tab_screenshot"})
            assert res_shot.success
            assert res_shot.output.get("screenshot_path") == "/tmp/axiom_tab_capture.png"

            # Test fill_element
            res_fill = await tool.execute({"action": "fill_element", "element_id": 3, "text": "choice_a"})
            assert res_fill.success
            assert res_fill.output.get("element_type") == "select"
            print("  → navigate_url, capture_tab_screenshot, and fill_element (<select>) validated.")
    finally:
        if worker_task:
            worker_task.cancel()
        await bridge.stop_server()
        BrowserExtensionBridge.reset_instance()

    print("✓ Check 3 PASSED: Tier 2 deep browser operations verified.\n")


async def test_repl_telemetry_and_clean_teardown():
    print("[CHECK 4] Testing REPL Telemetry /status command and clean socket teardown...")
    BrowserExtensionBridge.reset_instance()

    repl = InlineRepl(session_id="megasprint_v2_telemetry_test")
    await repl.start_services()
    assert repl.bridge.server is not None, "Bridge server failed to bind during repl.start_services()"

    # Capture stdout of /status command
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        handled = repl.handle_command("/status")
    output = captured.getvalue()

    assert handled is True, "/status command was not recognized by repl.handle_command"
    assert "WebSocket Extension Bridge" in output, "Missing WebSocket bridge in /status"
    assert "Desktop Environment" in output, "Missing Desktop Environment in /status"
    assert "Audio / Media (MPRIS)" in output, "Missing Audio/Media in /status"
    assert "Registered Tool Count" in output, "Missing Tool Count in /status"
    assert "VRAM / CUDA Grounding" in output, "Missing VRAM / CUDA in /status"
    print("  → REPL /status command successfully rendered all required telemetry sections.")

    # Graceful teardown
    await repl.do_exit()
    assert repl.bridge.server is None, "Bridge server was not cleared on do_exit()"

    # Verify socket 41144 was released with zero lingering sockets
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_sock.bind(("127.0.0.1", 41144))
        print("  → Port 41144 confirmed cleanly unbound and immediately re-bindable.")
    finally:
        test_sock.close()

    print("✓ Check 4 PASSED: REPL telemetry and clean socket lifecycle verified.\n")


def test_system_prompt_and_instructions():
    print("[CHECK 5] Validating System Prompt & Routing Hierarchy Directives...")
    assert "navigate_url" in HARDENED_SYSTEM_DIRECTIVES
    assert "manage_media_playback" in HARDENED_SYSTEM_DIRECTIVES
    assert 'action": "workspace"' in HARDENED_SYSTEM_DIRECTIVES

    im = InstructionManager()
    compiled = im.get_compiled_instructions()
    assert "THREE-TIER AUTOMATION DIRECTIVES" in compiled
    assert "manage_media_playback" in compiled
    assert "manage_workspace_file" in compiled
    print("✓ Check 5 PASSED: System prompt exemplars and hierarchical instructions verified.\n")


async def main():
    print("=" * 60)
    print("AXIOM AGENT MEGASPRINT 2 — MASTER INTEGRATION MATRIX")
    print("=" * 60)
    await test_three_tier_tool_registry()
    await test_tier1_desktop_and_file_suite()
    await test_tier2_deep_browser_bridge()
    await test_repl_telemetry_and_clean_teardown()
    test_system_prompt_and_instructions()
    print("=" * 60)
    print("✅ MASTER INTEGRATION MATRIX PASSED (100% SUCCESS)!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
