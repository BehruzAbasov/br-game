import asyncio
import websockets
import json
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading

# ===== GLOBAL STATE =====
clients = set()
game_active = False
countdown_task = None
winner_found = False
start_time = None
countdown_seconds = 20

# ===== WEBSOCKET HANDLER =====
async def handler(ws):
    global clients, game_active, countdown_task, winner_found, start_time

    print("WS CONNECTED")
    clients.add(ws)
    try:
        async for message in ws:
            data = json.loads(message)
            print("RECEIVED:", data, "ACTIVE:", game_active)

            # ---- START ----
            if data["type"] == "start" and not game_active:
                game_active = True
                winner_found = False
                start_time = time.time()
                if countdown_task and not countdown_task.done():
                    countdown_task.cancel()
                countdown_task = asyncio.create_task(countdown())
                await broadcast({"type": "start", "time": countdown_seconds})

            # ---- RESET ----
            elif data["type"] == "reset":
                game_active = False
                winner_found = False
                if countdown_task and not countdown_task.done():
                    countdown_task.cancel()
                await broadcast({"type": "reset"})

            # ---- PLAYER BUZZ ----
            elif data["type"].startswith("player"):
                if not game_active or winner_found:
                    await ws.send(json.dumps({"type":"faul"}))
                else:
                    winner_found = True
                    game_active = False
                    if countdown_task and not countdown_task.done():
                        countdown_task.cancel()
                    ms = int((time.time() - start_time) * 1000)
                    await broadcast({
                        "type": "won",
                        "player": data["type"],
                        "time": ms
                    })
    finally:
        clients.remove(ws)

# ===== COUNTDOWN FUNCTION =====
async def countdown():
    global countdown_seconds, winner_found
    try:
        for t in range(countdown_seconds, 0, -1):
            if winner_found:  # WIN basılıbsa dərhal dayandır
                print("Countdown stopped: winner found")
                break
            if t <= 3:
                await broadcast({"type":"warning", "time":t})
            await broadcast({"type": "time", "value": t})
            await asyncio.sleep(1)
        if not winner_found:
            await broadcast({"type":"timeout"})
            global game_active
            game_active = False
    except asyncio.CancelledError:
        print("COUNTDOWN CANCELLED")
        return

# ===== BROADCAST =====
async def broadcast(message):
    data = json.dumps(message)
    for client in clients:
        try:
            await client.send(data)
        except:
            pass

# ===== HTTP SERVER FOR HTML/JS =====
def run_http():
    server_address = ("", 8080)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    print("HTTP SERVER ON PORT 8080")
    httpd.serve_forever()

# ===== MAIN =====
async def main():
    ws_server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("WS SERVER ON PORT 8765")
    await asyncio.Future()  # run forever

# ===== START BOTH SERVERS =====
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()
    asyncio.run(main())
