import asyncio
import json
import logging
import socket
from websockets.server import serve
from axiom.core.events import EventBus

logger = logging.getLogger(__name__)

class MeshNodeServer:
    """A lightweight LAN Mesh server for P2P background task distribution."""
    
    def __init__(self, port: int = 9412, event_bus: EventBus = None):
        self.port = port
        self.event_bus = event_bus
        self.hostname = socket.gethostname()
        self.clients = set()
        
    def _get_hardware_profile(self) -> dict:
        import psutil
        # Check torch/CUDA if available
        vram_available = "Unknown"
        has_cuda = False
        try:
            import torch
            if torch.cuda.is_available():
                has_cuda = True
                vram_available = f"{torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB"
        except ImportError:
            pass
            
        return {
            "hostname": self.hostname,
            "role": "worker",
            "cpu_cores": psutil.cpu_count(logical=False),
            "ram_total": f"{psutil.virtual_memory().total / 1024**3:.1f}GB",
            "has_cuda": has_cuda,
            "vram_available": vram_available,
            "ollama_models": [] # Mock
        }

    async def _handle_client(self, websocket):
        self.clients.add(websocket)
        logger.info(f"MeshNode: Client connected from {websocket.remote_address}")
        
        try:
            # Send initial registration/profile
            profile = self._get_hardware_profile()
            await websocket.send(json.dumps({
                "type": "registration",
                "payload": profile
            }))
            
            async for message in websocket:
                data = json.loads(message)
                if data.get("type") == "task_dispatch":
                    task_id = data.get("task_id")
                    prompt = data.get("prompt")
                    logger.info(f"MeshNode: Received task {task_id}: {prompt}")
                    
                    # Execute task asynchronously
                    asyncio.create_task(self._process_task(websocket, task_id, prompt))
        except Exception as e:
            logger.error(f"MeshNode error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"MeshNode: Client disconnected {websocket.remote_address}")
            
    async def _process_task(self, websocket, task_id: str, prompt: str):
        """Simulates processing a heavy background workload."""
        logger.info(f"MeshNode: Processing task {task_id}...")
        
        # Here we would normally invoke SwarmSupervisor or Background RAG
        # For this prototype, we'll just wait and return
        await asyncio.sleep(2.0)
        
        result = f"[Mesh Worker {self.hostname}] Task {task_id} completed successfully."
        
        # Send result back
        try:
            await websocket.send(json.dumps({
                "type": "task_result",
                "task_id": task_id,
                "result": result
            }))
            
            if self.event_bus:
                self.event_bus.publish_sync("telemetry.update", data={"message": f"[🕸️ Mesh Result Delivered: {task_id}]"})
        except Exception as e:
            logger.error(f"MeshNode: Failed to send result for {task_id}: {e}")

    async def start(self):
        logger.info(f"Starting MeshNode server on port {self.port}")
        async with serve(self._handle_client, "0.0.0.0", self.port):
            await asyncio.Future()  # run forever

def run_mesh_node():
    server = MeshNodeServer()
    asyncio.run(server.start())

if __name__ == "__main__":
    run_mesh_node()
