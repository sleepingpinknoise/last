import tkinter as tk
from tkinter import messagebox
import websocket
import json
import threading
import os
from dotenv import load_dotenv
import chatgpt  # さっき作ったchatgpt.pyを読み込む

# パソコン側にある .env からAPIキーを読み込む
load_dotenv(".env")

class OthelloGame:
    def __init__(self, root):
        self.root = root
        self.root.title("ChatGPT連携 特殊オンラインオセロ")
        
        # AIの初期化
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.chatbot = chatgpt.ChatBot(api_key=api_key)
        else:
            self.chatbot = None
            print("警告: .envファイルに OPENAI_API_KEY が見つかりません。")

        # 盤面の初期化 (0: 空白, 1: 黒, -1: 白)
        self.board = [[0]*8 for _ in range(8)]
        self.board[3][3] = -1
        self.board[3][4] = 1
        self.board[4][3] = 1
        self.board[4][4] = -1
        
        self.my_turn = True   # 自分が打てるかどうかのフラグ
        self.my_color = 1     # 1: 黒(先手), -1: 白(後手)
        
        # 8x8のマス目ボタンを作成
        self.buttons = [[None]*8 for _ in range(8)]
        for r in range(8):
            for c in range(8):
                btn = tk.Button(root, width=4, height=2, bg="green", font=("Arial", 16),
                                command=lambda row=r, col=c: self.player_move(row, col))
                btn.grid(row=r, column=c)
                self.buttons[r][c] = btn
        
        # AI相談ボタンの配置
        self.ai_btn = tk.Button(root, text="AIに次の手を相談する", font=("Arial", 12), command=self.ask_ai)
        self.ai_btn.grid(row=8, column=0, columnspan=4, sticky="nsew")
        
        # 状態を表示するラベル
        self.status_label = tk.Label(root, text="サーバーに接続中...", font=("Arial", 12))
        self.status_label.grid(row=8, column=4, columnspan=4)
        
        self.update_board_dims()
        
        # オンラインサーバーへの接続を開始
        self.connect_server()

    def connect_server(self):
        # ★重要：Renderにデプロイしたあと、発行された自分のURL（https://〜）の
        # 頭を「wss://」に変えて、お尻に「/ws」をつけたものに書き換えてね！
        # （ローカル環境でテストする間は、下の "ws://localhost:10000/ws" のままでOK）
        server_url = "ws://localhost:10000/ws"
        
        self.ws = websocket.WebSocketApp(
            server_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        # 画面がフリーズしないように、通信は裏側の別スレッドで走らせる
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def on_open(self, ws):
        self.status_label.config(text="サーバー接続完了！対戦できます")
        print("Renderサーバーに接続しました。")

    def on_message(self, ws, message):
        # 相手プレイヤーから手が送られてきたときの処理
        try:
            data = json.loads(message)
            row = data.get("row")
            col = data.get("col")
            color = data.get("color")
            
            # 相手の手を画面に反映（Tkinterのルール上、メインスレッドで安全に実行）
            self.root.after(0, self.remote_move, row, col, color)
        except Exception as e:
            print("データ受信エラー:", e)

    def on_error(self, ws, error):
        self.status_label.config(text="通信エラー発生")
        print("エラー:", error)

    def on_close(self, ws, close_status_code, close_msg):
        self.status_label.config(text="サーバーから切断されました")
        print("切断されました。")

    def update_board_dims(self):
        # 盤面の配列データに合わせて、画面の「●」を更新する
        for r in range(8):
            for c in range(8):
                val = self.board[r][c]
                if val == 1:
                    self.buttons[r][c].config(text="●", fg="black")
                elif val == -1:
                    self.buttons[r][c].config(text="●", fg="white")
                else:
                    self.buttons[r][c].config(text="")

    def player_move(self, row, col):
        # 自分がマスをクリックしたときの処理
        if not self.my_turn:
            messagebox.showinfo("注意", "相手の番だから待ってね！")
            return
        if self.board[row][col] != 0:
            return
        
        # 自分の石を置く（簡易配置モード）
        self.board[row][col] = self.my_color
        self.update_board_dims()
        
        # サーバーを通じて相手の画面に手を送信
        move_data = {"row": row, "col": col, "color": self.my_color}
        try:
            self.ws.send(json.dumps(move_data))
        except Exception as e:
            print("送信に失敗しました:", e)
            
        self.my_turn = False
        self.status_label.config(text="相手の番です...")

    def remote_move(self, row, col, color):
        # 送られてきた相手の手を自分の画面に反映する
        if color != self.my_color:
            self.board[row][col] = color
            self.update_board_dims()
            self.my_turn = True
            self.status_label.config(text="あなたの番です！")

    def ask_ai(self):
        # ChatGPTに次の手を相談する特殊コマンド
        if not self.chatbot:
            messagebox.showerror("エラー", "AIの準備ができていません。.envの設定を確認してね。")
            return
            
        self.status_label.config(text="AIが考えています...")
        
        def ai_thread():
            system_setting = "あなたはオセロの天才です。プレイヤーに次のおすすめの座標（行と列）を1つ教えてあげてください。"
            board_str = str(self.board)
            prompt = f"現在の盤面（1が黒、-1が白、0が空）: {board_str}\n次の一手をアドバイスして。"
            
            # chatgpt.py の ask メソッドを呼び出す
            reply = self.chatbot.ask(system_setting, prompt)
            
            # 答えをポップアップで表示
            self.root.after(0, lambda: messagebox.showinfo("AIのアドバイス", reply))
            self.root.after(0, lambda: self.status_label.config(
                text="あなたの番です！" if self.my_turn else "相手の番です..."
            ))

        # AIとの通信も裏側で並列処理させる
        threading.Thread(target=ai_thread, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    game = OthelloGame(root)
    root.mainloop()