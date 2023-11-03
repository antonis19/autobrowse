import json
import websockets
import asyncio
import sys

async def run_puppeteer_commands():
    uri = "ws://localhost:3000"
    async with websockets.connect(uri) as websocket:
        while True:
            command = input("Enter a command to send to the browser: ")
            print(f"Sending command: {command}")
            message = json.dumps({
            'action': "executeCode",
            'code': command,
            })
            await websocket.send(message)
            response_data = json.loads(await websocket.recv())

            print("Response data = ")
            print(response_data)

            if response_data.get('success'):
                print(f"Received: {response_data.get('result')}")
            else:
                print(f"Error: {response_data.get('error')}")

# a loop where the user sends puppeteer.js code to the web
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_puppeteer_commands())
