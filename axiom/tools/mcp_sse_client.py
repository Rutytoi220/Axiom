import asyncio
import json
import logging
from typing import Callable, Optional, Dict, Any
from urllib.parse import urljoin
import httpx

logger = logging.getLogger(__name__)

class MCPSSEClient:
    """Async Client for Model Context Protocol over Server-Sent Events (SSE)."""

    def __init__(self, url: str, name: str, on_message: Callable[[Dict[str, Any]], None], on_disconnect: Callable[[], None] = None):
        self.url = url
        self.name = name
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.post_url: Optional[str] = None
        self._running = False
        self._client = httpx.AsyncClient(timeout=None)
        self._task: Optional[asyncio.Task] = None

    async def connect(self):
        """Establish the SSE connection and listen for events."""
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        # Wait until endpoint is discovered or disconnected
        for _ in range(50):
            if self.post_url or not self._running:
                break
            await asyncio.sleep(0.1)
            
        if not self.post_url:
            self.stop()
            raise ConnectionError(f"Failed to receive POST endpoint from SSE server '{self.name}' at {self.url}")

    async def _listen_loop(self):
        backoff = 1.0
        while self._running:
            try:
                logger.info(f"Connecting to SSE endpoint for MCP server '{self.name}': {self.url}")
                async with self._client.stream("GET", self.url, headers={"Accept": "text/event-stream"}) as response:
                    if response.status_code != 200:
                        logger.error(f"Failed to connect to SSE {self.url}: {response.status_code}")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60.0)
                        continue
                    
                    backoff = 1.0 # reset backoff on successful connect
                    
                    event_type = "message"
                    data_buffer = []
                    
                    async for line in response.aiter_lines():
                        if not self._running:
                            break
                            
                        # Handle SSE line protocol
                        if not line:
                            # Empty line means dispatch the event
                            if data_buffer:
                                data_str = "\n".join(data_buffer)
                                self._dispatch_event(event_type, data_str)
                                data_buffer.clear()
                            event_type = "message"
                            continue
                            
                        if line.startswith("event:"):
                            event_type = line[6:].strip()
                        elif line.startswith("data:"):
                            data_buffer.append(line[5:].strip())
                            
            except httpx.RequestError as e:
                logger.warning(f"SSE connection error to '{self.name}': {e}")
            except Exception as e:
                logger.exception(f"Unexpected error in SSE loop for '{self.name}': {e}")
                
            if self._running:
                logger.info(f"Reconnecting to '{self.name}' in {backoff} seconds...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                
        if self.on_disconnect:
            self.on_disconnect()

    def _dispatch_event(self, event_type: str, data: str):
        if event_type == "endpoint":
            # The server sends the endpoint URI to be used for POST requests
            if data.startswith("http://") or data.startswith("https://"):
                self.post_url = data
            else:
                self.post_url = urljoin(self.url, data)
            logger.info(f"Discovered POST endpoint for '{self.name}': {self.post_url}")
            return
            
        if event_type == "message":
            try:
                payload = json.loads(data)
                self.on_message(payload)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from SSE message: {data}")

    async def send_request(self, request: Dict[str, Any]) -> None:
        """Send a JSON-RPC request to the discovered POST endpoint."""
        if not self.post_url:
            raise ConnectionError("POST endpoint not yet discovered.")
        
        try:
            response = await self._client.post(self.post_url, json=request)
            response.raise_for_status()
            
            # Note: MCP servers over HTTP typically return empty responses and push responses via SSE,
            # but if they return the JSON-RPC response immediately via POST response, we handle it here.
            if response.content:
                try:
                    payload = response.json()
                    if payload:
                        self.on_message(payload)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Failed to send request to '{self.name}': {e}")
            raise

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            
    async def cleanup(self):
        self.stop()
        await self._client.aclose()
