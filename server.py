from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio

app = FastAPI()

# Static faylları /static altında serve edirik
app.mount("/static", StaticFiles(directory="static"), name="static")

# GAME STATE
players = {}
countdown_task = None
COUNTDOWN_TIME = 20  # saniyə


async def countdown():
    global countdown_task
    time_left = COUNTDOWN_TIME
    while time_left > 0:
        await asyncio.sleep(1)
        time_left -= 1
        # Son 3 saniyə xəbərdarlıq
        if time_left <= 3:
            for ws in players.values():
                await ws.send_text("warning")
    countdown_task = None
    for ws in players.values():
        await ws.send_text("time_up")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # İlk mesajda rol (player1, player2, admin) göndərilir
        role = await websocket.receive_text()
        players[role] = websocket
        await websocket.send_text("connected")

        global countdown_task
        while True:
            msg = await websocket.receive_text()
            
            if msg == "start" and role == "admin":
                if countdown_task is None:
                    countdown_task = asyncio.create_task(countdown())
                    for ws in players.values():
                        await ws.send_text("start_sound")
            elif msg.startswith("buzz"):
                if countdown_task:
                    # İlk basan qalib
                    player_name = msg.split(":")[1]
                    for r, ws in players.items():
                        if r == player_name:
                            await ws.send_text("won")
                        elif r != "admin":
                            await ws.send_text("lost")
                    # Stop countdown
                    countdown_task.cancel()
                    countdown_task = None
            elif msg == "reset" and role == "admin":
                if countdown_task:
                    countdown_task.cancel()
                    countdown_task = None
                for ws in players.values():
                    await ws.send_text("reset")

    except:
        pass
    finally:
        # Disconnect zamanı players-dən sil
        for k, v in list(players.items()):
            if v == websocket:
                del players[k]
