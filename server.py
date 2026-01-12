from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import asyncio
from time import time

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

players = {}
countdown_task = None
COUNTDOWN_TIME = 20  # saniyə
game_active = False
start_time = None

async def countdown():
    global countdown_task, game_active, start_time
    game_active = True
    start_time = time()
    time_left = COUNTDOWN_TIME
    try:
        while time_left > 0:
            await asyncio.sleep(0.1)
            time_left = COUNTDOWN_TIME - int(time() - start_time)
            if time_left <= 3:
                for ws in players.values():
                    await ws.send_text("warning")
            for ws in players.values():
                await ws.send_text(f"countdown:{time_left}")
        for ws in players.values():
            await ws.send_text("time_up")
    finally:
        countdown_task = None
        game_active = False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    global countdown_task, game_active, start_time
    try:
        role = await websocket.receive_text()
        players[role] = websocket
        await websocket.send_text("connected")

        while True:
            msg = await websocket.receive_text()
            
            if msg == "start" and role == "admin":
                if countdown_task is None:
                    countdown_task = asyncio.create_task(countdown())
                    for ws in players.values():
                        await ws.send_text("start_sound")

            elif msg.startswith("buzz:"):
                player_name = msg.split(":")[1]
                if not game_active:
                    await websocket.send_text("faul")
                else:
                    ms_time = int((time() - start_time) * 1000)
                    for r, ws in players.items():
                        if r == player_name:
                            await ws.send_text("won")
                        elif r != "admin":
                            await ws.send_text("lost")
                        # show buzz time for admin
                        if r == "admin":
                            await ws.send_text(f"buzz_time:{player_name}:{ms_time}")
                    # stop countdown
                    if countdown_task:
                        countdown_task.cancel()
                        countdown_task = None
                        game_active = False

            elif msg == "reset" and role == "admin":
                if countdown_task:
                    countdown_task.cancel()
                    countdown_task = None
                game_active = False
                start_time = None
                for ws in players.values():
                    await ws.send_text("reset")

    except:
        pass
    finally:
        # disconnect zamanı sil
        for k, v in list(players.items()):
            if v == websocket:
                del players[k]


if __name__ == "__main__":
    import os, uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
