import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8000/ws/swarm"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket")
            await websocket.send(json.dumps({"prompt": "Hello AXIOM"}))
            print("Sent prompt")
            
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Received: {data['status']}")
                if data['status'] == 'complete' or data['status'] == 'error':
                    print(f"Result: {data.get('response', data.get('message', ''))}")
                    break
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
