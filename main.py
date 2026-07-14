from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
            # メッセージを受信
            message = await websocket.receive_text()
            
            # 切断されたソケットを検知するためのリスト
            dead_connections = []
            
            for connection in active_connections:
                if connection != websocket:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        # 送信失敗したソケットは死んでいるのでマーク
                        dead_connections.append(connection)
            
            # 死んでいる接続を掃除
            for dead in dead_connections:
                if dead in active_connections:
                    active_connections.remove(dead)
                    
    except WebSocketDisconnect:
        print("プレイヤーが正常に切断されました")
    except Exception as e:
        print("プレイヤー通信エラー:", e)
    finally:
        # 切断されたらリストから確実に消去する
        if websocket in active_connections:
            active_connections.remove(websocket)
            print(f"接続を解除しました。現在の接続数: {len(active_connections)}")
