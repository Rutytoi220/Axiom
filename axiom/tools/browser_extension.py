"""AXIOM Browser Extension Local WebSocket Automation Bridge.

Provides zero-friction local browser automation via a WebSocket daemon on ws://127.0.0.1:41144.
Compatible with Zen Browser (Firefox/Gecko) and Chromium browsers running the AXIOM WebExtension.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets.server import WebSocketServer

logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_HOST = "127.0.0.1"
DEFAULT_BRIDGE_PORT = 41144


class BrowserResult(dict):
    """Dictionary subclass providing attribute-style access for tool results."""

    @property
    def success(self) -> bool:
        return bool(self.get("success", False))

    @property
    def error(self) -> Optional[str]:
        return self.get("error")

    @property
    def output(self) -> Any:
        return self.get("result") or self.get("tabs") or self.get("tab") or self.get("content")


class BrowserExtensionBridge:
    """Manages WebSocket connections from browser extensions and routes commands."""

    _instance: Optional[BrowserExtensionBridge] = None

    def __init__(self, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT):
        self.host = host
        self.port = port
        self.active_clients: Set[Any] = set()
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.server: Optional[WebSocketServer] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._lock is None:
            self._lock = asyncio.Lock()
        elif loop is not None and getattr(self._lock, "_loop", None) not in (None, loop):
            self._lock = asyncio.Lock()
        return self._lock

    @classmethod
    def get_instance(cls, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT) -> BrowserExtensionBridge:
        if cls._instance is None:
            cls._instance = cls(host=host, port=port)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def is_connected(self) -> bool:
        """Returns True if at least one browser extension is actively connected."""
        self.active_clients = {
            c for c in self.active_clients
            if getattr(c, "open", True) and not getattr(c, "closed", False)
        }
        return len(self.active_clients) > 0

    @property
    def client_count(self) -> int:
        return len(self.active_clients)

    async def _handle_client(self, websocket: Any, *args: Any) -> None:
        """Handles incoming WebSocket connection from a browser extension."""
        self.active_clients.add(websocket)
        remote = getattr(websocket, "remote_address", "client")
        logger.info("[AXIOM Extension Bridge] Browser extension connected: %s", remote)

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)

                    # Handle heartbeat ping frames from browser extension
                    msg_type = data.get("type")
                    msg_action = data.get("action")
                    if msg_type == "ping" or msg_action == "ping":
                        pong_payload = {"type": "pong", "id": data.get("id")}
                        await websocket.send(json.dumps(pong_payload))
                        logger.debug("[AXIOM Extension Bridge] Received ping from %s, replied with pong", remote)
                        print("  [Heartbeat] Extension ping received → Daemon replied pong", flush=True)
                        continue

                    msg_id = data.get("id")
                    if msg_id and msg_id in self.pending_requests:
                        future = self.pending_requests.pop(msg_id)
                        if not future.done():
                            future.set_result(data)
                except json.JSONDecodeError:
                    logger.warning("[AXIOM Extension Bridge] Received invalid JSON payload: %s", raw_message[:150])
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.active_clients.discard(websocket)
            logger.info("[AXIOM Extension Bridge] Browser extension disconnected: %s", remote)

    async def start_server(self) -> None:
        """Starts the WebSocket server on 127.0.0.1:41144."""
        async with self._get_lock():
            if self.server is not None:
                return
            try:
                self.server = await websockets.serve(
                    self._handle_client,
                    self.host,
                    self.port,
                )
                logger.info("[AXIOM Extension Bridge] Daemon listening on ws://%s:%d", self.host, self.port)
            except OSError as exc:
                logger.warning("[AXIOM Extension Bridge] Failed to bind ws://%s:%d: %s", self.host, self.port, exc)

    async def stop_server(self) -> None:
        """Closes all client connections and shuts down the server."""
        async with self._get_lock():
            for fut in self.pending_requests.values():
                if not fut.done():
                    fut.cancel()
            self.pending_requests.clear()

            for client in list(self.active_clients):
                try:
                    await client.close()
                except Exception:
                    pass
            self.active_clients.clear()

            if self.server is not None:
                self.server.close()
                await self.server.wait_closed()
                self.server = None
                logger.info("[AXIOM Extension Bridge] Daemon shut down.")

    async def ensure_server(self) -> None:
        """Ensures the daemon is listening."""
        if self.server is None:
            await self.start_server()

    async def send_command(self, action: str, timeout: float = 5.0, **kwargs: Any) -> BrowserResult:
        """Dispatches an action to the connected extension and waits for response."""
        await self.ensure_server()

        if not self.is_connected():
            return BrowserResult({
                "success": False,
                "error": (
                    f"No browser extension connected on ws://{self.host}:{self.port}. "
                    "Ensure the AXIOM extension is loaded in Zen Browser (about:debugging) or Chromium. "
                    "Do not ask for --remote-debugging-port flags."
                ),
                "port": self.port,
                "action": action,
            })

        msg_id = f"ext_{uuid.uuid4().hex[:10]}"
        kwargs.pop("action", None)
        payload = {
            "id": msg_id,
            "action": action,
            **kwargs,
        }

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self.pending_requests[msg_id] = future

        client = next(iter(self.active_clients))
        try:
            await client.send(json.dumps(payload))
        except Exception as exc:
            self.pending_requests.pop(msg_id, None)
            return BrowserResult({
                "success": False,
                "error": f"Failed to send '{action}' to browser extension: {exc}",
                "action": action,
            })

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return BrowserResult(response)
        except asyncio.TimeoutError:
            self.pending_requests.pop(msg_id, None)
            return BrowserResult({
                "success": False,
                "error": f"Command '{action}' timed out after {timeout}s awaiting extension response",
                "action": action,
            })


def get_bridge() -> BrowserExtensionBridge:
    """Returns the singleton BrowserExtensionBridge instance."""
    return BrowserExtensionBridge.get_instance()


async def interact_with_browser(
    action: str,
    query: str = "",
    selector: str = "",
    text: str = "",
    **kwargs: Any,
) -> BrowserResult:
    """Interacts with browser via local WebExtension WebSocket bridge.

    Actions:
      - list_tabs: Query list of open tabs with IDs, titles, URLs, active state.
      - switch_tab: Matches tab titles or URLs against query and switches focus.
      - click: Evaluates document.querySelector(selector).click() in active tab.
      - type: Dispatches synthetic input/typing to selector in active tab.
      - get_dom: Returns text and structure content of active tab.
    """
    bridge = get_bridge()
    cmd_args: Dict[str, Any] = dict(kwargs)
    if query:
        cmd_args["query"] = query
    if selector:
        cmd_args["selector"] = selector
    if text:
        cmd_args["text"] = text

    return await bridge.send_command(action, timeout=5.0, **cmd_args)
