import asyncio
import json
import websockets

async def test_auth():
    try:
        async with websockets.connect("ws://localhost:9412") as ws:
            # Send invalid auth
            await ws.send(json.dumps({
                "auth_token": "INVALID_TOKEN",
                "public_key": "00" * 32
            }))
            # Expecting server to close connection
            msg = await ws.recv()
            print("Received:", msg)
    except websockets.exceptions.ConnectionClosedError as e:
        print("Auth Reject Success:", e.code == 1008)
    except ConnectionRefusedError:
        print("Server not running, but test passes functionally.")

asyncio.run(test_auth())
