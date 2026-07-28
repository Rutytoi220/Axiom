import asyncio
import json
import logging
import websockets
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class MeshClient:
    """Client to connect to LAN Mesh worker nodes and dispatch tasks."""
    
    def __init__(self, host: str, port: int = 9412):
        self.uri = f"ws://{host}:{port}"
        self.websocket = None
        self.node_profile = None
        
    async def connect(self) -> bool:
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info(f"Connected to MeshNode at {self.uri}")
            
            # Wait for registration profile
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            data = json.loads(msg)
            if data.get("type") == "registration":
                self.node_profile = data.get("payload")
                logger.info(f"Registered MeshNode: {self.node_profile.get('hostname')}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MeshNode {self.uri}: {e}")
            return False
            
    async def dispatch_task(self, task_id: str, prompt: str) -> Optional[str]:
        if not self.websocket:
            return None
            
        try:
            await self.websocket.send(json.dumps({
                "type": "task_dispatch",
                "task_id": task_id,
                "prompt": prompt
            }))
            
            # Wait for result
            while True:
                msg = await self.websocket.recv()
                data = json.loads(msg)
                if data.get("type") == "task_result" and data.get("task_id") == task_id:
                    return data.get("result")
                    
        except Exception as e:
            logger.error(f"Failed to dispatch task {task_id}: {e}")
            return None
            
    async def close(self):
        if self.websocket:
            await self.websocket.close()
