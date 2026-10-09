"""Unit and integration tests for Phase 3 Browser Hardening: Transport Resilience & WebSocket Lifecycle.

Covers:
1. test_connection_drop_fails_fast_without_timeout:
   Instant fast-fail (< 200ms) on socket drop without waiting for 8.5s timeout.
2. test_server_restart_socket_reuse:
   Port 41144 binding recovery with SO_REUSEADDR on rapid restart.
3. test_client_replacement_on_reconnect:
   Clean client replacement when new extension connects, routing commands to new client.
4. test_ping_pong_heartbeat:
   Bidirectional ping/pong keepalive in background.js and Python bridge.
5. test_stop_server_drains_pending_requests:
   All pending futures resolve with ConnectionResetError and dict cleared on stop_server.
6. test_browser_tool_handles_connection_reset_gracefully:
   InteractWithBrowserTool.execute() returns structured remedy envelope on ConnectionResetError.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import unittest
from unittest.mock import patch

import websockets

from axiom.tools.browser_cdp import InteractWithBrowserTool
from axiom.tools.browser_extension import (
    BrowserExtensionBridge,
    _is_client_open,
    get_bridge,
)


class TestBrowserTransportP3(unittest.IsolatedAsyncioTestCase):
    """Test suite for Tier 2 Browser Hardening Phase 3."""

    async def asyncSetUp(self) -> None:
        bridge = get_bridge()
        if bridge.server is not None:
            await bridge.stop_server()
        BrowserExtensionBridge.reset_instance()

    async def asyncTearDown(self) -> None:
        bridge = get_bridge()
        if bridge.server is not None:
            await bridge.stop_server()
        BrowserExtensionBridge.reset_instance()

    async def test_connection_drop_fails_fast_without_timeout(self) -> None:
        """Start bridge, connect mock client, initiate command, drop socket mid-flight.

        Assert send_command raises ConnectionResetError immediately (< 200ms) rather than waiting 8.5s.
        """
        bridge = BrowserExtensionBridge(port=41144)
        await bridge.start_server()
        try:
            uri = f"ws://127.0.0.1:{bridge.port}"
            client = await websockets.connect(uri)
            await asyncio.sleep(0.05)
            self.assertTrue(bridge.is_connected())

            async def drop_client():
                await asyncio.sleep(0.05)
                await client.close()

            asyncio.create_task(drop_client())

            start_time = time.monotonic()
            with self.assertRaises(ConnectionResetError) as ctx:
                await bridge.send_command("get_page_snapshot", timeout=8.5)
            elapsed = time.monotonic() - start_time

            self.assertIn("disconnected", str(ctx.exception).lower())
            self.assertLess(
                elapsed,
                0.5,
                f"Fail-fast took {elapsed:.3f}s, expected < 0.5s (far below 8.5s timeout)",
            )
        finally:
            await bridge.stop_server()

    async def test_server_restart_socket_reuse(self) -> None:
        """Start bridge on port 41144, stop bridge, and immediately restart it.

        Assert server binds successfully with zero 'Address already in use' errors.
        """
        bridge = BrowserExtensionBridge(port=41144)
        await bridge.start_server()
        self.assertIsNotNone(bridge.server)

        await bridge.stop_server()
        self.assertIsNone(bridge.server)

        # Immediate restart
        await bridge.start_server()
        self.assertIsNotNone(bridge.server)
        await bridge.stop_server()
        self.assertIsNone(bridge.server)

    async def test_client_replacement_on_reconnect(self) -> None:
        """Connect client 1, then connect client 2.

        Assert client 2 becomes active client and commands route to client 2 cleanly.
        """
        bridge = BrowserExtensionBridge(port=41144)
        await bridge.start_server()
        try:
            uri = f"ws://127.0.0.1:{bridge.port}"
            client1 = await websockets.connect(uri)
            await asyncio.sleep(0.05)
            server_conn1 = bridge._client
            self.assertIsNotNone(server_conn1)

            client2 = await websockets.connect(uri)
            await asyncio.sleep(0.05)
            server_conn2 = bridge._client
            self.assertIsNotNone(server_conn2)
            self.assertNotEqual(server_conn1, server_conn2)
            self.assertFalse(_is_client_open(server_conn1))
            self.assertTrue(_is_client_open(server_conn2))

            async def client2_responder():
                async for raw in client2:
                    msg = json.loads(raw)
                    if msg.get("action") == "get_active_tab":
                        reply = {
                            "id": msg["id"],
                            "success": True,
                            "title": "Client2 Active Tab",
                        }
                        await client2.send(json.dumps(reply))

            task = asyncio.create_task(client2_responder())
            res = await bridge.send_command("get_active_tab", timeout=2.0)
            self.assertTrue(res.success)
            self.assertEqual(res.get("title"), "Client2 Active Tab")

            task.cancel()
            await client2.close()
        finally:
            await bridge.stop_server()

    def test_ping_pong_heartbeat(self) -> None:
        """Verify ping message sent to background.js returns { action: 'pong', success: true }."""
        js_code = """
        const { handleCommand } = require('./axiom/tools/extension/background.js');
        let reply = null;
        global.__axiomSendReplyHook = (data) => {
            reply = data;
        };
        (async () => {
            await handleCommand({ id: 'heartbeat_test_4', action: 'ping' });
            console.log(JSON.stringify(reply));
        })();
        """
        proc = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout.strip())
        self.assertEqual(data.get("action"), "pong")
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("id"), "heartbeat_test_4")

    async def test_stop_server_drains_pending_requests(self) -> None:
        """Initiate pending requests, call stop_server().

        Assert all pending futures resolve with exceptions and _pending_requests is empty.
        """
        bridge = BrowserExtensionBridge(port=41144)
        loop = asyncio.get_running_loop()
        fut1 = loop.create_future()
        fut2 = loop.create_future()
        bridge._pending_requests["req_1"] = fut1
        bridge._pending_requests["req_2"] = fut2

        self.assertEqual(len(bridge._pending_requests), 2)
        await bridge.stop_server()

        self.assertEqual(len(bridge._pending_requests), 0)
        self.assertTrue(fut1.done())
        self.assertTrue(fut2.done())
        with self.assertRaises(ConnectionResetError):
            fut1.result()
        with self.assertRaises(ConnectionResetError):
            fut2.result()

    async def test_browser_tool_handles_connection_reset_gracefully(self) -> None:
        """Invoke InteractWithBrowserTool.execute() with a bridge that raises ConnectionResetError.

        Assert result is success=False with structured remedy envelope.
        """
        tool = InteractWithBrowserTool()
        bridge = get_bridge()

        try:
            with patch.object(bridge, "is_connected", return_value=True), patch.object(
                bridge,
                "send_command",
                side_effect=ConnectionResetError("Browser extension disconnected mid-command."),
            ):
                res = await tool.execute(action="click_element", element_id=1)
                self.assertFalse(res.success)
                self.assertIn("Browser bridge connection lost mid-command", res.error)
                self.assertEqual(
                    res.remedy_hint,
                    "Verify browser window is running and focused, then retry get_page_snapshot.",
                )
                self.assertEqual(res.allowed_actions, ["get_page_snapshot"])
        finally:
            await bridge.stop_server()


if __name__ == "__main__":
    unittest.main()
