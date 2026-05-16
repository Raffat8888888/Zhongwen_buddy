import asyncio
import websockets

clients = set()

async def handler(websocket):
    clients.add(websocket)
    try:
        async for message in websocket:
            for c in clients:
                if c != websocket:
                    await c.send(message)
    finally:
        clients.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8004):
        print("WebSocket signaling server running on ws://0.0.0.0:8004")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
