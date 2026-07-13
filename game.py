import random
import tkinter as tk
from tkinter import messagebox
import os
import re
import socket
import threading
import json
from dotenv import load_dotenv
import chatgpt

EMPTY = 0
HOLE = -1
load_dotenv(".env")
chatbot = chatgpt.ChatBot(api_key=os.environ.get("OPENAI_API_KEY"))

system_setting = """
あなたは、多彩な特殊イベントが発生する「特殊オセロ」の最強のAIプレイヤーです。
現在の盤面状態、各マスのスコア、発生予定の特殊イベント情報が与えられます。
あなたは自分の手番において、最も勝利に近づく最適な一手を1つだけ選択し、以下のフォーマットで出力してください。

【思考プロセス】
（なぜそのマスを選んだのか、イベントをどう活かすか、または回避するかなどの思考を短く記述）

【選択マス】
(行, 列)

※注意：
- 選択マスは必ず (0, 1) のように括弧とカンマで記述してください。0始まりのインデックスです。
- 合法手（石を置けるマス）の中から選んでください。
- 特殊イベント（重力や破壊など）を考慮して、数手先を読んだプレイをしてください。
"""

PLAYER_COLORS = {
    1: ("黒", "#111827", "#f8fafc"),
    2: ("白", "#f8fafc", "#111827"),
    3: ("赤", "#e05263", "white"),
    4: ("青", "#3b82f6", "white"),
}
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
GRAVITY_DIRECTIONS = {"上": (-1, 0), "下": (1, 0), "左": (0, -1), "右": (0, 1)}
MIRROR_SIDES = ["上半分", "下半分", "左半分", "右半分"]

APP_BG = "#101418"
PANEL_BG = "#171d23"
PANEL_ALT = "#202832"
TEXT = "#eef2f6"
MUTED = "#9aa8b5"
BOARD_BG = "#0f7a4f"
BOARD_DARK = "#0b3d2c"
BOARD_LIGHT = "#17996a"
ACCENT = "#f5c542"
DANGER = "#ff5c7a"
FONT_FAMILY = "Yu Gothic UI"
FONT_UI = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 22, "bold")
FONT_SECTION = (FONT_FAMILY, 10, "bold")
FONT_BUTTON = (FONT_FAMILY, 11, "bold")

class OthelloApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Special Othello (Online Supported)")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        self.configure_theme()

        # ネットワーク用管理変数
        self.socket = None
        self.is_host = False
        self.my_player_index = 0  # 0=1P(ホスト), 1=2P(ゲスト)
        self.is_online = False

        self.players = []
        self.board = []
        self.cell_scores = []
        self.ages = []
        self.health = []
        self.holes = set()
        self.current_player_index = 0
        self.turn_count = 0
        self.game_started = False
        self.game_over = False
        
        self.next_gravity = None
        self.next_mirror = None
        self.next_destroy_targets = []
        self.next_flip_limit_event = False
        
        self.flip_mission_counters = []
        self.flip_mission_targets = []
        
        self.event_window = None
        self.settings = {}
        self.vars = {}

        self.build_layout()
        self.reset_settings()
        self.show_settings_screen()

    def configure_theme(self):
        self.root.option_add("*Font", FONT_UI)
        self.root.option_add("*Background", PANEL_BG)
        self.root.option_add("*Foreground", TEXT)

    def styled_button(self, parent, text, command, primary=False):
        bg = ACCENT if primary else PANEL_ALT
        fg = "#111827" if primary else TEXT
        return tk.Button(parent, text=text, command=command, font=FONT_BUTTON, bg=bg, fg=fg, relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2")

    def section_frame(self, title, expand=False):
        frame = tk.LabelFrame(self.left, text=title, padx=12, pady=10, bg=PANEL_BG, fg=TEXT, font=FONT_SECTION, relief=tk.FLAT, bd=1, highlightbackground="#27313c", highlightthickness=1)
        frame.pack(fill=tk.BOTH if expand else tk.X, expand=expand, pady=6)
        return frame

    def build_layout(self):
        self.left = tk.Frame(self.root, width=400, bg=PANEL_BG)
        self.left.pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=14)
        self.left.pack_propagate(False)

        self.right = tk.Frame(self.root, bg=APP_BG)
        self.right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 14), pady=14)

        self.title_label = tk.Label(self.left, text="特殊オセロ設定", font=FONT_TITLE, bg=PANEL_BG, fg=TEXT)
        self.title_label.pack(anchor="w", pady=(0, 10))

        self.canvas = tk.Canvas(self.right, bg=APP_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.status = tk.Label(self.right, text="設定を調整して「試合開始」を押してください。", font=FONT_UI, anchor="w", bg=APP_BG, fg=MUTED)
        self.status.pack(fill=tk.X, pady=(10, 0))

    def reset_settings(self):
        self.players = [{"kind": "人間"}, {"kind": "人間"}]
        self.holes = set()
        self.vars = {
            "rows": tk.IntVar(value=8), "cols": tk.IntVar(value=8), "wrap": tk.BooleanVar(value=False),
            "hole_count": tk.IntVar(value=0), "gravity": tk.BooleanVar(value=False), "gravity_interval": tk.IntVar(value=5),
            "mirror": tk.BooleanVar(value=False), "mirror_interval": tk.IntVar(value=5), "destroy": tk.BooleanVar(value=False),
            "destroy_count": tk.IntVar(value=1), "destroy_interval": tk.IntVar(value=5), "expand": tk.BooleanVar(value=False),
            "expand_count": tk.IntVar(value=3), "life": tk.BooleanVar(value=False), "life_length": tk.IntVar(value=5),
            "health": tk.BooleanVar(value=False), "health_count": tk.IntVar(value=3), "flip_limit_event": tk.BooleanVar(value=False),
            "flip_limit_interval": tk.IntVar(value=5), "flip_limit": tk.BooleanVar(value=False), "flip_limit_count": tk.IntVar(value=3),
            "reverse_judgment": tk.BooleanVar(value=False), "total_score": tk.BooleanVar(value=False),
        }

    def clear_left(self):
        for widget in self.left.winfo_children():
            if widget is not self.title_label:
                widget.destroy()

    def show_settings_screen(self):
        self.close_event_window()
        self.clear_left()
        self.title_label.config(text="特殊オセロ設定")
        self.game_started = False
        self.game_over = False

        # 人数設定
        pf = self.section_frame("プレイヤー構成")
        self.player_label = tk.Label(pf, text="", bg=PANEL_BG, fg=MUTED)
        self.player_label.pack(anchor="w")
        p_row = tk.Frame(pf, bg=PANEL_BG)
        p_row.pack(fill=tk.X, pady=5)
        self.styled_button(p_row, "+人間", lambda: self.add_player("人間")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.styled_button(p_row, "+CPU", lambda: self.add_player("CPU")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.styled_button(p_row, "+AI", lambda: self.add_player("AI")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.styled_button(p_row, "-削除", self.remove_player).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.update_player_label()

        # オンライン接続セクション
        net_f = self.section_frame("オンライン対戦設定")
        ip_row = tk.Frame(net_f, bg=PANEL_BG)
        ip_row.pack(fill=tk.X, pady=2)
        tk.Label(ip_row, text="接続先IP: ", bg=PANEL_BG).pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(ip_row, width=15, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT, bd=0)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack(side=tk.LEFT, padx=5)

        btn_row = tk.Frame(net_f, bg=PANEL_BG)
        btn_row.pack(fill=tk.X, pady=5)
        self.host_btn = self.styled_button(btn_row, "部屋を作る(Host)", self.network_host)
        self.host_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.join_btn = self.styled_button(btn_row, "部屋に入る(Guest)", self.network_join)
        self.join_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 盤面設定
        bf = self.section_frame("基本ルール")
        self.dimension_control(bf, "縦マス", "rows", 4, 16)
        self.dimension_control(bf, "横マス", "cols", 4, 16)
        self.dimension_control(bf, "穴の数", "hole_count", 0, 10)
        tk.Checkbutton(bf, text="ループ盤面（循環）", variable=self.vars["wrap"], bg=PANEL_BG, fg=TEXT, selectcolor=PANEL_ALT).pack(anchor="w", pady=2)
        tk.Checkbutton(bf, text="マスマス点数制（マス毎に加算）", variable=self.vars["total_score"], bg=PANEL_BG, fg=TEXT, selectcolor=PANEL_ALT).pack(anchor="w", pady=2)
        tk.Checkbutton(bf, text="天邪鬼ルール（少ない方が勝ち）", variable=self.vars["reverse_judgment"], bg=PANEL_BG, fg=TEXT, selectcolor=PANEL_ALT).pack(anchor="w", pady=2)

        # 特殊イベント
        ef = self.section_frame("特殊イベント", expand=True)
        canvas_scroll = tk.Canvas(ef, bg=PANEL_BG, highlightthickness=0)
        scroll_frame = tk.Frame(canvas_scroll, bg=PANEL_BG)
        scrollbar = tk.Scrollbar(ef, orient="vertical", command=canvas_scroll.yview)
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas_scroll.create_window((0, 0), window=scroll_frame, anchor="nw")

        def check_toggle(var_name, label_text, has_int=False, int_name=""):
            row = tk.Frame(scroll_frame, bg=PANEL_BG)
            row.pack(fill=tk.X, anchor="w", pady=2)
            tk.Checkbutton(row, text=label_text, variable=self.vars[var_name], bg=PANEL_BG, fg=TEXT, selectcolor=PANEL_ALT).pack(side=tk.LEFT)
            if has_int:
                tk.Label(row, text=" 周期:", bg=PANEL_BG).pack(side=tk.LEFT)
                tk.Entry(row, textvariable=self.vars[int_name], width=3, bg=PANEL_ALT, fg=TEXT, bd=0).pack(side=tk.LEFT, padx=2)

        check_toggle("gravity", "局所重力イベント", True, "gravity_interval")
        check_toggle("mirror", "反転ミラーイベント", True, "mirror_interval")
        check_toggle("destroy", "マス崩壊イベント", True, "destroy_interval")
        check_toggle("flip_limit_event", "指定ミッションイベント", True, "flip_limit_interval")
        check_toggle("expand", "盤面拡張システム")
        check_toggle("life", "石の寿命システム", True, "life_length")
        check_toggle("health", "石の耐久値システム", True, "health_count")
        check_toggle("flip_limit", "一回での最大反転数制限")

        scroll_frame.update_idletasks()
        canvas_scroll.config(scrollregion=canvas_scroll.bbox("all"))

        # アクションボタン
        b_row = tk.Frame(self.left, bg=PANEL_BG)
        b_row.pack(fill=tk.X, pady=10)
        self.start_btn = self.styled_button(b_row, "試合開始", self.start_game, primary=True)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.draw_preview_board()

    def dimension_control(self, parent, label, var_name, min_v, max_v):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=f"{label}: ", bg=PANEL_BG, width=8, anchor="w").pack(side=tk.LEFT)
        tk.Button(row, text="-", command=lambda: self.step_var(var_name, -1, min_v, max_v), bg=PANEL_ALT, fg=TEXT, bd=0, width=2).pack(side=tk.LEFT)
        tk.Label(row, textvariable=self.vars[var_name], bg=PANEL_BG, width=4).pack(side=tk.LEFT)
        tk.Button(row, text="+", command=lambda: self.step_var(var_name, 1, min_v, max_v), bg=PANEL_ALT, fg=TEXT, bd=0, width=2).pack(side=tk.LEFT)

    def step_var(self, name, step, min_v, max_v):
        val = self.vars[name].get() + step
        if min_v <= val <= max_v:
            self.vars[name].set(val)
            self.draw_preview_board()

    def add_player(self, kind):
        if len(self.players) < 4:
            self.players.append({"kind": kind})
            self.update_player_label()

    def remove_player(self):
        if len(self.players) > 2:
            self.players.pop()
            self.update_player_label()

    def update_player_label(self):
        txt = " ➔ ".join([f"{i+1}P:{p['kind']}" for i, p in enumerate(self.players)])
        self.player_label.config(text=txt)

    def reset_all_settings(self):
        self.reset_settings()
        self.show_settings_screen()

    # ---- オンライン通信処理系 ----
    def network_host(self):
        self.is_host = True
        self.my_player_index = 0
        self.is_online = True
        self.host_btn.config(state=tk.DISABLED, text="待機中...")
        self.join_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", 5555))
            server.listen(1)
            conn, addr = server.accept()
            self.socket = conn
            self.status.config(text=f"ゲスト接続成功: {addr}")
            self.host_btn.config(text="接続済")
            threading.Thread(target=self._listen_network, daemon=True).start()
        except Exception as e:
            messagebox.showerror("エラー", f"部屋作成に失敗したーー。: {e}")
            self.reset_network_ui()

    def network_join(self):
        self.is_host = False
        self.my_player_index = 1
        self.is_online = True
        ip = self.ip_entry.get()
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ip, 5555))
            self.socket = client
            self.join_btn.config(text="接続済", state=tk.DISABLED)
            self.host_btn.config(state=tk.DISABLED)
            self.start_btn.config(state=tk.DISABLED, text="ホストの開始待ち...")
            threading.Thread(target=self._listen_network, daemon=True).start()
        except Exception as e:
            messagebox.showerror("エラー", f"接続に失敗したってわけ。: {e}")
            self.reset_network_ui()

    def reset_network_ui(self):
        self.is_online = False
        self.host_btn.config(state=tk.NORMAL, text="部屋を作る(Host)")
        self.join_btn.config(state=tk.NORMAL, text="部屋に入る(Guest)")
        if hasattr(self, "start_btn"):
            self.start_btn.config(state=tk.NORMAL, text="試合開始")

    def _listen_network(self):
        while self.is_online:
            try:
                data = self.socket.recv(8192)
                if not data:
                    break
                packet = json.loads(data.decode('utf-8'))
                
                if packet["type"] == "START":
                    self.root.after(10, lambda: self.sync_and_start_game(packet["data"]))
                elif packet["type"] == "MOVE":
                    row, col = packet["data"]["row"], packet["data"]["col"]
                    self.root.after(10, lambda: self._execute_local_place(row, col))
            except:
                break
        self.status.config(text="ネットワーク接続が切断されましたーー。")
        self.reset_network_ui()

    def sync_and_start_game(self, data):
        self.settings = data["settings"]
        self.board = data["board"]
        self.cell_scores = data["cell_scores"]
        self.holes = set((tuple(h) for h in data["holes"]))
        
        r, c = len(self.board), len(self.board[0])
        self.ages = [[None for _ in range(c)] for _ in range(r)]
        self.health = [[None for _ in range(c)] for _ in range(r)]
        self.flip_mission_counters = [self.settings.get("flip_limit_interval", 5) for _ in self.players]
        self.flip_mission_targets = data["flip_mission_targets"]
        
        self.current_player_index = 0
        self.turn_count = 0
        self.game_started = True
        self.game_over = False
        
        self.show_game_controls()
        self.prepare_predictions()
        self.draw_board()

    # ---- ゲーム初期化・進行ロジック ----
    def collect_settings(self):
        return {k: v.get() for k, v in self.vars.items()}

    def draw_preview_board(self):
        if self.game_started: return
        self.canvas.delete("all")
        r, c = self.vars["rows"].get(), self.vars["cols"].get()
        self.draw_grid_base(r, c)

    def draw_grid_base(self, r, c):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            self.root.update_idletasks()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
        
        self.cell_size = min((w - 60) // c, (h - 60) // r)
        self.ox = (w - self.cell_size * c) // 2
        self.oy = (h - self.cell_size * r) // 2

        for i in range(r):
            for j in range(c):
                x1 = self.ox + j * self.cell_size
                y1 = self.oy + i * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                bg = BOARD_LIGHT if (i + j) % 2 == 0 else BOARD_DARK
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#1b242c")

    def create_initial_board(self):
        r, c = self.settings["rows"], self.settings["cols"]
        board = [[EMPTY for _ in range(c)] for _ in range(r)]
        mid_r, mid_c = r // 2, c // 2
        
        # 2P〜4P構成の初期配置配置
        board[mid_r - 1][mid_c - 1] = 2
        board[mid_r][mid_c] = 2
        board[mid_r - 1][mid_c] = 1
        board[mid_r][mid_c - 1] = 1
        
        if len(self.players) >= 3:
            board[max(0, mid_r - 2)][mid_c] = 3
        if len(self.players) == 4:
            board[min(r - 1, mid_r + 1)][mid_c - 1] = 4

        # 穴ぼこの初期設定
        self.holes.clear()
        available = [(i, j) for i in range(r) for j in range(c) if board[i][j] == EMPTY]
        count = min(self.settings["hole_count"], len(available))
        for (ri, ci) in random.sample(available, count):
            self.holes.add((ri, ci))
            board[ri][ci] = HOLE
            
        return board

    def generate_random_scores(self, r, c):
        return [[random.randint(1, 9) for _ in range(c)] for _ in range(r)]

    def show_game_controls(self):
        self.clear_left()
        self.title_label.config(text="対戦中...")
        
        self.info_panel = self.section_frame("現在のステータス")
        self.score_label = tk.Label(self.info_panel, text="", bg=PANEL_BG, justify=tk.LEFT)
        self.score_label.pack(anchor="w")

        self.evt_panel = self.section_frame("予告イベント")
        self.evt_label = tk.Label(self.evt_panel, text="なし", bg=PANEL_BG, fg=ACCENT, justify=tk.LEFT)
        self.evt_label.pack(anchor="w")

        self.styled_button(self.left, "タイトルへ戻る", self.show_settings_screen).pack(fill=tk.X, side=tk.BOTTOM, pady=10)

    def draw_board(self):
        self.canvas.delete("all")
        r, c = len(self.board), len(self.board[0])
        self.draw_grid_base(r, c)

        # 盤面の石・テキストの描画
        for i in range(r):
            for j in range(c):
                val = self.board[i][j]
                x1 = self.ox + j * self.cell_size
                y1 = self.oy + i * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                if val == HOLE:
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill="#1a1a1a", outline="#333")
                    self.canvas.create_line(x1, y1, x2, y2, fill="#2a2a2a")
                    self.canvas.create_line(x1, y2, x2, y1, fill="#2a2a2a")
                    continue

                # スコア表示
                if self.settings.get("total_score"):
                    self.canvas.create_text(x1 + 6, y1 + 6, text=str(self.cell_scores[i][j]), fill="#ffffff", font=FONT_SMALL, anchor="nw")

                # 石の描画
                if val in PLAYER_COLORS:
                    _, f_col, t_col = PLAYER_COLORS[val]
                    pad = self.cell_size * 0.12
                    self.canvas.create_oval(x1+pad, y1+pad, x2-pad, y2-pad, fill=f_col, outline=t_col, width=1)
                    
                    # 耐久値 or 寿命値のオーバーレイ
                    sub_txt = ""
                    if self.settings.get("health") and self.health[i][j] is not None:
                        sub_txt = f"H{self.health[i][j]}"
                    elif self.settings.get("life") and self.ages[i][j] is not None:
                        rem = self.settings["life_length"] - self.ages[i][j]
                        sub_txt = f"L{rem}"
                    
                    if sub_txt:
                        self.canvas.create_text(x1+self.cell_size/2, y1+self.cell_size/2, text=sub_txt, fill=t_col, font=FONT_SMALL)

        # 合法手のガイドラインハイライト
        if not self.game_over and self.is_human_turn():
            p = self.current_player()
            for i in range(r):
                for j in range(c):
                    if self.get_flips(i, j, p):
                        x1 = self.ox + j * self.cell_size + 2
                        y1 = self.oy + i * self.cell_size + 2
                        x2 = x1 + self.cell_size - 4
                        y2 = y1 + self.cell_size - 4
                        self.canvas.create_rectangle(x1, y1, x2, y2, outline=ACCENT, width=2)

        self.update_status_ui()

    def update_status_ui(self):
        scores = self.calculate_scores()
        txt = ""
        for idx, p in enumerate(self.players):
            p_num = idx + 1
            name, _, _ = PLAYER_COLORS[p_num]
            mark = " ➔ " if idx == self.current_player_index else "   "
            txt += f"{mark}{p_num}P({name}) [{p['kind']}]: {scores[p_num]}点"
            if self.settings.get("flip_limit_event"):
                txt += f" (ミッション:{self.flip_mission_targets[idx]}枚 / あと{self.flip_mission_counters[idx]}ターン)"
            txt += "\n"
        self.score_label.config(text=txt)

        # 予告の更新
        e_txt = ""
        if self.next_gravity: e_txt += f"・次ターン：重力引力 [{self.next_gravity}]\n"
        if self.next_mirror: e_txt += f"・次ターン：ミラー鏡面反転 [{self.next_mirror}]\n"
        if self.next_destroy_targets: e_txt += f"・次ターン：マス崩壊 ({len(self.next_destroy_targets)}箇所)\n"
        if self.next_flip_limit_event: e_txt += "・次ターン：指定枚数制限ルール発動\n"
        self.evt_label.config(text=e_txt if e_txt else "特になし。平和な盤面。")

        if self.game_over:
            self.status.config(text="ゲーム終了ーー。結果を確認してね。")
        else:
            curr_p = self.current_player_index + 1
            if self.is_online:
                if self.current_player_index == self.my_player_index:
                    self.status.config(text=f"あなたの手番（{curr_p}P）だよ！打つ場所を選んで。")
                else:
                    self.status.config(text=f"相手プレイヤー（{curr_p}P）の思考・通信を待ってるよーー。")
            else:
                self.status.config(text=f"{curr_p}P（{self.players[self.current_player_index]['kind']}）の手番です。")

    def calculate_scores(self):
        scores = {idx+1: 0 for idx in range(len(self.players))}
        r, c = len(self.board), len(self.board[0])
        for i in range(r):
            for j in range(c):
                p = self.board[i][j]
                if p in scores:
                    if self.settings.get("total_score"):
                        scores[p] += self.cell_scores[i][j]
                    else:
                        scores[p] += 1
        return scores

    def current_player(self):
        return self.current_player_index + 1

    # ---- ひっくり返し・判定コアロジック ----
    def get_flips(self, row, col, player):
        if self.board[row][col] != EMPTY: return []
        r_max, c_max = len(self.board), len(self.board[0])
        all_flips = []

        for dr, dc in DIRECTIONS:
            matched = []
            cr, cc = row + dr, col + dc
            while True:
                if self.settings.get("wrap"):
                    cr, cc = cr % r_max, cc % c_max
                else:
                    if not (0 <= cr < r_max and 0 <= cc < c_max): break
                
                v = self.board[cr][cc]
                if v == EMPTY or v == HOLE: break
                if v == player:
                    all_flips.extend(matched)
                    break
                else:
                    matched.append((cr, cc))
                    cr += dr
                    cc += dc

        if self.settings.get("flip_limit") and self.settings.get("flip_limit_count", 0) > 0:
            if len(all_flips) > self.settings["flip_limit_count"]:
                return [] # 制限枚数を超えたら置けないルール

        if self.next_flip_limit_event:
            # 指定ミッション枚数以外は置けない
            req = self.flip_mission_targets[self.current_player_index]
            if len(all_flips) != req: return []

        return list(set(all_flips))

    def next_player_with_move(self):
        num_p = len(self.players)
        for i in range(1, num_p + 1):
            nxt = (self.current_player_index + i) % num_p
            if self.has_any_move(nxt + 1):
                return nxt
        return None

    def has_any_move(self, player):
        for i in range(len(self.board)):
            for j in range(len(self.board[0])):
                if self.get_flips(i, j, player): return True
        return False

    # ---- イベント駆動・毎ターン処理 ----
    def prepare_predictions(self):
        r, c = len(self.board), len(self.board[0])
        nt = self.turn_count + 1
        
        self.next_gravity = random.choice(list(GRAVITY_DIRECTIONS.keys())) if (self.settings.get("gravity") and nt % self.settings.get("gravity_interval", 5) == 0) else None
        self.next_mirror = random.choice(MIRROR_SIDES) if (self.settings.get("mirror") and nt % self.settings.get("mirror_interval", 5) == 0) else None
        
        self.next_destroy_targets = []
        if self.settings.get("destroy") and nt % self.settings.get("destroy_interval", 5) == 0:
            dc = self.settings.get("destroy_count", 1)
            valid_cells = [(i, j) for i in range(r) for j in range(c) if self.board[i][j] != HOLE]
            self.next_destroy_targets = random.sample(valid_cells, min(dc, len(valid_cells)))

        self.next_flip_limit_event = False
        if self.settings.get("flip_limit_event"):
            c_idx = (self.current_player_index + 1) % len(self.players)
            if self.flip_mission_counters[c_idx] - 1 <= 0:
                self.next_flip_limit_event = True

    def after_turn_events(self):
        # 1. 寿命システム経過処理
        if self.settings.get("life"):
            for i in range(len(self.board)):
                for j in range(len(self.board[0])):
                    if self.board[i][j] > EMPTY and self.ages[i][j] is not None:
                        self.ages[i][j] += 1
                        if self.ages[i][j] >= self.settings["life_length"]:
                            self.board[i][j] = EMPTY
                            self.ages[i][j] = None
                            self.health[i][j] = None

        # 2. 特殊発動系
        triggered = []
        if self.next_gravity:
            self.apply_gravity(self.next_gravity)
            triggered.append(f"局所重力引力 [{self.next_gravity}] が牙を剥いた！")
        if self.next_mirror:
            self.apply_mirror(self.next_mirror)
            triggered.append(f"空間が歪み、[{self.next_mirror}] が反転コピーされた！")
        if self.next_destroy_targets:
            for (ri, ci) in self.next_destroy_targets:
                self.board[ri][ci] = HOLE
                self.holes.add((ri, ci))
                self.ages[ri][ci] = None
                self.health[ri][ci] = None
            triggered.append(f"大異変！{len(self.next_destroy_targets)}箇所のマスが奈落に崩壊した！")

        if self.settings.get("flip_limit_event"):
            for idx in range(len(self.players)):
                if idx == self.current_player_index:
                    if self.next_flip_limit_event:
                        self.flip_mission_counters[idx] = self.settings.get("flip_limit_interval", 5)
                        self.flip_mission_targets[idx] = random.randint(1, 4)
                    else:
                        self.flip_mission_counters[idx] -= 1

        if triggered:
            self.popup_event_window("\n".join(triggered))

    def apply_gravity(self, direction):
        dr, dc = GRAVITY_DIRECTIONS[direction]
        r, c = len(self.board), len(self.board[0])
        
        if direction == "下":
            for j in range(c):
                write_ptr = r - 1
                for i in range(r - 1, -1, -1):
                    if self.board[i][j] == HOLE: continue
                    if self.board[i][j] != EMPTY:
                        if i != write_ptr:
                            self.move_cell_data(i, j, write_ptr, j)
                        write_ptr -= 1
        elif direction == "上":
            for j in range(c):
                write_ptr = 0
                for i in range(r):
                    if self.board[i][j] == HOLE: continue
                    if self.board[i][j] != EMPTY:
                        if i != write_ptr:
                            self.move_cell_data(i, j, write_ptr, j)
                        write_ptr += 1
        elif direction == "右":
            for i in range(r):
                write_ptr = c - 1
                for j in range(c - 1, -1, -1):
                    if self.board[i][j] == HOLE: continue
                    if self.board[i][j] != EMPTY:
                        if j != write_ptr:
                            self.move_cell_data(i, j, i, write_ptr)
                        write_ptr -= 1
        elif direction == "左":
            for i in range(r):
                write_ptr = 0
                for j in range(c):
                    if self.board[i][j] == HOLE: continue
                    if self.board[i][j] != EMPTY:
                        if j != write_ptr:
                            self.move_cell_data(i, j, i, write_ptr)
                        write_ptr += 1

    def move_cell_data(self, fr, fc, tr, tc):
        self.board[tr][tc] = self.board[fr][fc]
        self.ages[tr][tc] = self.ages[fr][fc]
        self.health[tr][tc] = self.health[fr][fc]
        self.board[fr][fc] = EMPTY
        self.ages[fr][fc] = None
        self.health[fr][fc] = None

    def apply_mirror(self, side):
        r, c = len(self.board), len(self.board[0])
        if side == "上半分":
            for i in range(r // 2):
                for j in range(c):
                    self.mirror_copy(i, j, r - 1 - i, j)
        elif side == "下半分":
            for i in range((r + 1) // 2, r):
                for j in range(c):
                    self.mirror_copy(i, j, r - 1 - i, j)
        elif side == "左半分":
            for i in range(r):
                for j in range(c // 2):
                    self.mirror_copy(i, j, i, c - 1 - j)
        elif side == "右半分":
            for i in range(r):
                for j in range((c + 1) // 2, c):
                    self.mirror_copy(i, j, i, c - 1 - j)

    def mirror_copy(self, fr, fc, tr, tc):
        if self.board[tr][tc] == HOLE or self.board[fr][fc] == HOLE: return
        self.board[tr][tc] = self.board[fr][fc]
        self.ages[tr][tc] = self.ages[fr][fc]
        self.health[tr][tc] = self.health[fr][fc]

    def is_outer_cell(self, r, col):
        return r == 0 or r == len(self.board)-1 or col == 0 or col == len(self.board[0])-1

    def expand_board(self):
        r, c = len(self.board), len(self.board[0])
        new_board = [[EMPTY for _ in range(c+2)] for _ in range(r+2)]
        new_ages = [[None for _ in range(c+2)] for _ in range(r+2)]
        new_health = [[None for _ in range(c+2)] for _ in range(r+2)]
        
        for i in range(r):
            for j in range(c):
                new_board[i+1][j+1] = self.board[i][j]
                new_ages[i+1][j+1] = self.ages[i][j]
                new_health[i+1][j+1] = self.health[i][j]

        # 奈落穴の位置情報もシフト
        self.holes = set(((ri+1, ci+1) for (ri, ci) in self.holes))
        self.board = new_board
        self.ages = new_ages
        self.health = new_health
        self.cell_scores = self.generate_random_scores(r+2, c+2)

    def popup_event_window(self, msg):
        self.close_event_window()
        self.event_window = tk.Toplevel(self.root)
        self.event_window.title("EVENT TRIGGERED")
        self.event_window.geometry("420x180")
        self.event_window.config(bg=PANEL_BG, padx=15, pady=15)
        self.event_window.transient(self.root)
        
        tk.Label(self.event_window, text="🚨 特殊災害・環境変化イベント発生 🚨", font=FONT_SECTION, fg=DANGER, bg=PANEL_BG).pack(pady=5)
        tk.Label(self.event_window, text=msg, font=FONT_UI, fg=TEXT, bg=PANEL_BG, justify=tk.LEFT).pack(pady=10)
        self.styled_button(self.event_window, "了解ーー。", self.close_event_window, primary=True).pack(pady=5)

    def close_event_window(self):
        if self.event_window and self.event_window.winfo_exists():
            self.event_window.destroy()
        self.event_window = None

    # ---- プレイヤー・インタラクション（クリック / 通信同調） ----
    def on_canvas_click(self, event):
        if not self.game_started or self.game_over: return
        if not self.is_human_turn(): return

        c = (event.x - self.ox) // self.cell_size
        r = (event.y - self.oy) // self.cell_size
        
        if 0 <= r < len(self.board) and 0 <= c < len(self.board[0]):
            flips = self.get_flips(r, c, self.current_player())
            if flips:
                self.place_piece(r, c)

    def place_piece(self, row, col):
        # 自分が打った人間かつオンラインなら相手へ送信
        if self.is_online and self.current_player_index == self.my_player_index:
            packet = {
                "type": "MOVE",
                "data": {"row": row, "col": col}
            }
            try:
                self.socket.sendall(json.dumps(packet).encode('utf-8'))
            except:
                self.status.config(text="パケット送信失敗。同期ズレが起きたかも。")
                return

        self._execute_local_place(row, col)

    def _execute_local_place(self, row, col):
        player = self.current_player()
        flips = self.get_flips(row, col, player)
        if not flips: return

        self.board[row][col] = player
        if self.settings.get("life"): self.ages[row][col] = 0
        if self.settings.get("health"): self.health[row][col] = self.settings.get("health_count")

        for r, c in flips:
            if self.settings.get("health") and self.health[r][c] is not None:
                self.health[r][c] -= 1
                if self.health[r][c] <= 0:
                    self.board[r][c] = EMPTY
                    self.ages[r][c] = None
                    self.health[r][c] = None
                    continue
            self.board[r][c] = player
            if self.settings.get("life"): self.ages[r][c] = 0 # ひっくり返されたらリセット

        if self.settings.get("expand") and self.settings.get("expand_count", 0) > 0 and self.is_outer_cell(row, col):
            self.expand_board()
            self.settings["expand_count"] -= 1

        self.turn_count += 1
        self.after_turn_events()

        next_index = self.next_player_with_move()
        if next_index is None:
            self.end_game()
            return
        
        self.current_player_index = next_index
        self.prepare_predictions()
        self.draw_board()
        self.schedule_cpu_if_needed()
        self.schedule_ai_if_needed()

    # ---- 外部NPC・AI（ChatGPT）スケジューリング ----
    def schedule_cpu_if_needed(self):
        if self.game_over: return
        if self.is_online and self.current_player_index != self.my_player_index: return
        if self.players[self.current_player_index]["kind"] == "CPU":
            self.root.after(600, self.cpu_move)

    def schedule_ai_if_needed(self):
        if self.game_over: return
        if self.is_online and self.current_player_index != self.my_player_index: return
        if self.players[self.current_player_index]["kind"] == "AI":
            self.root.after(400, lambda: threading.Thread(target=self.ai_move_async, daemon=True).start())

    def cpu_move(self):
        p = self.current_player()
        moves = [(i, j) for i in range(len(self.board)) for j in range(len(self.board[0])) if self.get_flips(i, j, p)]
        if moves:
            # 簡易優先度：基本点数＋ひっくり返せる数
            best_move = random.choice(moves)
            best_score = -999
            for (r, col) in moves:
                score = len(self.get_flips(r, col, p))
                if self.settings.get("total_score"): score += self.cell_scores[r][col]
                if score > best_score:
                    best_score = score
                    best_move = (r, col)
            self.place_piece(best_move[0], best_move[1])

    def ai_move_async(self):
        p = self.current_player()
        moves = [(i, j) for i in range(len(self.board)) for j in range(len(self.board[0])) if self.get_flips(i, j, p)]
        if not moves: return

        # 盤面状況などの情報をシリアライズしてプロンプト構築
        board_str = "\n".join([" ".join([str(cell) for cell in row]) for row in self.board])
        score_str = "\n".join([" ".join([str(s) for s in row]) for row in self.cell_scores])
        
        prompt = f"""
【現在の盤面 (0=空, -1=奈落穴, 1〜4=各PL)】
{board_str}

【マスマス点数制の各マススコア】
{score_str}

あなたのプレイヤー番号: {p}P
選択可能な合法手一覧: {moves}

【予定されている次ターンの特殊イベント】
重力: {self.next_gravity if self.next_gravity else "なし"}
ミラー: {self.next_mirror if self.next_mirror else "なし"}
破壊ターゲット: {self.next_destroy_targets if self.next_destroy_targets else "なし"}
枚数指定ルール強制: {self.next_flip_limit_event} (指定枚数: {self.flip_mission_targets[self.current_player_index] if self.settings.get('flip_limit_event') else '無制限'})
"""
        try:
            reply = chatbot.ask(system_setting, prompt)
            match = re.search(r"【選択マス】\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", reply)
            if match:
                r, c = int(match.group(1)), int(match.group(2))
                if (r, c) in moves:
                    self.root.after(10, lambda: self.place_piece(r, c))
                    return
            # パース漏れや非合法手はランダムフォールバック
            raise ValueError
        except:
            r, c = random.choice(moves)
            self.root.after(10, lambda: self.place_piece(r, c))

    def end_game(self):
        self.game_over = True
        self.draw_board()
        
        scores = self.calculate_scores()
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=not self.settings.get("reverse_judgment"))
        
        win_p, win_s = ranking[0]
        w_name, _, _ = PLAYER_COLORS[win_p]
        
        res_txt = f"👑 試合終了 👑\n\n勝者: {win_p}P ({w_name}) - {win_s}点\n\n"
        for idx, (p, s) in enumerate(ranking):
            res_txt += f" {idx+1}位: {p}P ({s}点)\n"
            
        messagebox.showinfo("リザルト", res_txt)

    def start_game(self):
        if len(self.players) < 2: return
        
        self.settings = self.collect_settings()
        self.board = self.create_initial_board()
        self.cell_scores = self.generate_random_scores(len(self.board), len(self.board[0]))
        
        r, c = len(self.board), len(self.board[0])
        self.ages = [[None for _ in range(c)] for _ in range(r)]
        self.health = [[None for _ in range(c)] for _ in range(r)]
        self.flip_mission_counters = [self.settings.get("flip_limit_interval", 5) for _ in self.players]
        self.flip_mission_targets = [random.randint(1, 4) for _ in self.players]

        self.prepare_predictions()

        # ホスト側の場合は設定内容をすべてゲストへ送信して同期
        if self.is_online and self.is_host:
            packet = {
                "type": "START",
                "data": {
                    "settings": self.settings,
                    "board": self.board,
                    "cell_scores": self.cell_scores,
                    "holes": list(self.holes),
                    "flip_mission_targets": self.flip_mission_targets
                }
            }
            try:
                self.socket.sendall(json.dumps(packet).encode('utf-8'))
            except:
                messagebox.showerror("通信エラー", "ゲスト端末へのデータ初期同期送信に失敗したーー。")
                return

        self.current_player_index = 0
        self.turn_count = 0
        self.game_started = True
        self.game_over = False

        self.show_game_controls()
        self.draw_board()
        self.schedule_cpu_if_needed()
        self.schedule_ai_if_needed()

if __name__ == "__main__":
    root = tk.Tk()
    app = OthelloApp(root)
    root.mainloop()
