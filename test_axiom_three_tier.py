"""Comprehensive verification test harness for AXIOM Three-Tier Automation and Inline CLI.

Verifies:
1. Inline CLI imports and initializes without layout errors.
2. manage_desktop_window queries hyprctl JSON without crashing.
3. interact_with_browser handles offline CDP connections gracefully without blocking.
4. NativeOrchestrator correctly selects Tier 1/2 tools before falling back to Tier 3.
"""

import asyncio
import sys
from axiom.cli.repl import InlineRepl
from axiom.tools.hyprland_ipc import ManageDesktopWindowTool
from axiom.tools.browser_cdp import InteractWithBrowserTool
from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.core.plugins import load_plugins, get_tool_schemas


async def test_three_tier_suite():
    print("=" * 60)
    print("AXIOM THREE-TIER AUTOMATION & INLINE CLI VERIFICATION")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Check 1: Inline CLI initialization without layout errors
    # -----------------------------------------------------------------------
    print("\n[CHECK 1] Testing Inline CLI initialization...")
    repl = InlineRepl(session_id="test_suite_session")
    assert repl.prompt_session is not None, "PromptSession failed to initialize."
    assert repl.orchestrator is not None, "NativeOrchestrator failed to initialize in REPL."
    
    # Test command handling in REPL
    handled_help = repl.handle_command("/help")
    assert handled_help is True, "REPL /help command handler failed."
    handled_session = repl.handle_command("/session test_switched")
    assert handled_session is True, "REPL /session command handler failed."
    assert repl.session_id == "test_switched", "REPL session ID was not updated."
    print("✓ Check 1 PASSED: Inline CLI initialized cleanly without layout errors.")

    # -----------------------------------------------------------------------
    # Check 2: manage_desktop_window queries hyprctl JSON without crashing
    # -----------------------------------------------------------------------
    print("\n[CHECK 2] Testing manage_desktop_window (Tier 1 System IPC)...")
    hypr_tool = ManageDesktopWindowTool()
    assert hypr_tool.name == "manage_desktop_window"

    # Query active clients
    res_list = await hypr_tool.execute({"action": "list"})
    assert res_list.success is True, f"hyprctl clients failed: {res_list.error}"
    assert isinstance(res_list.output, dict), "Expected dict output from clients query."
    assert "windows" in res_list.output, "Expected 'windows' in output."
    print(f"  → Found {res_list.output.get('count', 0)} open Hyprland windows.")

    # Query active window
    res_active = await hypr_tool.execute({"action": "get_active"})
    assert res_active.success is True, f"hyprctl activewindow failed: {res_active.error}"
    print(f"  → Active window query succeeded: {type(res_active.output)}")
    print("✓ Check 2 PASSED: manage_desktop_window executed deterministically via hyprctl.")

    # -----------------------------------------------------------------------
    # Check 3: interact_with_browser handles offline CDP connections gracefully
    # -----------------------------------------------------------------------
    print("\n[CHECK 3] Testing interact_with_browser (Tier 2 Semantic UI)...")
    browser_tool = InteractWithBrowserTool()
    assert browser_tool.name == "interact_with_browser"

    # Should handle offline CDP port gracefully without raising unhandled exceptions
    offline_click = await browser_tool.execute({"action": "click", "selector": "button#submit"})
    assert offline_click.success is False, "Expected offline click to report failure."
    assert offline_click.error is not None, "Expected an informative error message."
    assert "CDP" in offline_click.error or "debugging" in offline_click.error or "Connect" in offline_click.error
    print(f"  → Offline click handled gracefully: '{offline_click.error[:60]}...'")

    offline_tabs = await browser_tool.execute({"action": "list_tabs"})
    assert offline_tabs.success is False, "Expected offline list_tabs to report failure."
    print(f"  → Offline tab discovery handled gracefully: '{offline_tabs.error[:60]}...'")
    print("✓ Check 3 PASSED: interact_with_browser handled offline state with zero unhandled exceptions.")

    # -----------------------------------------------------------------------
    # Check 4: Three-Tier Router Classification & Hierarchy
    # -----------------------------------------------------------------------
    print("\n[CHECK 4] Testing Three-Tier Router classification & tool routing...")
    
    # Tier 1 Tests (System IPC)
    tier1_tasks = [
        "Please switch to workspace 2 for me",
        "Focus window matching kitty",
        "Make the active window fullscreen",
        "Toggle floating mode for this window",
        "Close window 0x55a8e8690210",
        "List all active windows on my desktop",
    ]
    for task in tier1_tasks:
        tier = NativeOrchestrator.route_tier(task)
        tool = NativeOrchestrator.get_tier_tool(task)
        assert tier == "tier1_ipc", f"Task '{task}' was routed to '{tier}', expected 'tier1_ipc'."
        assert tool == "manage_desktop_window", f"Task '{task}' mapped to '{tool}', expected 'manage_desktop_window'."
    print(f"  → Verified {len(tier1_tasks)} Tier 1 (System IPC) route classifications.")

    # Tier 2 Tests (Semantic UI Browser CDP)
    tier2_tasks = [
        "Click the start test button on monkeytype",
        "Type 'quantum computing' into the search input on Google Chrome",
        "Inspect the DOM title of the current website",
        "Click the link with selector a[href='/dashboard'] in Zen Browser",
        "Evaluate document.body.innerText in this web app",
        "Search for documentation in the browser tab",
    ]
    for task in tier2_tasks:
        tier = NativeOrchestrator.route_tier(task)
        tool = NativeOrchestrator.get_tier_tool(task)
        assert tier == "tier2_browser", f"Task '{task}' was routed to '{tier}', expected 'tier2_browser'."
        assert tool == "interact_with_browser", f"Task '{task}' mapped to '{tool}', expected 'interact_with_browser'."
    print(f"  → Verified {len(tier2_tasks)} Tier 2 (Semantic UI) route classifications.")

    # Tier 3 Tests (Vision Fallback)
    tier3_tasks = [
        "Click the green target in this retro OpenGL canvas game",
        "Shoot the spaceship on screen",
        "Click the unmapped button on this legacy binary UI without DOM or accessibility",
    ]
    for task in tier3_tasks:
        tier = NativeOrchestrator.route_tier(task)
        tool = NativeOrchestrator.get_tier_tool(task)
        assert tier == "tier3_vision", f"Task '{task}' was routed to '{tier}', expected 'tier3_vision'."
        assert tool == "interact_with_ui", f"Task '{task}' mapped to '{tool}', expected 'interact_with_ui'."
    print(f"  → Verified {len(tier3_tasks)} Tier 3 (Vision Fallback) route classifications.")
    print("✓ Check 4 PASSED: Three-Tier Router correctly prioritizes Tier 1 and Tier 2 before Tier 3 fallback.")

    # -----------------------------------------------------------------------
    # Check 5: Dynamic Plugin Registry Coexistence
    # -----------------------------------------------------------------------
    print("\n[CHECK 5] Testing Dynamic Plugin Registry Coexistence...")
    load_plugins()
    schemas = get_tool_schemas(0)
    tool_names = [s["function"]["name"] for s in schemas]
    print(f"  → Total active plugins: {len(tool_names)}")
    assert "manage_desktop_window" in tool_names, "manage_desktop_window missing from registry!"
    assert "interact_with_browser" in tool_names, "interact_with_browser missing from registry!"
    assert "interact_with_ui" in tool_names, "interact_with_ui missing from registry!"
    print("✓ Check 5 PASSED: All three tier tools registered and available simultaneously.")

    print("\n" + "=" * 60)
    print("✅ ALL THREE-TIER AUTOMATION & INLINE CLI CHECKS PASSED!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_three_tier_suite())
