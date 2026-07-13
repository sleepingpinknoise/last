from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import json

app = FastAPI()
active_connections = []

@app.get("/")
async def get():
    return HTMLResponse("<h1>Othello Server is Live! Ready for match!</h1>")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"新しいプレイヤーが接続しました。現在の接続数: {len(active_connections)}")
    
    try:
        while True:
            message = await websocket.receive_text()
            for connection in active_connections:
                if connection != websocket:
                    await connection.send_text(message)
                    
    except Exception as e:
        print("プレイヤーが切断されました:", e)
    finally:
        # 切断されたらリストから消去する
        if websocket in active_connections:
            active_connections.remove(websocket)
