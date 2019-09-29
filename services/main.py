import asyncio
import datetime
import random
import websockets

async def time(websocket, path):
    #TODO If person says clip that etc send a websocket message
    await websocket.send('data being sent')
    await asyncio.sleep(random.random() * 3)


print('listening on port 5678')
start_server = websockets.serve(time, "127.0.0.1", 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()