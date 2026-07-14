import random
import tkinter as tk
from tkinter import messagebox
import os
import json
from dotenv import load_dotenv
import threading
# 事前に pip install websocket-client しておいてね！
import websocket 

EMPTY = 0
HOLE = -1
load_dotenv(".env")

PLAYER_COLORS = {
    1: ("黒", "#111827", "#f8fafc"),
    2: ("白", "#f8fafc", "#111827"),
    3: ("赤", "#e05263", "white"),
    4: ("青", "#3b82f6", "white"),
}

DIRECTIONS = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]

GRAVITY_DIRECTIONS = {
    "上": (-1, 0),
    "下": (1, 0),
    "左": (0, -1),
    "右": (0, 1),
}

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
        self.root.title("Special Othello (Online)")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self.configure_theme()

        self.players = []
        self.board = []
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
        self.event_window = None

        # 固定されたRenderのWebSocket用URL
        self.SERVER_URL = "wss://last-26c0.onrender.com/ws"
        self.has_online = False
        self.ws = None
        self.is_host = False

        self.settings = {}
        self.vars = {}

        self.build_layout()
        self.reset_settings()
        self.show_settings_screen()

    def configure_theme(self):
        self.root.configure(bg=APP_BG)
        self.root.option_add("*Font", FONT_UI)
        self.root.option_add("*Background", PANEL_BG)
        self.root.option_add("*Foreground", TEXT)
        self.root.option_add("*LabelFrame.Background", PANEL_BG)
        self.root.option_add("*LabelFrame.Foreground", TEXT)
        self.root.option_add("*Button.Background", PANEL_ALT)
        self.root.option_add("*Button.Foreground", TEXT)
        self.root.option_add("*Button.ActiveBackground", ACCENT)
        self.root.option_add("*Button.ActiveForeground", "#111827")
        self.root.option_add("*Checkbutton.SelectColor", PANEL_ALT)
        self.root.option_add("*Entry.Background", "#0f151b")
        self.root.option_add("*Entry.Foreground", TEXT)
        self.root.option_add("*Spinbox.Background", "#0f151b")
        self.root.option_add("*Spinbox.Foreground", TEXT)
        self.root.option_add("*Scale.Background", PANEL_BG)
        self.root.option_add("*Scale.TroughColor", "#0f151b")

    def styled_button(self, parent, text, command, primary=False):
        bg = ACCENT if primary else PANEL_ALT
        fg = "#111827" if primary else TEXT
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=FONT_BUTTON,
            bg=bg,
            fg=fg,
            activebackground="#ffd86b" if primary else "#2c3744",
            activeforeground="#111827" if primary else TEXT,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=8,
            cursor="hand2",
        )

    def section_frame(self, title, expand=False):
        frame = tk.LabelFrame(
            self.left,
            text=title,
            padx=12,
            pady=10,
            bg=PANEL_BG,
            fg=TEXT,
            font=FONT_SECTION,
            relief=tk.FLAT,
            bd=1,
            highlightbackground="#27313c",
            highlightcolor="#27313c",
            highlightthickness=1,
        )
        frame.pack(fill=tk.BOTH if expand else tk.X, expand=expand, pady=6)
        return frame

    def build_layout(self):
        self.left = tk.Frame(self.root, width=390, bg=PANEL_BG)
        self.left.pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=14)
        self.left.pack_propagate(False)

        self.right = tk.Frame(self.root, bg=APP_BG)
        self.right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 14), pady=14)

        self.title_label = tk.Label(self.left, text="特殊オセロ設定", font=FONT_TITLE, bg=PANEL_BG, fg=TEXT)
        self.title_label.pack(anchor="w", pady=(0, 10))

        self.canvas = tk.Canvas(self.right, bg=APP_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.status = tk.Label(self.right, text="", font=FONT_UI, anchor="w", bg=APP_BG, fg=MUTED)
        self.status.pack(fill=tk.X, pady=(10, 0))

    def reset_settings(self):
        self.players = [{"kind": "人間"}, {"kind": "人間"}]
        self.holes = set()

        self.vars = {
            "rows": tk.IntVar(value=8),
            "cols": tk.IntVar(value=8),
            "wrap": tk.BooleanVar(value=False),
            "hole_count": tk.IntVar(value=0),
            "blackout": tk.BooleanVar(value=False),
            "blackout_duration": tk.IntVar(value=5),
            "blackout_interval": tk.IntVar(value=5),
            "gravity": tk.BooleanVar(value=False),
            "gravity_interval": tk.IntVar(value=5),
            "gravity_notice": tk.BooleanVar(value=False),
            "mirror": tk.BooleanVar(value=False),
            "mirror_interval": tk.IntVar(value=5),
            "mirror_notice": tk.BooleanVar(value=False),
            "destroy": tk.BooleanVar(value=False),
            "destroy_count": tk.IntVar(value=1),
            "destroy_interval": tk.IntVar(value=5),
            "destroy_notice": tk.BooleanVar(value=False),
            "expand": tk.BooleanVar(value=False),
            "expand_count": tk.IntVar(value=3),
            "life": tk.BooleanVar(value=False),
            "life_length": tk.IntVar(value=5),
            "life_show": tk.BooleanVar(value=False),
            "health": tk.BooleanVar(value=False),
            "health_count": tk.IntVar(value=3),
            "health_show": tk.BooleanVar(value=False),
            "flip_limit_event": tk.BooleanVar(value=False),
            "flip_limit_interval": tk.IntVar(value=5),
            "flip_limit_notice": tk.BooleanVar(value=False),
            "flip_limit": tk.BooleanVar(value=False),
            "flip_limit_count": tk.IntVar(value=3),
            "reverse_judgment": tk.BooleanVar(value=False),
            "total_score": tk.BooleanVar(value=False),
            "total_score_count": tk.IntVar(value=5),
            "total_score_show": tk.BooleanVar(value=False),
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

        if self.ws:
            try: self.ws.close()
            except: pass
            self.ws = None
        self.has_online = False

        self.add_player_section()
        self.add_board_section()

        button_row = tk.Frame(self.left, bg=PANEL_BG)
        button_row.pack(fill=tk.X, pady=10)
        self.styled_button(button_row, "試合開始", self.start_game, primary=True).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5)
        )
        self.styled_button(button_row, "設定リセット", self.reset_all_settings).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0)
        )

        self.add_event_section()
        self.draw_preview_board()

    def add_player_section(self):
        frame = self.section_frame("人数変更")
        self.player_label = tk.Label(frame, text="", bg=PANEL_BG, fg=MUTED, font=FONT_UI)
        self.player_label.pack(anchor="w")
        row = tk.Frame(frame, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=(5, 0))
        self.styled_button(row, "CPU追加", lambda: self.add_player("CPU")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.styled_button(row, "オンライン追加", lambda: self.add_player("オンライン")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.styled_button(row, "人数追加", lambda: self.add_player("人間")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.styled_button(row, "1人削除", self.remove_player).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.update_player_label()

    def add_board_section(self):
        frame = self.section_frame("盤面変更")

        self.dimension_control(frame, "縦", "rows", 4, 24)
        self.dimension_control(frame, "横", "cols", 4, 24)

        tk.Checkbutton(frame, text="循環", variable=self.vars["wrap"], bg=PANEL_BG, fg=TEXT, activebackground=PANEL_BG, activeforeground=TEXT).pack(anchor="w")

        hole_row = tk.Frame(frame, bg=PANEL_BG)
        hole_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(hole_row, text="穴の数").pack(side=tk.LEFT)
        tk.Spinbox(
            hole_row,
            from_=0,
            to=288,
            width=5,
            textvariable=self.vars["hole_count"],
            command=self.clamp_hole_count,
        ).pack(side=tk.LEFT, padx=5)
        self.styled_button(hole_row, "実行", self.generate_random_holes).pack(side=tk.LEFT, padx=4)
        tk.Label(frame, text="右の盤面クリックでも穴を指定できます", bg=PANEL_BG, fg=MUTED, font=FONT_SMALL).pack(anchor="w", pady=(5, 0))

    def dimension_control(self, parent, label, key, start, end):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=f"{label}マス", width=7, anchor="w", bg=PANEL_BG, fg=TEXT).pack(side=tk.LEFT)
        scale = tk.Scale(
            row,
            from_=start,
            to=end,
            orient=tk.HORIZONTAL,
            resolution=2,
            showvalue=False,
            variable=self.vars[key],
            command=lambda _value: self.on_dimension_change(),
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Spinbox(
            row,
            from_=start,
            to=end,
            increment=2,
            width=5,
            textvariable=self.vars[key],
            command=self.on_dimension_change,
        ).pack(side=tk.LEFT, padx=(6, 0))

    def event_specs(self):
        return [
            ("暗転", "blackout", [("時間", "blackout_duration", 1, 99), ("間隔", "blackout_interval", 0, 99)], None, "予告"),
            ("重力", "gravity", [("間隔", "gravity_interval", 0, 99)], "gravity_notice", "予告"),
            ("鏡", "mirror", [("間隔", "mirror_interval", 0, 99)], "mirror_notice", "予告"),
            ("無差別破壊", "destroy", [("破壊", "destroy_count", 1, 98), ("間隔", "destroy_interval", 1, 99)], "destroy_notice", "予告"),
            ("盤面拡大", "expand", [("回数", "expand_count", 1, 10)], None, "予告"),
            ("寿命", "life", [("長さ", "life_length", 1, 99)], "life_show", "表示"),
            ("体力", "health", [("回数", "health_count", 1, 99)], "health_show", "表示"),
            ("反転個数指定", "flip_limit_event", [("間隔", "flip_limit_interval", 1, 99)], "flip_limit_notice", "予告"),
            ("反転能力上限", "flip_limit", [("上限", "flip_limit_count", 1, 99)], None, "予告"),
            ("判定逆転", "reverse_judgment", [], None, "予告"),
            ("総得点オセロ", "total_score", [("上限得点", "total_score_count", 1, 99)], "total_score_show", "表示"),
        ]

    def add_event_section(self):
        frame = self.section_frame("イベント設定")
        tk.Label(
            frame,
            text="イベント設定は別ウィンドウで変更できます。",
            bg=PANEL_BG,
            fg=MUTED,
            font=FONT_SMALL,
            anchor="w",
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        self.styled_button(frame, "イベント設定を開く", self.open_event_window, primary=True).pack(fill=tk.X)

    def build_event_controls(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0, bg=PANEL_BG)
        scrollbar = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner_frame = tk.Frame(canvas, bg=PANEL_BG)

        inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for title, enabled_key, number_specs, option_key, option_text in self.event_specs():
            self.event_row(inner_frame, title, enabled_key, number_specs, option_key, option_text)

    def open_event_window(self):
        if self.event_window is not None and self.event_window.winfo_exists():
            self.event_window.lift()
            self.event_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.event_window = window
        window.title("イベント設定")
        window.geometry("460x560+120+120")
        window.minsize(420, 420)
        window.configure(bg=PANEL_BG)
        window.protocol("WM_DELETE_WINDOW", self.close_event_window)

        header = tk.Frame(window, bg=PANEL_BG)
        header.pack(fill=tk.X, padx=14, pady=(14, 6))
        tk.Label(header, text="イベント設定", bg=PANEL_BG, fg=TEXT, font=(FONT_FAMILY, 16, "bold")).pack(side=tk.LEFT)
        self.styled_button(header, "閉じる", self.close_event_window).pack(side=tk.RIGHT)

        body = tk.Frame(window, bg=PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        self.build_event_controls(body)

    def close_event_window(self):
        if self.event_window is not None and self.event_window.winfo_exists():
            self.event_window.destroy()
        self.event_window = None

    def event_row(self, parent, title, enabled_key, number_specs, option_key=None, option_text="予告"):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=3)
        tk.Checkbutton(row, text=title, variable=self.vars[enabled_key], width=12, anchor="w", bg=PANEL_BG, fg=TEXT, activebackground=PANEL_BG, activeforeground=TEXT).pack(side=tk.LEFT)
        for label, key, start, end in number_specs:
            tk.Label(row, text=label, bg=PANEL_BG, fg=MUTED, font=FONT_SMALL).pack(side=tk.LEFT)
            tk.Spinbox(row, from_=start, to=end, width=4, textvariable=self.vars[key]).pack(side=tk.LEFT, padx=(2, 5))
        if option_key:
            tk.Checkbutton(row, text=option_text, variable=self.vars[option_key], bg=PANEL_BG, fg=TEXT, activebackground=PANEL_BG, activeforeground=TEXT).pack(side=tk.LEFT)

    def add_player(self, kind):
        if len(self.players) >= 4:
            messagebox.showinfo("人数変更", "人数は最大4人です。")
            return
        self.players.append({"kind": kind})
        self.update_player_label()
        self.draw_preview_board()

    def remove_player(self):
        if len(self.players) <= 1:
            messagebox.showinfo("人数変更", "一人は残してください。")
            return
        self.players.pop()
        self.update_player_label()
        self.draw_preview_board()

    def update_player_label(self):
        counts = []
        for i, player in enumerate(self.players, start=1):
            counts.append(f"{PLAYER_COLORS[i][0]}:{player['kind']}")
        self.player_label.config(text=f"{len(self.players)}人対戦  " + " / ".join(counts))

    def reset_all_settings(self):
        self.reset_settings()
        self.show_settings_screen()

    def on_dimension_change(self):
        self.force_even_dimensions()
        self.remove_invalid_holes()
        self.clamp_hole_count()
        self.draw_preview_board()

    def force_even_dimensions(self):
        for key in ("rows", "cols"):
            value = self.vars[key].get()
            value = max(4, min(24, value))
            if value % 2:
                value += 1
            self.vars[key].set(max(4, min(24, value)))

    def max_holes(self):
        return (self.vars["rows"].get() * self.vars["cols"].get()) // 2

    def generate_random_scores(self, rows, cols):
        if self.settings.get("total_score"):
            max_score = self.settings.get("total_score_count", 99)
        else:
            max_score = 1
        return [[random.randint(1, max_score) for _ in range(cols)] for _ in range(rows)]

    def clamp_hole_count(self):
        value = max(0, min(self.max_holes(), self.vars["hole_count"].get()))
        self.vars["hole_count"].set(value)

    def initial_cells(self, rows=None, cols=None, player_count=None):
        rows = rows or self.vars["rows"].get()
        cols = cols or self.vars["cols"].get()
        player_count = player_count or len(self.players)
        top = rows // 2 - 2
        left = cols // 2 - 2
        if player_count < 2:
            return {}
        pattern = {
            2: ["0000", "0210", "0120", "0000"],
            3: ["0200", "1310", "0232", "0010"],
            4: ["0430", "4123", "2341", "0210"],
        }[player_count]
        cells = {}
        for r, line in enumerate(pattern):
            for c, char in enumerate(line):
                value = int(char)
                if value:
                    cells[(top + r, left + c)] = value
        return cells

    def remove_invalid_holes(self):
        rows = self.vars["rows"].get()
        cols = self.vars["cols"].get()
        initial = set(self.initial_cells(rows, cols).keys())
        self.holes = {
            cell for cell in self.holes
            if 0 <= cell[0] < rows and 0 <= cell[1] < cols and cell not in initial
        }

    def generate_random_holes(self):
        self.force_even_dimensions()
        self.clamp_hole_count()
        rows = self.vars["rows"].get()
        cols = self.vars["cols"].get()
        initial = set(self.initial_cells(rows, cols).keys())
        candidates = [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if (r, c) not in initial
        ]
        count = min(self.vars["hole_count"].get(), len(candidates))
        self.holes = set(random.sample(candidates, count))
        self.draw_preview_board()

    def collect_settings(self):
        self.force_even_dimensions()
        self.clamp_hole_count()
        destroy_interval = max(1, self.vars["destroy_interval"].get())
        self.vars["destroy_count"].set(min(self.vars["destroy_count"].get(), destroy_interval - 1 or 1))
        return {key: var.get() for key, var in self.vars.items()}

    def start_game(self):
        if len(self.players) < 2:
            messagebox.showinfo("人数変更", "人数は最低2人です。")
            return

        self.settings = self.collect_settings()

        self.has_online = any(p["kind"] == "オンライン" for p in self.players)
        if self.has_online and not self.ws:
            if not self.setup_online_connection():
                return
            if not self.is_host:
                messagebox.showinfo("待機", "ホストが試合を開始するのを待っているってことーー。")
                return

        self.init_game_states()
        
        if self.has_online and self.is_host:
            self.send_sync_packet()

        self.launch_game_ui()

    def init_game_states(self):
        if self.settings.get("gravity") and self.settings.get("gravity_notice"):
            self.next_gravity = random.choice(list(GRAVITY_DIRECTIONS))
        else:
            self.next_gravity = None
        if self.settings.get("mirror") and self.settings.get("mirror_notice"):
            self.next_mirror = random.choice(MIRROR_SIDES)
        else:
            self.next_mirror = None

        self.board = self.create_initial_board()
        
        if self.settings.get("destroy") and self.settings.get("destroy_notice"):
            self.next_destroy_targets = self.random_piece_targets(self.settings["destroy_count"])
        else:
            self.next_destroy_targets = []

        self.cell_scores = self.generate_random_scores(len(self.board), len(self.board[0]))
        self.ages = [[None for _ in row] for row in self.board]
        self.health = [[None for _ in row] for row in self.board]
        self.flip_mission_counters = [self.settings.get("flip_limit_interval", 5) for _ in self.players]
        self.flip_mission_targets = [random.randint(1, 4) for _ in self.players]
        self.is_bonus_turn = False
        self.current_player_index = 0
        self.turn_count = 0
        self.game_started = True
        self.game_over = False
        self.prepare_predictions()

    def launch_game_ui(self):
        self.show_game_controls()
        self.draw_board()
        self.schedule_cpu_if_needed()

    def setup_online_connection(self):
        res = messagebox.askyesno("オンライン設定", "あなたがホスト（先攻・部屋を立てる側）ですか？")
        self.is_host = res
        
        try:
            # 固定されたURLへ接続
            self.ws = websocket.create_connection(self.SERVER_URL, timeout=10.0)
            messagebox.showinfo("接続完了", "Renderサーバーに接続できたってわけーー。さいこー！")
        except Exception as e:
            messagebox.showerror("エラー", f"Renderへの接続に失敗したってこと: {e}")
            return False

        threading.Thread(target=self.receive_online_loop, daemon=True).start()
        return True

    def send_sync_packet(self):
        packet = {
            "type": "sync",
            "settings": self.settings,
            "holes": list(self.holes),
            "cell_scores": self.cell_scores,
            "next_gravity": self.next_gravity,
            "next_mirror": self.next_mirror,
            "next_destroy_targets": self.next_destroy_targets,
            "flip_mission_targets": self.flip_mission_targets
        }
        try:
            self.ws.send(json.dumps(packet))
        except:
            pass

    def receive_online_loop(self):
        while True:
            try:
                msg = self.ws.recv()
                if not msg: break
                data = json.loads(msg)
                
                if data.get("type") == "sync" and not self.is_host:
                    self.settings = data["settings"]
                    self.holes = set(tuple(h) for h in data["holes"])
                    
                    self.board = self.create_initial_board()
                    self.cell_scores = data["cell_scores"]
                    self.next_gravity = data["next_gravity"]
                    self.next_mirror = data["next_mirror"]
                    self.next_destroy_targets = [tuple(t) for t in data["next_destroy_targets"]]
                    self.flip_mission_targets = data["flip_mission_targets"]
                    
                    self.ages = [[None for _ in row] for row in self.board]
                    self.health = [[None for _ in row] for row in self.board]
                    self.flip_mission_counters = [self.settings.get("flip_limit_interval", 5) for _ in self.players]
                    self.is_bonus_turn = False
                    self.current_player_index = 0
                    self.turn_count = 0
                    self.game_started = True
                    self.game_over = False
                    
                    self.root.after(0, self.launch_game_ui)
                
                elif data.get("type") == "move":
                    r, c = data["row"], data["col"]
                    if "next_events" in data:
                        ne = data["next_events"]
                        self.next_gravity = ne["gravity"]
                        self.next_mirror = ne["mirror"]
                        self.next_destroy_targets = [tuple(t) for t in ne["destroy_targets"]]
                        
                    self.root.after(0, lambda: self.remote_place_piece(r, c))
            except:
                break

        if not self.game_over and self.game_started:
            self.root.after(0, lambda: messagebox.showerror("切断", "オンライン通信が切れちゃったみたいーー。"))

    def remote_place_piece(self, row, col):
        if self.game_started and not self.game_over:
            if self.players[self.current_player_index]["kind"] == "オンライン":
                self.place_piece(row, col)

    def show_game_controls(self):
        self.close_event_window()
        self.clear_left()
        self.title_label.config(text="特殊オセロ")
        info = self.section_frame("対局情報")
        self.game_info = tk.Label(info, text="", justify=tk.LEFT, anchor="w", bg=PANEL_BG, fg=TEXT, font=FONT_UI)
        self.game_info.pack(fill=tk.X)
        self.styled_button(self.left, "設定画面に戻る", self.confirm_return_to_settings).pack(fill=tk.X, pady=10)

    def confirm_return_to_settings(self):
        if messagebox.askyesno("設定画面", "対局を終了して設定画面に戻りますか？"):
            self.show_settings_screen()

    def create_initial_board(self):
        rows = self.settings["rows"]
        cols = self.settings["cols"]
        board = [[EMPTY for _ in range(cols)] for _ in range(rows)]
        for r, c in self.holes:
            if 0 <= r < rows and 0 <= c < cols:
                board[r][c] = HOLE
        for (r, c), value in self.initial_cells(rows, cols, len(self.players)).items():
            board[r][c] = value
        return board

    def current_player(self):
        return self.current_player_index + 1

    def player_name(self, player):
        return PLAYER_COLORS[player][0]

    def is_human_turn(self):
        return self.players[self.current_player_index]["kind"] == "人間"

    def in_bounds(self, row, col):
        return 0 <= row < len(self.board) and 0 <= col < len(self.board[0])

    def next_pos(self, row, col, dr, dc):
        row += dr
        col += dc
        if self.settings.get("wrap"):
            return row % len(self.board), col % len(self.board[0])
        if self.in_bounds(row, col):
            return row, col
        return None

    def get_flips(self, row, col, player):
        if not self.in_bounds(row, col) or self.board[row][col] != EMPTY:
            return []

        flips = []
        max_steps = len(self.board) * len(self.board[0])
        line_limit = self.settings.get("flip_limit_count", 99) if self.settings.get("flip_limit") else 99

        for dr, dc in DIRECTIONS:
            pos = self.next_pos(row, col, dr, dc)
            line = []
            seen = set()
            while pos is not None and pos not in seen and len(seen) < max_steps:
                seen.add(pos)
                r, c = pos
                value = self.board[r][c]
                if value in (EMPTY, HOLE):
                    break
                if value == player:
                    if line:
                        flips.extend(line[:line_limit])
                    break
                line.append((r, c))
                pos = self.next_pos(r, c, dr, dc)
        return flips

    def valid_moves(self, player):
        moves = []
        for row in range(len(self.board)):
            for col in range(len(self.board[0])):
                if self.get_flips(row, col, player):
                    moves.append((row, col))
        return moves

    def next_player_with_move(self):
        for step in range(1, len(self.players) + 1):
            next_index = (self.current_player_index + step) % len(self.players)
            if self.valid_moves(next_index + 1):
                return next_index
        return None

    def place_piece(self, row, col):
        if self.game_over:
            return
        player = self.current_player()
        flips = self.get_flips(row, col, player)
        if not flips:
            self.status.config(text="そこには置けません")
            return

        self.board[row][col] = player
        self.ages[row][col] = 0 if self.settings.get("life") else None
        self.health[row][col] = self.settings.get("health_count") if self.settings.get("health") else None

        for r, c in flips:
            if self.settings.get("health") and self.health[r][c] is not None:
                self.health[r][c] -= 1
                if self.health[r][c] <= 0:
                    self.board[r][c] = EMPTY
                    self.ages[r][c] = None
                    self.health[r][c] = None
                    continue
            self.board[r][c] = player

        if self.settings.get("expand") and self.settings["expand_count"] > 0 and self.is_outer_cell(row, col):
            self.expand_board()
            self.settings["expand_count"] -= 1

        self.turn_count += 1
        self.after_turn_events()
        is_bonus = False
        if self.settings.get("flip_limit_event"):
            pi = self.current_player_index
            if getattr(self, "is_bonus_turn", False):
                pass
            else:
                if self.flip_mission_counters[pi] == 0:
                    if len(flips) == self.flip_mission_targets[pi]:
                        messagebox.showinfo("ミッション達成", f"ぴったり{len(flips)}個反転させました！連続手番を獲得します。")
                        is_bonus = True
                    self.flip_mission_counters[pi] = max(1, self.settings.get("flip_limit_interval", 5))
                else:
                    self.flip_mission_counters[pi] -= 1

        if self.has_online and self.is_host:
            self.prepare_predictions()

        if self.has_online and self.players[self.current_player_index]["kind"] != "オンライン":
            move_packet = {
                "type": "move",
                "row": row,
                "col": col
            }
            if self.is_host:
                move_packet["next_events"] = {
                    "gravity": self.next_gravity,
                    "mirror": self.next_mirror,
                    "destroy_targets": self.next_destroy_targets
                }
            try:
                self.ws.send(json.dumps(move_packet))
            except:
                pass

        if is_bonus and self.valid_moves(self.current_player()):
            next_index = self.current_player_index
            self.is_bonus_turn = True
        else:
            next_index = self.next_player_with_move()
            self.is_bonus_turn = False
            
        if next_index is None:
            self.end_game()
            return
        self.current_player_index = next_index
        
        if not (self.has_online and not self.is_host):
            self.prepare_predictions()
            
        self.draw_board()
        self.schedule_cpu_if_needed()

    def is_outer_cell(self, row, col):
        return row == 0 or col == 0 or row == len(self.board) - 1 or col == len(self.board[0]) - 1

    def after_turn_events(self):
        self.apply_life()
        if self.should_fire("gravity", "gravity_interval"):
            self.apply_gravity(self.next_gravity or random.choice(list(GRAVITY_DIRECTIONS)))
        if self.should_fire("mirror", "mirror_interval"):
            self.apply_mirror(self.next_mirror or random.choice(MIRROR_SIDES))
        if self.should_fire("destroy", "destroy_interval"):
            self.apply_destroy(self.next_destroy_targets)

    def should_fire(self, enabled_key, interval_key):
        if not self.settings.get(enabled_key):
            return False
        interval = self.settings.get(interval_key, 0)
        return interval == 0 or (self.turn_count > 0 and self.turn_count % interval == 0)

    def apply_life(self):
        if not self.settings.get("life"):
            return
        limit = self.settings["life_length"]
        for r in range(len(self.board)):
            for c in range(len(self.board[0])):
                if self.board[r][c] > 0 and self.ages[r][c] is not None:
                    self.ages[r][c] += 1
                    if self.ages[r][c] >= limit:
                        self.board[r][c] = EMPTY
                        self.ages[r][c] = None
                        self.health[r][c] = None

    def apply_gravity(self, direction_name):
        dr, dc = GRAVITY_DIRECTIONS[direction_name]
        pieces = []
        holes = {(r, c) for r, row in enumerate(self.board) for c, value in enumerate(row) if value == HOLE}
        for r in range(len(self.board)):
            for c in range(len(self.board[0])):
                if self.board[r][c] > 0:
                    pieces.append((r, c, self.board[r][c], self.ages[r][c], self.health[r][c]))
                    self.board[r][c] = EMPTY
                    self.ages[r][c] = None
                    self.health[r][c] = None
        pieces.sort(key=lambda item: item[0] * dr + item[1] * dc, reverse=True)
        occupied = set(holes)
        for r, c, value, age, hp in pieces:
            nr, nc = r, c
            while True:
                test = (nr + dr, nc + dc)
                if not self.in_bounds(*test) or test in occupied:
                    break
                nr, nc = test
            self.board[nr][nc] = value
            self.ages[nr][nc] = age
            self.health[nr][nc] = hp
            occupied.add((nr, nc))
        self.next_gravity = None

    def apply_mirror(self, side):
        rows = len(self.board)
        cols = len(self.board[0])
        if side in ("上半分", "下半分"):
            source_rows = range(0, rows // 2) if side == "上半分" else range(rows // 2, rows)
            for r in source_rows:
                target_r = rows - 1 - r
                for c in range(cols):
                    self.copy_cell(r, c, target_r, c)
        else:
            source_cols = range(0, cols // 2) if side == "左半分" else range(cols // 2, cols)
            for c in source_cols:
                target_c = cols - 1 - c
                for r in range(rows):
                    self.copy_cell(r, c, r, target_c)
        self.next_mirror = None

    def copy_cell(self, sr, sc, tr, tc):
        self.board[tr][tc] = self.board[sr][sc]
        self.ages[tr][tc] = self.ages[sr][sc]
        self.health[tr][tc] = self.health[sr][sc]

    def apply_destroy(self, targets):
        if not targets:
            targets = self.random_piece_targets(self.settings["destroy_count"])
        for r, c in targets:
            if self.in_bounds(r, c) and self.board[r][c] > 0:
                self.board[r][c] = EMPTY
                self.ages[r][c] = None
                self.health[r][c] = None
        self.next_destroy_targets = []

    def random_piece_targets(self, count):
        pieces = [
            (r, c)
            for r in range(len(self.board))
            for c in range(len(self.board[0]))
            if self.board[r][c] > 0
        ]
        return random.sample(pieces, min(count, len(pieces))) if pieces else []

    def expand_board(self):
        old_rows = len(self.board)
        old_cols = len(self.board[0])
        if old_rows >= 24 or old_cols >= 24:
            return
        old_board = [row[:] for row in self.board]
        old_ages = [row[:] for row in self.ages]
        old_health = [row[:] for row in self.health]
        new_rows = min(24, old_rows + 2)
        new_cols = min(24, old_cols + 2)
        self.board = [[EMPTY for _ in range(new_cols)] for _ in range(new_rows)]
        self.ages = [[None for _ in range(new_cols)] for _ in range(new_rows)]
        self.health = [[None for _ in range(new_cols)] for _ in range(new_rows)]
        a = [[0 for _ in range(new_cols)] for _ in range(new_rows)]
        for i in range(new_rows):
            for j in range(new_cols):
                if i == 0 or j == 0 or i == new_rows - 1 or j == new_cols - 1:
                    a[i][j] = random.randint(1, self.settings.get("total_score_count", 99))
                else:
                    a[i][j] = self.cell_scores[i-1][j-1]
        row_shift = 1 if new_rows > old_rows else 0
        col_shift = 1 if new_cols > old_cols else 0
        for r in range(old_rows):
            for c in range(old_cols):
                nr = r + row_shift
                nc = c + col_shift
                self.board[nr][nc] = old_board[r][c]
                self.ages[nr][nc] = old_ages[r][c]
                self.health[nr][nc] = old_health[r][c]
        self.cell_scores = a
        messagebox.showinfo("盤面拡大", "盤面が拡大しました。")

    def prepare_predictions(self):
        if self.settings.get("gravity") and self.settings.get("gravity_notice"):
            if self.next_gravity is None:
                self.next_gravity = random.choice(list(GRAVITY_DIRECTIONS))
        else:
            self.next_gravity = None
        if self.settings.get("mirror") and self.settings.get("mirror_notice"):
            if self.next_mirror is None:
                self.next_mirror = random.choice(MIRROR_SIDES)
        else:
            self.next_mirror = None
        if self.settings.get("destroy") and self.settings.get("destroy_notice"):
            if not self.next_destroy_targets:
                self.next_destroy_targets = self.random_piece_targets(self.settings["destroy_count"])
        else:
            self.next_destroy_targets = []

    def schedule_cpu_if_needed(self):
        if self.game_started and not self.game_over:
            current_kind = self.players[self.current_player_index]["kind"]
            if current_kind == "CPU":
                self.root.after(500, self.cpu_move) 

    def cpu_move(self):
        if not self.game_started or self.game_over or self.is_human_turn():
            return
        moves = self.valid_moves(self.current_player())
        if moves:
            self.place_piece(*random.choice(moves))

    def on_canvas_click(self, event):
        cell = self.cell_from_event(event)
        if cell is None:
            return
        row, col = cell
        if not self.game_started:
            self.toggle_hole(row, col)
            return
        if self.is_human_turn():
            self.place_piece(row, col)

    def toggle_hole(self, row, col):
        self.force_even_dimensions()
        initial = set(self.initial_cells().keys())
        if (row, col) in initial:
            messagebox.showinfo("穴指定", "初期配置の場所には穴を作れません。")
            return
        if (row, col) in self.holes:
            self.holes.remove((row, col))
        else:
            if len(self.holes) >= self.max_holes():
                messagebox.showinfo("穴指定", "穴の数が上限に達しています。")
                return
            self.holes.add((row, col))
        self.vars["hole_count"].set(len(self.holes))
        self.draw_preview_board()

    def cell_from_event(self, event):
        if self.game_started and self.board:
            rows = len(self.board)
            counts_cols = len(self.board[0])
        else:
            rows = self.vars["rows"].get()
            counts_cols = self.vars["cols"].get()
        size, offset_x, offset_y = self.board_geometry(rows, counts_cols)
        col = int((event.x - offset_x) // size)
        row = int((event.y - offset_y) // size)
        if 0 <= row < rows and 0 <= col < counts_cols:
            return row, col
        return None

    def board_geometry(self, rows, cols):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        size = max(16, min((width - 48) // cols, (height - 48) // rows))
        offset_x = (width - size * cols) // 2
        offset_y = (height - size * rows) // 2
        return size, offset_x, offset_y

    def draw_preview_board(self):
        self.force_even_dimensions()
        rows = self.vars["rows"].get()
        cols = self.vars["cols"].get()
        preview = [[EMPTY for _ in range(cols)] for _ in range(rows)]
        for r, c in self.holes:
            if 0 <= r < rows and 0 <= c < cols:
                preview[r][c] = HOLE
        for (r, c), value in self.initial_cells(rows, cols, len(self.players)).items():
            preview[r][c] = value
        self.draw_grid(preview, title="初期配置プレビュー")
        self.status.config(text="設定を調整してから試合開始を押してください。")

    def game_event_info_lines(self):
        blackout = self.is_blackout_active()
        lines = []

        if blackout:
            lines.append(f"暗転中        {self.blackout_turn_label(blackout)}")
            lines.append("  候補マスだけ表示")
        elif self.settings.get("blackout"):
            lines.append(f"暗転          {self.blackout_turn_label(blackout)}")

        if self.next_gravity:
            lines.append(f"重力予告      {self.event_turn_label('gravity_interval')}")
            lines.append(f"  方向: {self.next_gravity}")
        elif self.settings.get("gravity"):
            lines.append(f"重力          {self.event_turn_label('gravity_interval')}")

        if self.next_mirror:
            lines.append(f"鏡予告        {self.event_turn_label('mirror_interval')}")
            lines.append(f"  対象: {self.next_mirror}")
        elif self.settings.get("mirror"):
            lines.append(f"鏡            {self.event_turn_label('mirror_interval')}")

        if self.next_destroy_targets:
            lines.append(f"破壊予告      {self.event_turn_label('destroy_interval')}")
            lines.append(f"  対象: {len(self.next_destroy_targets)}マス")
        elif self.settings.get("destroy"):
            lines.append(f"破壊          {self.event_turn_label('destroy_interval')}")

        return lines or ["発生予定なし"]

    def draw_board(self):
        self.draw_grid(self.board, title=None)
        counts = self.count_pieces()
        player = self.current_player()

        status_parts = [
            f"{self.turn_count}ターン目",
            f"手番: {self.player_name(player)} ({self.players[player - 1]['kind']})",
        ]
        status_parts.extend(f"{self.player_name(p)}:{counts.get(p, 0)}" for p in range(1, len(self.players) + 1))
        self.status.config(text="   ".join(status_parts))

        if hasattr(self, "game_info"):
            info = [
                "【対局】",
                f"ターン: {self.turn_count}",
                f"手番: {self.player_name(player)} ({self.players[player - 1]['kind']})",
                "",
                "【スコア】",
            ]
            info.extend(f"{self.player_name(p)}: {counts.get(p, 0)}" for p in range(1, len(self.players) + 1))
            info.extend(["", "【イベント】"])
            info.extend(self.game_event_info_lines())

            if self.settings.get("flip_limit_event"):
                info.extend(["", "【反転ミッション】"])
                for pi in range(len(self.players)):
                    p_name = self.player_name(pi + 1)
                    if self.flip_mission_counters[pi] == 0:
                        info.append(f"{p_name}: 今ターン {self.flip_mission_targets[pi]}個")
                    else:
                        info.append(f"{p_name}: あと{self.flip_mission_counters[pi]}回 / {self.flip_mission_targets[pi]}個")

            self.game_info.config(text="\n".join(info))

    def draw_grid(self, board, title=None):
        self.canvas.delete("all")
        rows = len(board)
        cols = len(board[0])
        size, offset_x, offset_y = self.board_geometry(rows, cols)
        blackout = self.is_blackout_active() if self.game_started else False
        valid = set(self.valid_moves(self.current_player())) if self.game_started and blackout else set()

        board_x1 = offset_x
        board_y1 = offset_y
        board_x2 = offset_x + size * cols
        board_y2 = offset_y + size * rows
        self.canvas.create_rectangle(board_x1 + 8, board_y1 + 10, board_x2 + 8, board_y2 + 10, fill="#070a0d", outline="")
        self.canvas.create_rectangle(board_x1 - 6, board_y1 - 6, board_x2 + 6, board_y2 + 6, fill=BOARD_DARK, outline="#25372f", width=2)

        if title:
            self.canvas.create_text(
                self.canvas.winfo_width() // 2,
                max(22, offset_y // 2),
                text=title,
                fill=TEXT,
                font=(FONT_FAMILY, 16, "bold"),
            )

        legal_moves = set(self.valid_moves(self.current_player())) if self.game_started else set()
        for r in range(rows):
            for c in range(cols):
                x1 = offset_x + c * size
                y1 = offset_y + r * size
                x2 = x1 + size
                y2 = y1 + size
                value = board[r][c]
                if value == HOLE:
                    fill = "#e5e7eb"
                elif blackout and (r, c) not in valid:
                    fill = "#0c0f12"
                else:
                    fill = BOARD_BG if (r + c) % 2 == 0 else BOARD_LIGHT
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=BOARD_DARK, fill=fill, width=1)
                if self.settings.get("total_score") and self.settings.get("total_score_show") and value != HOLE and hasattr(self, "cell_scores"):
                    if size >= 20:
                        self.canvas.create_text(
                            x1 + 4, y1 + 3,
                            text=str(self.cell_scores[r][c]),
                            fill="#dff7ea",
                            font=FONT_SMALL,
                            anchor="nw"
                        )

                if value > 0 and not (blackout and (r, c) not in valid):
                    name, color, text_color = PLAYER_COLORS[value]
                    pad = max(4, size // 9)
                    self.canvas.create_oval(x1 + pad + 2, y1 + pad + 3, x2 - pad + 2, y2 - pad + 3, fill="#06100b", outline="")
                    self.canvas.create_oval(x1 + pad, y1 + pad, x2 - pad, y2 - pad, fill=color, outline="#f8fafc" if value == 2 else "#05080b", width=2)
                    self.canvas.create_arc(x1 + pad + 4, y1 + pad + 4, x2 - pad - 4, y2 - pad - 4, start=70, extent=70, style=tk.ARC, outline="#ffffff", width=1)
                    if size >= 28:
                        badge_font = (FONT_FAMILY, max(8, min(12, size // 5)), "bold")
                        if self.settings.get("life_show") and self.ages and self.ages[r][c] is not None:
                            left = max(0, self.settings["life_length"] - self.ages[r][c])
                            self.draw_cell_badge(x1, y1, size, f"L {left}", ACCENT, "#111827", badge_font, top=True)
                        if self.settings.get("health_show") and self.health and self.health[r][c] is not None:
                            self.draw_cell_badge(x1, y1, size, f"HP {self.health[r][c]}", "#38bdf8", "#061018", badge_font, top=False)

                if self.game_started and (r, c) in legal_moves:
                    self.canvas.create_oval(
                        x1 + size * 0.38,
                        y1 + size * 0.38,
                        x2 - size * 0.38,
                        y2 - size * 0.38,
                        fill=ACCENT,
                        outline="",
                    )

                if self.game_started and (r, c) in self.next_destroy_targets:
                    self.canvas.create_rectangle(
                        x1 + 3,
                        y1 + 3,
                        x2 - 3,
                        y2 - 3,
                        outline=DANGER,
                        width=3,
                    )
                    self.canvas.create_line(x1 + 7, y1 + 7, x2 - 7, y2 - 7, fill=DANGER, width=2)
                    self.canvas.create_line(x2 - 7, y1 + 7, x1 + 7, y2 - 7, fill=DANGER, width=2)

        if self.game_over:
            self.canvas.create_rectangle(offset_x + 30, offset_y + 90, offset_x + size * cols - 30, offset_y + 210, fill="#111827", outline=ACCENT, width=2)
            self.canvas.create_text(offset_x + size * cols // 2, offset_y + 135, text="ゲーム終了", fill=TEXT, font=(FONT_FAMILY, 28, "bold"))
            self.canvas.create_text(offset_x + size * cols // 2, offset_y + 180, text=self.result_text(), fill=MUTED, font=(FONT_FAMILY, 16))

    def draw_cell_badge(self, x, y, size, text, fill, fg, font, top=True):
        width = max(size * 0.52, 34)
        height = max(size * 0.22, 16)
        cx = x + size / 2
        cy = y + size * (0.26 if top else 0.74)
        x1 = cx - width / 2
        y1 = cy - height / 2
        x2 = cx + width / 2
        y2 = cy + height / 2
        self.canvas.create_rectangle(x1 + 1, y1 + 2, x2 + 1, y2 + 2, fill="#05080b", outline="")
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#ffffff", width=1)
        self.canvas.create_text(cx, cy, text=text, fill=fg, font=font)

    def event_turn_label(self, interval_key):
        interval = self.settings.get(interval_key, 0)
        if interval == 0:
            return "毎ターン"
        left = interval - (self.turn_count % interval)
        if left == 0:
            left = interval
        return f"あと{left}ターン"

    def blackout_turn_label(self, blackout):
        interval = self.settings.get("blackout_interval", 5)
        duration = self.settings.get("blackout_duration", 5)
        if interval == 0:
            return "常に暗転"
        cycle = duration + interval
        pos = self.turn_count % cycle
        if blackout:
            left = max(1, duration - pos)
            return f"解除まで{left}ターン"
        left = max(1, cycle - pos)
        return f"開始まで{left}ターン"

    def is_blackout_active(self):
        if not self.settings.get("blackout"):
            return False
        interval = self.settings.get("blackout_interval", 5)
        duration = self.settings.get("blackout_duration", 5)
        if interval == 0:
            return True
        cycle = duration + interval
        return self.turn_count % cycle < duration

    def count_pieces(self):
        counts = {player: 0 for player in range(1, len(self.players) + 1)}
        for r, row in enumerate(self.board):
            for c, value in enumerate(row):
                if(self.settings.get("total_score") and hasattr(self, "cell_scores")):
                    if value > 0:
                        counts[value] = counts.get(value, 0) + self.cell_scores[r][c]
                else:
                    if value > 0:
                        counts[value] = counts.get(value, 0) + 1
        return counts

    def result_text(self):
        counts = self.count_pieces()
        best = max(counts.values()) if counts else 0
        worst = min(counts.values()) if counts else 0
        if(self.settings.get("reverse_judgment") == False):
            winners = [self.player_name(player) for player, count in counts.items() if count == best]
            if len(winners) == 1:
                return f"{winners[0]}の勝ち  " + "  ".join(f"{self.player_name(p)}:{c}" for p, c in counts.items())
            else:
                return "引き分け  " + "  ".join(f"{self.player_name(p)}:{c}" for p, c in counts.items())
        else:
            winners = [self.player_name(player) for player, count in counts.items() if count == worst]
            if len(winners) == 1:
                return f"{winners[0]}の勝ち  " + "  ".join(f"{self.player_name(p)}:{c}" for p, c in counts.items())
            else:
                return "引き分け  " + "  ".join(f"{self.player_name(p)}:{c}" for p, c in counts.items())

    def end_game(self):
        self.game_over = True
        self.draw_board()
        messagebox.showinfo("ゲーム終了", self.result_text())


if __name__ == "__main__":
    root = tk.Tk()
    app = OthelloApp(root)
    root.mainloop()
