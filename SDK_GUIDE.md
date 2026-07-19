# AXIOM SDK Developer Guide

The `axiom-sdk` is the official Python client library for integrating with the AXIOM JSON-RPC 2.0 daemon. It provides both asynchronous and synchronous wrappers around the core Unix Domain Socket API, featuring automatic authentication, strict Pydantic typings, and event streaming.

## Installation

Since AXIOM SDK is bundled with the OS environment, you can import it directly from your Python scripts running on the system:

```python
from axiom.sdk import AxiomClient, SyncAxiomClient
from axiom.sdk import PromptRequest, TelemetryPayload
```

## Quick Start (Async)

The primary interface is asynchronous, which is ideal for high-throughput or event-driven applications like custom IDE extensions.

```python
import asyncio
from axiom.sdk import AxiomClient

async def main():
    # Automatically locates ~/.axiom/axiom.sock and ~/.axiom/daemon.token
    client = AxiomClient()
    await client.connect()

    # 1. Check System Status
    status = await client.get_status()
    print(f"System Load: RAM {status.ram_percent}%, VRAM {status.vram_percent}%")

    # 2. Submit a Prompt
    result = await client.prompt("Analyze the current directory and summarize its purpose.")
    print("AXIOM response:", result)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Quick Start (Sync Wrapper)

For simple scripts, use `SyncAxiomClient`. This wrapper runs an internal background thread and event loop, allowing you to seamlessly integrate with synchronous code.

```python
from axiom.sdk import SyncAxiomClient

client = SyncAxiomClient()

# Blocks until the response is ready
status = client.get_status()
print(status.model_dump())

result = client.prompt("Hello AXIOM!")
print(result)
```

## EventBus Streaming

You can subscribe directly to the daemon's EventBus to observe the inner workings of AXIOM, including Multi-Agent Swarm proposals, system state changes, and proactive perception events.

```python
import asyncio
from axiom.sdk import AxiomClient

async def monitor_swarm():
    client = AxiomClient()
    await client.connect()
    
    print("Listening for sub-agent proposals...")
    
    # Subscribe to a specific topic
    async for event in client.subscribe("swarm.proposal"):
        print(f"New Proposal [{event['proposal_id']}]: Agent {event['agent']} wants to run {event['tool']}")

if __name__ == "__main__":
    asyncio.run(monitor_swarm())
```

### Common Event Topics

- `swarm.proposal`: When a sub-agent proposes an action.
- `swarm.vote`: When consensus votes are cast.
- `telemetry.update`: Hardware RAM/VRAM tracking.
- `perception.window.change`: Emitted by the Proactive OS Kernel (if enabled).
- `perception.clipboard.change`: Emitted when new clipboard text passes the privacy scrubber.
