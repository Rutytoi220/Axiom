"""Autonomous Docker Swarm Replication.

Dynamically spins up N headless AXIOM worker nodes via Docker to process
highly parallelizable workloads. Distributes task shards via the EventBus
and automatically tears down the cluster upon completion.
"""
import logging
import asyncio
import tempfile
import os
import uuid
from typing import List, Any

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from axiom.core.events import EventBus

logger = logging.getLogger(__name__)

# Lightweight base image for the worker nodes
DOCKERFILE_TEMPLATE = """
FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN pip install pydantic aiohttp
CMD ["python", "axiom_worker.py"]
"""

WORKER_SCRIPT = """
import sys
import json
import asyncio
import os

async def main():
    # In production, this would connect to the P2P Mesh WebSocket (port 9412)
    # For this simulation, we'll just process the shard passed via ENV
    shard_data = os.environ.get("AXIOM_SHARD", "[]")
    shard_id = os.environ.get("AXIOM_SHARD_ID", "unknown")
    try:
        tasks = json.loads(shard_data)
        results = []
        for task in tasks:
            # Simulate work
            await asyncio.sleep(0.5)
            results.append(f"Processed: {task}")
            
        print(json.dumps({"shard_id": shard_id, "status": "success", "results": results}))
    except Exception as e:
        print(json.dumps({"shard_id": shard_id, "status": "error", "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
"""

class DistributedSwarmManager:
    """Orchestrates ephemeral Docker containers for distributed workloads."""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.client = docker.from_env() if DOCKER_AVAILABLE else None
        
    async def distribute_workload(self, items: List[Any], num_nodes: int = 3) -> List[Any]:
        """Shards an array of items across N docker containers and aggregates the result."""
        if not DOCKER_AVAILABLE or not self.client:
            logger.warning("SwarmManager: Docker is not available. Falling back to local execution.")
            return [f"Local Processed: {item}" for item in items]
            
        logger.info(f"SwarmManager: Distributing {len(items)} items across {num_nodes} Swarm nodes...")
        
        # 1. Shard the data
        chunk_size = max(1, len(items) // num_nodes)
        shards = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        
        # 2. Build the worker image dynamically
        image_tag = "axiom-ephemeral-worker:latest"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write Dockerfile
            with open(os.path.join(tmpdir, "Dockerfile"), "w") as f:
                f.write(DOCKERFILE_TEMPLATE)
            # Write Worker Script
            with open(os.path.join(tmpdir, "axiom_worker.py"), "w") as f:
                f.write(WORKER_SCRIPT)
                
            logger.debug("SwarmManager: Building ephemeral Docker image...")
            try:
                self.client.images.build(path=tmpdir, tag=image_tag, rm=True)
            except Exception as e:
                logger.error(f"SwarmManager: Failed to build Docker image: {e}")
                return []
                
        # 3. Spin up containers
        containers = []
        for i, shard in enumerate(shards):
            import json
            shard_id = f"shard-{uuid.uuid4().hex[:6]}"
            try:
                logger.debug(f"SwarmManager: Spinning up container for {shard_id}")
                container = self.client.containers.run(
                    image_tag,
                    detach=True,
                    environment={
                        "AXIOM_SHARD": json.dumps(shard),
                        "AXIOM_SHARD_ID": shard_id
                    },
                    name=f"axiom-worker-{shard_id}"
                )
                containers.append(container)
            except Exception as e:
                logger.error(f"SwarmManager: Failed to start container - {e}")
                
        # 4. Wait for completion and aggregate
        aggregated_results = []
        for container in containers:
            try:
                # Wait for the container to exit (blocking in this mock, would be async in production)
                logger.debug(f"SwarmManager: Waiting for {container.name} to complete...")
                result = container.wait()
                logs = container.logs().decode("utf-8").strip()
                
                # Parse logs for JSON output
                try:
                    import json
                    output = json.loads(logs.split("\n")[-1]) # Assuming the last line is our JSON output
                    if output.get("status") == "success":
                        aggregated_results.extend(output.get("results", []))
                    else:
                        logger.error(f"SwarmManager: Worker error - {output.get('error')}")
                except json.JSONDecodeError:
                    logger.error(f"SwarmManager: Could not parse worker output: {logs}")
                    
            except Exception as e:
                logger.error(f"SwarmManager: Error collecting from container - {e}")
            finally:
                # 5. Cleanup
                logger.debug(f"SwarmManager: Tearing down container {container.name}")
                container.remove(force=True)
                
        logger.info(f"SwarmManager: Successfully aggregated {len(aggregated_results)} results from {len(containers)} nodes.")
        return aggregated_results
