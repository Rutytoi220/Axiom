"""Semantic Browser CDP Bridge Tool for AXIOM.

Provides deterministic sub-10ms browser automation via Chrome DevTools Protocol (CDP) WebSocket.
Compatible with Chrome, Chromium, Brave, Zen Browser, and Electron apps.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
import websockets

from axiom.tools.core import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

DEFAULT_CDP_PORTS = [9222, 9223, 9224]


class InteractWithBrowserTool(BaseTool):
    """Semantic browser automation using the Chrome DevTools Protocol (CDP)."""

    def __init__(self):
        super().__init__(
            tool_id="interact_with_browser",
            name="interact_with_browser",
            description=(
                "Tier 2 Semantic UI Automation: Sub-10ms browser interaction via Chrome DevTools Protocol (CDP). "
                "Deterministically click, type, and evaluate JavaScript in web browsers (Zen, Chrome, Brave) "
                "and Electron apps. Actions: 'click', 'type', 'evaluate', 'get_content', 'list_tabs'."
            ),
        )
        self.parameters = [
            ToolParameter(
                name="action",
                type="string",
                description="The browser action: 'click', 'type', 'evaluate', 'get_content', 'list_tabs'.",
                required=True,
            ),
            ToolParameter(
                name="selector",
                type="string",
                description="CSS selector of the DOM element to interact with (e.g. 'button.submit', '#search-input', 'a[href=\"/login\"]').",
                required=False,
                default="",
            ),
            ToolParameter(
                name="text",
                type="string",
                description="Text to type into the targeted DOM element.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="expression",
                type="string",
                description="JavaScript code expression to evaluate in the page context.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="port",
                type="integer",
                description="Remote debugging port (defaults to 9222, auto-discovers 9222-9224).",
                required=False,
                default=9222,
            ),
            ToolParameter(
                name="tab_id",
                type="string",
                description="Optional tab ID or URL filter to select a specific browser tab.",
                required=False,
                default="",
            ),
        ]

    async def _discover_tab(self, requested_port: int, tab_filter: str = "") -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Finds active CDP WebSocket debugger URL across candidate ports."""
        ports_to_try = [requested_port] + [p for p in DEFAULT_CDP_PORTS if p != requested_port]
        last_error = ""

        async with httpx.AsyncClient(timeout=1.5) as client:
            for port in ports_to_try:
                url = f"http://127.0.0.1:{port}/json"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        targets: List[dict] = resp.json()
                        page_targets = [t for t in targets if t.get("type") == "page"]
                        if not page_targets:
                            page_targets = targets

                        if tab_filter:
                            matching = [
                                t for t in page_targets
                                if tab_filter.lower() in t.get("url", "").lower()
                                or tab_filter.lower() in t.get("title", "").lower()
                                or tab_filter == t.get("id")
                            ]
                            if matching:
                                chosen = matching[0]
                                return chosen.get("webSocketDebuggerUrl"), chosen, None

                        if page_targets:
                            chosen = page_targets[0]
                            return chosen.get("webSocketDebuggerUrl"), chosen, None
                except Exception as e:
                    last_error = str(e)
                    continue

        return None, None, f"Could not connect to browser CDP port ({', '.join(str(p) for p in ports_to_try)}). {last_error}"

    async def _send_cdp(self, ws_url: str, method: str, params: Optional[dict] = None) -> dict:
        """Connects to CDP WebSocket and dispatches a JSON-RPC command."""
        req_id = 1
        payload = {
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        async with websockets.connect(ws_url, ping_interval=None, close_timeout=2.0) as ws:
            await ws.send(json.dumps(payload))
            while True:
                raw_resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                resp = json.loads(raw_resp)
                if resp.get("id") == req_id:
                    return resp

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        action = params.get("action", "").strip().lower()
        selector = str(params.get("selector", "") or "").strip()
        text = str(params.get("text", "") or "")
        expression = str(params.get("expression", "") or "").strip()
        tab_id = str(params.get("tab_id", "") or "").strip()

        # Check if caller explicitly requested a specific CDP port (e.g. port=9222 in tests)
        explicit_port = params.get("port")
        has_explicit_port = explicit_port is not None

        # Tier 2 WebExtension Bridge is primary for browser automation.
        # Unless the caller explicitly passed a port parameter, route strictly through the extension bridge.
        if not has_explicit_port:
            try:
                from axiom.tools.browser_extension import get_bridge
                bridge = get_bridge()
                if bridge.server is None:
                    try:
                        await bridge.ensure_server()
                    except Exception:
                        pass

                if bridge.is_connected():
                    ext_params = {k: v for k, v in params.items() if k != "action"}
                    ext_res = await bridge.send_command(action, **ext_params)
                    if ext_res.success:
                        return ToolResult(True, output=ext_res.output or ext_res)
                    return ToolResult(False, error=ext_res.error or "Extension command failed")
                else:
                    return ToolResult(
                        False,
                        error=(
                            "No browser extension connected on ws://127.0.0.1:41144. "
                            "Ensure the AXIOM extension is loaded in Zen Browser (about:debugging) or Chromium. "
                            "Do not ask for --remote-debugging-port flags."
                        ),
                    )
            except Exception as exc:
                return ToolResult(
                    False,
                    error=(
                        f"Browser extension bridge error: {exc}. "
                        "No browser extension connected on ws://127.0.0.1:41144. "
                        "Ensure the AXIOM extension is loaded in Zen Browser (about:debugging) or Chromium. "
                        "Do not ask for --remote-debugging-port flags."
                    ),
                )

        # Legacy / Explicit CDP path (when caller explicitly specifies a port, e.g. port=9222)
        port = int(explicit_port or 9222)

        # Handle list_tabs discovery
        if action in ("list_tabs", "tabs"):
            ports_to_try = [port] + [p for p in DEFAULT_CDP_PORTS if p != port]
            async with httpx.AsyncClient(timeout=1.5) as client:
                for p in ports_to_try:
                    try:
                        resp = await client.get(f"http://127.0.0.1:{p}/json")
                        if resp.status_code == 200:
                            targets = resp.json()
                            summary = [
                                {
                                    "id": t.get("id"),
                                    "title": t.get("title"),
                                    "url": t.get("url"),
                                    "type": t.get("type"),
                                }
                                for t in targets
                            ]
                            return ToolResult(True, output={"port": p, "tabs": summary})
                    except Exception:
                        continue
            return ToolResult(
                False,
                error="No running browser found on CDP debug ports (9222, 9223). Start browser with '--remote-debugging-port=9222'.",
            )

        # Discover active page WebSocket
        ws_url, page_info, err = await self._discover_tab(port, tab_id)
        if not ws_url or err:
            return ToolResult(
                False,
                error=(
                    "CDP Connection Failed: Browser is not running with remote debugging enabled. "
                    "Ensure Zen Browser, Chrome, or Brave is launched with '--remote-debugging-port=9222'."
                ),
            )

        try:
            if action == "click":
                if not selector:
                    return ToolResult(False, error="CSS selector is required for 'click' action.")

                js_click = f"""
                (() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return {{ success: false, error: "Element not found for selector: " + {json.dumps(selector)} }};
                    el.scrollIntoView({{ block: "center", inline: "center", behavior: "instant" }});
                    el.focus();
                    el.click();
                    el.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window }}));
                    el.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window }}));
                    return {{
                        success: true,
                        tag: el.tagName,
                        text: (el.innerText || el.value || "").slice(0, 100),
                        selector: {json.dumps(selector)}
                    }};
                }})()
                """
                resp = await self._send_cdp(ws_url, "Runtime.evaluate", {
                    "expression": js_click,
                    "returnByValue": True,
                    "awaitPromise": True,
                })
                result = resp.get("result", {}).get("result", {}).get("value", {})
                if isinstance(result, dict) and not result.get("success", False):
                    return ToolResult(False, error=result.get("error", "Click failed."))
                return ToolResult(True, output=result)

            elif action == "type":
                if not selector:
                    return ToolResult(False, error="CSS selector is required for 'type' action.")

                js_type = f"""
                (() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return {{ success: false, error: "Element not found for selector: " + {json.dumps(selector)} }};
                    el.scrollIntoView({{ block: "center", inline: "center", behavior: "instant" }});
                    el.focus();
                    if ('value' in el) {{
                        el.value = {json.dumps(text)};
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }} else {{
                        el.textContent = {json.dumps(text)};
                        el.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: {json.dumps(text)} }}));
                    }}
                    return {{
                        success: true,
                        selector: {json.dumps(selector)},
                        typed: {json.dumps(text)}
                    }};
                }})()
                """
                resp = await self._send_cdp(ws_url, "Runtime.evaluate", {
                    "expression": js_type,
                    "returnByValue": True,
                    "awaitPromise": True,
                })
                result = resp.get("result", {}).get("result", {}).get("value", {})
                if isinstance(result, dict) and not result.get("success", False):
                    return ToolResult(False, error=result.get("error", "Type failed."))
                return ToolResult(True, output=result)

            elif action in ("evaluate", "js", "exec"):
                if not expression:
                    return ToolResult(False, error="JavaScript expression is required for 'evaluate' action.")

                resp = await self._send_cdp(ws_url, "Runtime.evaluate", {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                })
                res_obj = resp.get("result", {}).get("result", {})
                if "value" in res_obj:
                    return ToolResult(True, output=res_obj["value"])
                return ToolResult(True, output=res_obj)

            elif action in ("get_content", "read_page", "content"):
                js_content = """
                (() => {
                    return {
                        title: document.title,
                        url: location.href,
                        body_text: (document.body ? document.body.innerText : "").slice(0, 3000)
                    };
                })()
                """
                resp = await self._send_cdp(ws_url, "Runtime.evaluate", {
                    "expression": js_content,
                    "returnByValue": True,
                    "awaitPromise": True,
                })
                result = resp.get("result", {}).get("result", {}).get("value", {})
                return ToolResult(True, output=result)

            else:
                return ToolResult(
                    False,
                    error=f"Unknown browser action '{action}'. Supported actions: click, type, evaluate, get_content, list_tabs.",
                )

        except Exception as exc:
            logger.exception("Error executing CDP command")
            return ToolResult(False, error=f"CDP command execution error: {exc}")
