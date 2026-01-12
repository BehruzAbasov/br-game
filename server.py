import os
import time
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Railway PORT
PORT = int(os.environ.get("PORT", 8080))

# Static files (html + mp3)
app.mount("/", StaticFiles(directory=".", html=True), name="static")

# Game state
players = {}
admin_ws = None

game_active = False
start_time = None
countdown_task = None
winner_declared = False

COUNTDOWN_SECONDS = 20


async def broadcast(message: dict):
    for ws in players.values():
        await ws.send_json(message)
    if admin_ws:
        await admin_ws.send_json(message)


async def countdown():
    global game_active
    for remaining in range(COUNTDOWN_SECONDS, 0, -1):
        if not game_active:
            return
        await broadcast({"type": "countdown", "value": remaining})
        await asyncio.sleep(1)

    game_active = False
    await broadcast({"type": "time_up"})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global admin_ws, game_active, start_time, countdown_task, winner_declared

    await ws.accept()

    try:
        data = await ws.receive_json()
        role = data.get("role")

        # ADMIN
        if role == "admin":
            admin_ws = ws
            await ws.send_json({"type": "status", "message": "admin connected"})

            while True:
                msg = await ws.receive_json()

                if msg["action"] == "start":
                    if countdown_task:
                        countdown_task.cancel()

                    game_active = True
                    winner_declared = False
                    start_time = time.time()

                    await broadcast({"type": "start"})
                    countdown_task = asyncio.create_task(countdown())

                elif msg["action"] == "reset":
                    if countdown_task:
                        countdown_task.cancel()

                    game_active = False
                    winner_declared = False
                    await broadcast({"type": "reset"})

        # PLAYER
        else:
            player_id = role
            players[player_id] = ws
            await ws.send_json({"type": "status", "message": f"{player_id} connected"})

            while True:
                msg = await ws.receive_json()

                if msg["action"] == "buzz":
                    now = time.time()

                    if not game_active:
                        await ws.send_json({"type": "false_start"})
                        continue

                    if winner_declared:
                        continue

                    winner_declared = True
                    game_active = False

                    if countdown_task:
                        countdown_task.cancel()

                    reaction_ms = int((now - start_time) * 1000)

                    await broadcast({
                        "type": "won",
                        "player": player_id,
                        "reaction": reaction_ms
                    })

    except WebSocketDisconnect:
        if ws == admin_ws:
            admin_ws = None
        else:
            for k, v in list(players.items()):
                if v == ws:
                    del players[k]
