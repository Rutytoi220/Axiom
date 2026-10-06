"""Verification Harness for AXIOM Browser Extension & Local WebSocket Bridge."""

import asyncio
import json
from pathlib import Path
import websockets

from axiom.tools.browser_extension import (
    BrowserExtensionBridge,
    get_bridge,
    interact_with_browser,
)


def test_extension_scaffold():
    print("[CHECK 1] Testing WebExtension Scaffold Files...")
    ext_dir = Path(__file__).parent / "axiom" / "tools" / "extension"
    assert ext_dir.is_dir(), f"Extension directory missing: {ext_dir}"

    manifest_file = ext_dir / "manifest.json"
    assert manifest_file.is_file(), "manifest.json missing"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert manifest.get("manifest_version") == 3, "Expected manifest_version 3"
    perms = manifest.get("permissions", [])
    assert "tabs" in perms, "Missing 'tabs' permission"
    assert "activeTab" in perms, "Missing 'activeTab' permission"
    assert "scripting" in perms, "Missing 'scripting' permission"
    assert "<all_urls>" in manifest.get("host_permissions", []), "Missing '<all_urls>' host permission"

    bg_file = ext_dir / "background.js"
    assert bg_file.is_file(), "background.js missing"
    bg_code = bg_file.read_text(encoding="utf-8")
    assert "41144" in bg_code, "Port 41144 not configured in background.js"
    assert "switch_tab" in bg_code, "switch_tab handler missing in background.js"
    assert "click" in bg_code, "click handler missing in background.js"
    assert "type" in bg_code, "type handler missing in background.js"
    assert "get_dom" in bg_code, "get_dom handler missing in background.js"

    # Verify icons
    icons_dir = ext_dir / "icons"
    assert (icons_dir / "icon.svg").is_file(), "icon.svg missing"
    assert (icons_dir / "icon-16.png").is_file(), "icon-16.png missing"
    assert (icons_dir / "icon-48.png").is_file(), "icon-48.png missing"
    assert (icons_dir / "icon-128.png").is_file(), "icon-128.png missing"
    print("✓ Check 1 PASSED: WebExtension Manifest V3, background worker, and icons validated.\n")


async def run_bridge_lifecycle_tests():
    print("[CHECK 2] Testing Local WebSocket Bridge Server Lifecycle & Commands...")
    bridge = get_bridge()
    await bridge.start_server()
    assert bridge.server is not None, "Failed to start WebSocket server on 41144"

    try:
        # 1. Test offline error reporting
        offline_res = await interact_with_browser("list_tabs")
        assert offline_res.success is False
        assert "41144" in offline_res.error or "connected" in offline_res.error.lower()
        print(f"  → Offline error handled cleanly: '{offline_res.error}'")

        # 2. Connect mock WebExtension client
        ws_uri = f"ws://{bridge.host}:{bridge.port}"
        async with websockets.connect(ws_uri) as client_ws:
            # Allow server to register client
            await asyncio.sleep(0.1)
            assert bridge.is_connected() is True
            print(f"  → Mock extension connected to {ws_uri} (active clients: {bridge.client_count})")

            # Background task to emulate background.js responses
            async def mock_extension_worker():
                try:
                    while True:
                        msg_raw = await client_ws.recv()
                        msg = json.loads(msg_raw)
                        req_id = msg.get("id")
                        action = msg.get("action")

                        if action == "switch_tab":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "switch_tab",
                                "tab": {
                                    "id": 101,
                                    "title": "Google Gemini - AI Chat",
                                    "url": "https://gemini.google.com/app",
                                },
                            }
                        elif action == "list_tabs":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "list_tabs",
                                "tabs": [
                                    {"id": 101, "title": "Google Gemini", "url": "https://gemini.google.com", "active": True},
                                    {"id": 102, "title": "Monkeytype", "url": "https://monkeytype.com", "active": False},
                                ],
                            }
                        elif action == "click":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "click",
                                "result": f"Clicked <button> matching '{msg.get('selector')}'",
                            }
                        elif action == "type":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "type",
                                "result": f"Typed '{msg.get('text')}' into '{msg.get('selector')}'",
                            }
                        elif action == "get_dom":
                            reply = {
                                "id": req_id,
                                "success": True,
                                "action": "get_dom",
                                "title": "Google Gemini",
                                "url": "https://gemini.google.com",
                                "content": "Welcome to Gemini. How can I help you today?",
                            }
                        else:
                            reply = {"id": req_id, "success": False, "error": f"Unknown {action}"}

                        await client_ws.send(json.dumps(reply))
                except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
                    pass

            worker_task = asyncio.create_task(mock_extension_worker())

            try:
                # 3. Test switch_tab (Target requirement)
                res_switch = await interact_with_browser("switch_tab", query="gemini")
                assert res_switch.success is True, f"switch_tab failed: {res_switch.error}"
                assert res_switch["tab"]["title"] == "Google Gemini - AI Chat"
                print(f"  → switch_tab roundtrip verified: Focused '{res_switch['tab']['title']}'")

                # 4. Test list_tabs
                res_tabs = await interact_with_browser("list_tabs")
                assert res_tabs.success is True
                assert len(res_tabs["tabs"]) == 2
                print(f"  → list_tabs roundtrip verified: Retrieved {len(res_tabs['tabs'])} tabs")

                # 5. Test click
                res_click = await interact_with_browser("click", selector="button.submit")
                assert res_click.success is True
                assert "Clicked" in res_click["result"]
                print(f"  → click roundtrip verified: {res_click['result']}")

                # 6. Test type
                res_type = await interact_with_browser("type", selector="input#search", text="hello axiom")
                assert res_type.success is True
                assert "hello axiom" in res_type["result"]
                print(f"  → type roundtrip verified: {res_type['result']}")

                # 7. Test get_dom
                res_dom = await interact_with_browser("get_dom")
                assert res_dom.success is True
                assert "Gemini" in res_dom["content"]
                print(f"  → get_dom roundtrip verified: Content length {len(res_dom['content'])} chars")

            finally:
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass

    finally:
        await bridge.stop_server()

    print("✓ Check 2 PASSED: End-to-end WebSocket bridge roundtrip fully operational.\n")


def test_main():
    test_extension_scaffold()
    asyncio.run(run_bridge_lifecycle_tests())
    print("============================================================")
    print("✅ ALL BROWSER EXTENSION & WEBSOCKET BRIDGE CHECKS PASSED!")
    print("============================================================")


if __name__ == "__main__":
    test_main()
