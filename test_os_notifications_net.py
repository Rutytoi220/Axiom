"""Test suite for SendDesktopNotificationTool and InspectNetworkTool."""

import unittest
from axiom.tools.os_desktop import SendDesktopNotificationTool
from axiom.tools.os_system import InspectNetworkTool


class TestNotificationsAndNetwork(unittest.IsolatedAsyncioTestCase):
    async def test_send_desktop_notification_success(self):
        tool = SendDesktopNotificationTool()
        result = await tool.execute({
            "title": "AXIOM Test",
            "message": "Integration test notification message",
            "urgency": "low",
        })
        self.assertTrue(result.success)
        self.assertIsNotNone(result.output)
        self.assertTrue(result.output.get("delivered"))
        self.assertEqual(result.output.get("urgency"), "low")

    async def test_send_desktop_notification_missing_message(self):
        tool = SendDesktopNotificationTool()
        result = await tool.execute({
            "title": "AXIOM Test",
            "message": "",
        })
        self.assertFalse(result.success)
        self.assertIn("required", result.error.lower())

    async def test_inspect_network(self):
        tool = InspectNetworkTool()
        result = await tool.execute({
            "include_tailscale": True,
            "include_dns": True,
        })
        self.assertTrue(result.success)
        self.assertIsNotNone(result.output)
        
        data = result.output
        self.assertIn("gateway", data)
        self.assertIn("interfaces", data)
        self.assertIsInstance(data["interfaces"], list)
        self.assertGreater(len(data["interfaces"]), 0)

        # Tailscale diagnostics
        self.assertIn("tailscale", data)
        tailscale = data["tailscale"]
        self.assertIn("tailscale_active", tailscale)

        # DNS diagnostics
        self.assertIn("dns", data)
        dns = data["dns"]
        self.assertIn("target", dns)
        self.assertIn("latency_ms", dns)


if __name__ == "__main__":
    unittest.main()
