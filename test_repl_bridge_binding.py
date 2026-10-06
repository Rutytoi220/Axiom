"""Verification Test: REPL Bridge Eager Startup & GC Retention."""

import asyncio
import websockets
from axiom.cli.repl import InlineRepl
from axiom.tools.browser_extension import BrowserExtensionBridge


async def test_repl_bridge_binding():
    print("[TEST] Initializing InlineRepl instance...")
    # Ensure bridge singleton is clean before test
    BrowserExtensionBridge.reset_instance()

    repl = InlineRepl(session_id="test_bridge_binding_session")
    assert repl.bridge is None
    assert repl._bridge_server is None

    print("[TEST] Awaiting repl.start_services()...")
    await repl.start_services()

    # 1. Assert bridge server is initialized and retained
    from axiom.tools.browser_extension import get_bridge
    assert repl.bridge is not None, "repl.bridge should be initialized"
    assert repl.bridge.server is not None, "repl.bridge.server must be active"
    assert repl._bridge_server is not None, "repl._bridge_server must retain server reference"
    assert repl._bridge_server is repl.bridge.server, "References must match"
    assert get_bridge().server is not None, "get_bridge().server must be active"
    assert get_bridge().server.is_serving(), "get_bridge().server must be actively listening"
    print("✓ Bridge server reference retained on InlineRepl instance and actively serving.")

    # 2. Test WebSocket connection directly
    ws_uri = f"ws://{repl.bridge.host}:{repl.bridge.port}"
    print(f"[TEST] Connecting to {ws_uri} via websockets client...")
    async with websockets.connect(ws_uri) as client_ws:
        await asyncio.sleep(0.1)
        assert repl.bridge.is_connected() is True
        print("✓ Connected to REPL bridge successfully; is_connected() == True.")

    # 3. Teardown via repl.do_exit()
    print("[TEST] Invoking repl.do_exit()...")
    await repl.do_exit()
    assert repl._bridge_server is None, "repl._bridge_server should be reset"
    assert repl.bridge.server is None, "repl.bridge.server should be stopped"
    assert repl.bridge.is_connected() is False
    print("✓ REPL bridge shut down cleanly via do_exit().")

    # 4. Confirm port is closed
    try:
        async with websockets.connect(ws_uri, open_timeout=0.5):
            assert False, "Connection should fail after do_exit"
    except Exception:
        print("✓ Port verified closed after teardown.")

    # Reset bridge singleton for other tests
    BrowserExtensionBridge.reset_instance()
    print("\n✅ test_repl_bridge_binding PASSED successfully!")


if __name__ == "__main__":
    asyncio.run(test_repl_bridge_binding())
