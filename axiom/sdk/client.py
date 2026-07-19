"""AXIOM SDK Client.

Provides async and sync clients for integrating with the AXIOM JSON-RPC daemon.
"""

import asyncio
import json
import logging
import uuid
import threading
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

from axiom.sdk.models import (
    JsonRpcRequest,
    JsonRpcResponse,
    PromptRequest,
    TelemetryPayload,
)

logger = logging.getLogger(__name__)


class AxiomClient:
    """Async Client for communicating with the AXIOM JSON-RPC daemon."""

    def __init__(self, socket_path: Optional[str] = None, token_path: Optional[str] = None):
        self.socket_path = Path(socket_path or Path.home() / ".axiom" / "axiom.sock")
        self.token_path = Path(token_path or Path.home() / ".axiom" / "daemon.token")
        
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._auth_token: Optional[str] = None
        
        # Track pending requests by ID
        self._pending_requests: Dict[str, asyncio.Future] = {}
        
        # Track active subscriptions by topic
        self._subscriptions: Dict[str, asyncio.Queue] = {}
        
        # Read loop task
        self._read_task: Optional[asyncio.Task] = None
        
    def _read_token(self) -> str:
        """Reads the authentication token from disk."""
        if not self.token_path.exists():
            # For testing without a token file, we can fall back or raise
            return "dev-token-fallback"
        return self.token_path.read_text().strip()

    async def connect(self) -> None:
        """Connect to the daemon's Unix Domain Socket."""
        self._auth_token = self._read_token()
        self._reader, self._writer = await asyncio.open_unix_connection(str(self.socket_path))
        
        # Start background read loop
        self._read_task = asyncio.create_task(self._read_loop())
        logger.debug("Connected to AXIOM daemon.")

    async def disconnect(self) -> None:
        """Disconnect from the daemon."""
        if self._read_task:
            self._read_task.cancel()
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def _read_loop(self) -> None:
        """Background loop reading JSON-RPC responses and events from the socket."""
        try:
            while True:
                if not self._reader:
                    break
                    
                line = await self._reader.readline()
                if not line:
                    logger.debug("Socket closed by server.")
                    break
                    
                try:
                    payload = json.loads(line.decode().strip())
                except json.JSONDecodeError:
                    continue
                    
                # Is it a response to a request?
                if "id" in payload and str(payload["id"]) in self._pending_requests:
                    req_id = str(payload["id"])
                    future = self._pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(payload)
                # Is it an event subscription message?
                elif "method" in payload and payload["method"] == "event.bus.published":
                    event_data = payload.get("params", {})
                    topic = event_data.get("event_type", event_data.get("topic"))
                    
                    for sub_topic, queue in self._subscriptions.items():
                        if topic == sub_topic or sub_topic == "*":
                            await queue.put(event_data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Read loop encountered error: {e}")
        finally:
            # Clear pending requests
            for fut in self._pending_requests.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("Socket disconnected"))
            self._pending_requests.clear()

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self._writer:
            await self.connect()
            
        req_id = str(uuid.uuid4())
        
        full_params = params or {}
        if "token" not in full_params and self._auth_token:
            full_params["token"] = self._auth_token
            
        request = JsonRpcRequest(id=req_id, method=method, params=full_params)
        
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[req_id] = future
        
        payload_bytes = request.model_dump_json(exclude_none=True).encode() + b"\n"
        # self._writer guarantees it won't be None because we await connect()
        self._writer.write(payload_bytes) # type: ignore
        await self._writer.drain() # type: ignore
        
        response_dict = await future
        response = JsonRpcResponse(**response_dict)
        
        if response.error:
            raise RuntimeError(f"JSON-RPC Error {response.error.code}: {response.error.message}")
            
        return response.result

    async def prompt(self, text: str, session_id: Optional[str] = None) -> Any:
        """Submit a prompt to AXIOM."""
        req = PromptRequest(text=text, session_id=session_id)
        return await self._send_request("prompt.submit", req.model_dump(exclude_none=True))

    async def get_status(self) -> TelemetryPayload:
        """Get the current telemetry status of AXIOM."""
        result = await self._send_request("system.status")
        if isinstance(result, dict):
            return TelemetryPayload(**result)
        # Best effort
        return result

    async def subscribe(self, topic: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to an EventBus topic and yield events. Use '*' for all events."""
        if not self._writer:
            await self.connect()
            
        await self._send_request("event.subscribe", {"topic": topic})
        
        queue = asyncio.Queue()
        self._subscriptions[topic] = queue
        
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            if topic in self._subscriptions:
                del self._subscriptions[topic]
            try:
                await self._send_request("event.unsubscribe", {"topic": topic})
            except Exception:
                pass


class SyncAxiomClient:
    """Synchronous wrapper for AxiomClient."""

    def __init__(self, socket_path: Optional[str] = None, token_path: Optional[str] = None):
        self._socket_path = socket_path
        self._token_path = token_path

    def prompt(self, text: str, session_id: Optional[str] = None) -> Any:
        return asyncio.run(self._prompt_async(text, session_id))

    async def _prompt_async(self, text: str, session_id: Optional[str]):
        client = AxiomClient(self._socket_path, self._token_path)
        try:
            return await client.prompt(text, session_id)
        finally:
            await client.disconnect()

    def get_status(self) -> TelemetryPayload:
        return asyncio.run(self._get_status_async())

    async def _get_status_async(self):
        client = AxiomClient(self._socket_path, self._token_path)
        try:
            return await client.get_status()
        finally:
            await client.disconnect()

    def subscribe(self, topic: str):
        """Synchronous generator for subscribing to events."""
        queue = []
        condition = threading.Condition()
        closed = False
        
        def run_loop():
            nonlocal closed
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def consume():
                client = AxiomClient(self._socket_path, self._token_path)
                try:
                    async for event in client.subscribe(topic):
                        with condition:
                            queue.append(event)
                            condition.notify()
                except Exception:
                    pass
                finally:
                    await client.disconnect()
                    with condition:
                        closed = True
                        condition.notify()
                        
            try:
                loop.run_until_complete(consume())
            finally:
                loop.close()
                
        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        
        while True:
            with condition:
                while not queue and not closed:
                    condition.wait()
                if queue:
                    yield queue.pop(0)
                elif closed:
                    break
