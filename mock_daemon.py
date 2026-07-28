import asyncio
import websockets
import json

async def handler(websocket):
    async for message in websocket:
        data = json.loads(message)
        if data.get("action") == "submit_task":
            prompt = data.get("prompt", "")
            
            # Send telemetry update
            await websocket.send(json.dumps({
                "type": "event",
                "event": {"type": "telemetry.update", "data": {"message": "[🔄 Processing Pipe Task...]"}}
            }))
            
            # Send tokens
            fixed = "def add(a, b):\n    return a + b\n"
            for char in fixed:
                await websocket.send(json.dumps({
                    "type": "event",
                    "event": {"type": "telemetry.token", "data": {"token": char}}
                }))
                
            # Send completion
            await websocket.send(json.dumps({
                "type": "event",
                "event": {"type": "orchestrator.completed", "data": {}}
            }))

async def main():
    async with websockets.serve(handler, "127.0.0.1", 9410):
        print("Mock daemon listening on 9410")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
