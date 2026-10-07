"""Test suite for Closed-Loop Fallback & Error Escalation State Machine (Phase 2).

Covers:
1. Simulated click_element & fill_element failure returns structured recovery envelope.
2. Simulated switch_tab failure returns structured recovery envelope.
3. Orchestrator automatically ingests recovery hint and rejects conversational tutorial prose,
   retrying and dispatching get_page_snapshot.
4. Orchestrator handles switch_tab failure and routes recovery to open_tab/list_tabs.
5. ToolResult recovery envelope contract & serialization.
"""

import asyncio
import contextlib
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from axiom.agents.native_orchestrator import NativeOrchestrator
from axiom.tools.browser_cdp import InteractWithBrowserTool
from axiom.tools.browser_extension import BrowserResult
from axiom.tools.core import ToolResult


class TestErrorEscalation(unittest.IsolatedAsyncioTestCase):
    def test_tool_result_envelope_contract(self):
        """Test ToolResult supports structured error metadata and recovery envelope."""
        res = ToolResult(
            success=False,
            error="Element ID 42 not found on page.",
            remedy_hint="Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
            allowed_actions=["get_page_snapshot", "scroll_page"],
        )
        self.assertFalse(res.success)
        self.assertEqual(res.error, "Element ID 42 not found on page.")
        self.assertEqual(
            res.remedy_hint,
            "Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
        )
        self.assertEqual(res.allowed_actions, ["get_page_snapshot", "scroll_page"])

        envelope = res.to_dict(
            tool="interact_with_browser",
            arguments={"action": "click_element", "element_id": 42},
        )
        self.assertFalse(envelope["success"])
        self.assertEqual(envelope["error"], "Element ID 42 not found on page.")
        self.assertEqual(
            envelope["remedy_hint"],
            "Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
        )
        self.assertEqual(envelope["allowed_actions"], ["get_page_snapshot", "scroll_page"])
        self.assertIn("result", envelope)
        self.assertEqual(
            envelope["result"]["remedy_hint"],
            "Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
        )

    async def test_simulated_click_and_fill_element_failure_envelope(self):
        """Test simulated click_element and fill_element failure returns structured recovery envelope."""
        tool = InteractWithBrowserTool()

        with patch("axiom.tools.browser_extension.get_bridge") as mock_get_bridge:
            mock_bridge = MagicMock()
            mock_bridge.is_connected.return_value = True
            mock_bridge.server = object()
            mock_bridge.ensure_server = AsyncMock()

            # 1. click_element failure
            mock_bridge.send_command = AsyncMock(
                return_value=BrowserResult({
                    "success": False,
                    "action": "click_element",
                    "error": "Element not found for id #42",
                })
            )
            mock_get_bridge.return_value = mock_bridge

            res_click = await tool.execute({"action": "click_element", "element_id": 42})
            self.assertFalse(res_click.success)
            self.assertIn("Element ID 42 not found on page.", res_click.error)
            self.assertEqual(
                res_click.remedy_hint,
                "Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
            )
            self.assertEqual(res_click.allowed_actions, ["get_page_snapshot", "scroll_page"])

            envelope_click = res_click.to_dict("interact_with_browser", {"action": "click_element", "element_id": 42})
            self.assertFalse(envelope_click["success"])
            self.assertIn("remedy_hint", envelope_click)

            # 2. fill_element failure
            mock_bridge.send_command = AsyncMock(
                return_value=BrowserResult({
                    "success": False,
                    "action": "fill_element",
                    "error": "Element not found for id #99",
                })
            )

            res_fill = await tool.execute({"action": "fill_element", "element_id": 99, "text": "axiom"})
            self.assertFalse(res_fill.success)
            self.assertIn("Element ID 99 not found on page.", res_fill.error)
            self.assertEqual(
                res_fill.remedy_hint,
                "Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
            )
            self.assertEqual(res_fill.allowed_actions, ["get_page_snapshot", "scroll_page"])

    async def test_simulated_switch_tab_failure_envelope(self):
        """Test simulated switch_tab failure returns open_tab/list_tabs recovery envelope."""
        tool = InteractWithBrowserTool()

        with patch("axiom.tools.browser_extension.get_bridge") as mock_get_bridge:
            mock_bridge = MagicMock()
            mock_bridge.is_connected.return_value = True
            mock_bridge.server = object()
            mock_bridge.ensure_server = AsyncMock()

            mock_bridge.send_command = AsyncMock(
                return_value=BrowserResult({
                    "success": False,
                    "action": "switch_tab",
                    "error": "No open tab matching query: 'github'",
                    "open_tabs": [{"id": 1, "title": "Google", "url": "https://google.com"}],
                })
            )
            mock_get_bridge.return_value = mock_bridge

            res_switch = await tool.execute({"action": "switch_tab", "query": "github"})
            self.assertFalse(res_switch.success)
            self.assertIn("No open tab matching query: 'github'", res_switch.error)
            self.assertEqual(
                res_switch.remedy_hint,
                "Call list_tabs to see valid targets, or open_tab with url='github' to launch it.",
            )
            self.assertEqual(res_switch.allowed_actions, ["list_tabs", "open_tab"])

    async def test_orchestrator_ingests_recovery_hint_and_dispatches_snapshot(self):
        """Test orchestrator ingests recovery hint, rejects conversational advisory prose,
        and automatically dispatches get_page_snapshot recovery tool.
        """
        orch = NativeOrchestrator()
        executed_tools = []

        async def mock_execute(name, **kwargs):
            executed_tools.append((name, kwargs))
            action = kwargs.get("action")
            if action == "click_element":
                return ToolResult(
                    success=False,
                    error="Element ID 42 not found on page.",
                    remedy_hint="Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
                    allowed_actions=["get_page_snapshot", "scroll_page"],
                )
            elif action == "get_page_snapshot":
                return {
                    "elements": [
                        {"element_id": 1, "tag": "button", "text": "Submit"},
                        {"element_id": 2, "tag": "a", "text": "Learn more"},
                    ]
                }
            return {"status": "ok"}

        turn_counter = 0

        @contextlib.asynccontextmanager
        async def mock_stream_client(method, url, **kwargs):
            nonlocal turn_counter
            turn_counter += 1
            resp = AsyncMock()
            resp.status_code = 200

            # Turn 1: Model calls click_element with invalid id 42
            if turn_counter == 1:
                lines = [
                    'data: {"choices": [{"delta": {"content": "{\\"name\\": \\"interact_with_browser\\", \\"arguments\\": {\\"action\\": \\"click_element\\", \\"element_id\\": 42}}"}}]}',
                    "data: [DONE]",
                ]
            # Turn 2: Model attempts conversational tutorial/apology prose instead of an actuator tool call
            elif turn_counter == 2:
                lines = [
                    'data: {"choices": [{"delta": {"content": "I apologize, element 42 was not found on the page. Please inspect the DOM manually or refresh the browser tab."}}]}',
                    "data: [DONE]",
                ]
            # Turn 3 (Retry after Anti-Consultant rejection): Model calls get_page_snapshot
            elif turn_counter == 3:
                lines = [
                    'data: {"choices": [{"delta": {"content": "{\\"name\\": \\"interact_with_browser\\", \\"arguments\\": {\\"action\\": \\"get_page_snapshot\\"}}"}}]}',
                    "data: [DONE]",
                ]
            # Turn 4: Final completion message
            else:
                lines = [
                    'data: {"choices": [{"delta": {"content": "I refreshed the page snapshot and found updated elements 1 and 2."}}]}',
                    "data: [DONE]",
                ]

            async def aiter_lines():
                for l in lines:
                    yield l

            resp.aiter_lines = aiter_lines
            yield resp

        payload = {
            "messages": [{"role": "user", "content": "Click button 42 on the active web page"}],
        }

        with patch("axiom.agents.native_orchestrator.execute_tool", side_effect=mock_execute), \
             patch.object(orch, "get_active_window_context", return_value=None), \
             patch("httpx.AsyncClient") as mock_client:

            mock_client.return_value.__aenter__.return_value.stream = mock_stream_client
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()

            streamed_content = []
            async for chunk in orch.generate_stream(payload):
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        streamed_content.append(delta["content"])

            final_text = "".join(streamed_content)

            # 1. Assert exactly 2 tools were executed: click_element, then recovery get_page_snapshot
            self.assertEqual(len(executed_tools), 2)
            self.assertEqual(executed_tools[0][1]["action"], "click_element")
            self.assertEqual(executed_tools[0][1]["element_id"], 42)
            self.assertEqual(executed_tools[1][1]["action"], "get_page_snapshot")

            # 2. Anti-consultant rule: conversational advisory prose was rejected and NEVER streamed to user
            self.assertNotIn("I apologize, element 42 was not found", final_text)
            self.assertIn("I refreshed the page snapshot and found updated elements", final_text)

            # 3. History verification: message history contains the structured recovery hint
            tool_messages = [m for m in payload["messages"] if m.get("role") == "tool"]
            self.assertGreaterEqual(len(tool_messages), 1)
            error_msg = tool_messages[0]
            self.assertIn("[Tool Error]: Element ID 42 not found on page.", error_msg["content"])
            self.assertIn(
                "Recovery Hint: Call get_page_snapshot to refresh element IDs, or scroll_page down if the element is below the viewport.",
                error_msg["content"],
            )

    async def test_orchestrator_handles_switch_tab_failure_and_prompts_open_tab(self):
        """Test orchestrator handles switch_tab failure, rejects advisory prose,
        and executes open_tab recovery tool.
        """
        orch = NativeOrchestrator()
        executed_tools = []

        async def mock_execute(name, **kwargs):
            executed_tools.append((name, kwargs))
            action = kwargs.get("action")
            if action == "switch_tab":
                return ToolResult(
                    success=False,
                    error="No open tab matching query: 'reddit'",
                    remedy_hint="Call list_tabs to see valid targets, or open_tab with url='https://reddit.com' to launch it.",
                    allowed_actions=["list_tabs", "open_tab"],
                )
            elif action == "open_tab":
                return {"status": "success", "tab_id": 202, "url": kwargs.get("url")}
            return {"status": "ok"}

        turn_counter = 0

        @contextlib.asynccontextmanager
        async def mock_stream_client(method, url, **kwargs):
            nonlocal turn_counter
            turn_counter += 1
            resp = AsyncMock()
            resp.status_code = 200

            # Turn 1: Model calls switch_tab
            if turn_counter == 1:
                lines = [
                    'data: {"choices": [{"delta": {"content": "{\\"name\\": \\"interact_with_browser\\", \\"arguments\\": {\\"action\\": \\"switch_tab\\", \\"query\\": \\"reddit\\"}}"}}]}',
                    "data: [DONE]",
                ]
            # Turn 2: Model attempts conversational tutorial prose
            elif turn_counter == 2:
                lines = [
                    'data: {"choices": [{"delta": {"content": "No reddit tab was found. You should open Firefox and navigate to reddit.com."}}]}',
                    "data: [DONE]",
                ]
            # Turn 3 (Retry after Anti-Consultant rejection): Model calls open_tab
            elif turn_counter == 3:
                lines = [
                    'data: {"choices": [{"delta": {"content": "{\\"name\\": \\"interact_with_browser\\", \\"arguments\\": {\\"action\\": \\"open_tab\\", \\"url\\": \\"https://reddit.com\\"}}"}}]}',
                    "data: [DONE]",
                ]
            # Turn 4: Final completion message
            else:
                lines = [
                    'data: {"choices": [{"delta": {"content": "I opened reddit.com in a new tab."}}]}',
                    "data: [DONE]",
                ]

            async def aiter_lines():
                for l in lines:
                    yield l

            resp.aiter_lines = aiter_lines
            yield resp

        payload = {
            "messages": [{"role": "user", "content": "Switch to my reddit tab"}],
        }

        with patch("axiom.agents.native_orchestrator.execute_tool", side_effect=mock_execute), \
             patch.object(orch, "get_active_window_context", return_value=None), \
             patch("httpx.AsyncClient") as mock_client:

            mock_client.return_value.__aenter__.return_value.stream = mock_stream_client
            mock_client.return_value.__aenter__.return_value.post = AsyncMock()

            streamed_content = []
            async for chunk in orch.generate_stream(payload):
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        streamed_content.append(delta["content"])

            final_text = "".join(streamed_content)

            self.assertEqual(len(executed_tools), 2)
            self.assertEqual(executed_tools[0][1]["action"], "switch_tab")
            self.assertEqual(executed_tools[1][1]["action"], "open_tab")
            self.assertEqual(executed_tools[1][1]["url"], "https://reddit.com")

            self.assertNotIn("No reddit tab was found. You should open Firefox", final_text)
            self.assertIn("I opened reddit.com in a new tab.", final_text)

            tool_messages = [m for m in payload["messages"] if m.get("role") == "tool"]
            self.assertGreaterEqual(len(tool_messages), 1)
            self.assertIn("Recovery Hint: Call list_tabs to see valid targets", tool_messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
