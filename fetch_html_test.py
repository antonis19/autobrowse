import asyncio
import json

import websockets


async def fetch_html(websocket) -> str:
    '''
    Fetch the HTML from the browser
    '''
    print(f"Fetching HTML of current page...")
    message = json.dumps({
        'action': "fetchHTML",
    })
    
    await websocket.send(message)
    response_data = json.loads(await websocket.recv())
    if not response_data.get('success'):
        raise Exception("Failed to fetch HTML")
    return response_data["result"]
    


if __name__ == "__main__":
    uri = "ws://localhost:3000"
    websocket = asyncio.get_event_loop().run_until_complete(websockets.connect(uri))
    dom = asyncio.get_event_loop().run_until_complete(fetch_html(websocket))
    print(dom)

  