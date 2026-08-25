#!/usr/bin/env python3
"""Windows host for LX04: USB ADB tunnel + virtual-mic playback + status."""
from __future__ import annotations

import array
import json
import math
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


HOST_DIR = _host_dir()
ROUTES_FILE = HOST_DIR / "audio_routes.json"
if not getattr(sys, "frozen", False) and str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

import adb_usb
import hifi_cable
import protocol
import vb_cable
import win_endpoint
import win_mic
import win_volume
from audio_out import AudioSink, find_hidden_cable_ks_output
from hw_capture import HardwareMic
from speaker_loopback import SpeakerLoopback

BG = "#0B1220"
PANEL = "#141C2E"
TEXT = "#E8EEF8"
DIM = "#8FA0BE"
GREEN = "#3DDC97"
AMBER = "#FFB020"
RED = "#FF5C7A"


class BridgeClient:
    def __init__(self, on_event) -> None:
        self.on_event = on_event
        self.sock: socket.socket | None = None
        self.alive = False
        self.seq = 0
        self.hello: dict = {}
        self.status: dict = {}
        self.frames = 0
        self._thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._seq_lock = threading.Lock()

    def connect(self, host: str, port: int) -> None:
        self.close()
        sock = socket.create_connection((host, port), timeout=5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(8)
        self.sock = sock
        self.alive = True
        self.seq = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self.alive = False
        sock = self.sock
        self.sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def send_control(self, cmd: str, **fields) -> None:
        payload = {"cmd": cmd}
        payload.update(fields)
        self._send(protocol.encode_json(protocol.CONTROL, payload, seq=self._next_seq()))

    def send_play(self, pcm: bytes, muted: bool = False) -> None:
        flags = protocol.FLAG_MUTED if muted else 0
        self._send(protocol.encode(protocol.PLAY, pcm or b"", flags=flags, seq=self._next_seq()))

    def _next_seq(self) -> int:
        with self._seq_lock:
            self.seq = (self.seq + 1) & 0xFFFF
            return self.seq

    def _send(self, data: bytes) -> None:
        with self._send_lock:
            sock = self.sock
            if sock is None:
                return
            try:
                sock.sendall(data)
            except OSError:
                self.alive = False

    def _loop(self) -> None:
        sock = self.sock
        if sock is None:
            return
        last_ping = time.monotonic()
        try:
            while self.alive and sock is self.sock:
                header = _read_exact(sock, protocol.HEADER.size)
                decoded = protocol.try_decode_header(header)
                if decoded is None:
                    raise ConnectionError("bad frame")
                msg_type, flags, seq, timestamp_ms, length = decoded
                payload = _read_exact(sock, length) if length else b""
                frame = protocol.Frame(msg_type, flags, seq, timestamp_ms, payload)
                self._handle(frame)
                now = time.monotonic()
                if now - last_ping > 2:
                    last_ping = now
                    self._send(protocol.encode(protocol.PING, seq=self._next_seq()))
        except Exception as exc:
            if self.alive:
                self.on_event("error", str(exc))
        finally:
            self.alive = False
            self.on_event("disconnected", "")

    def _handle(self, frame: protocol.Frame) -> None:
        if frame.type == protocol.HELLO:
            self.hello = frame.json()
            self._send(protocol.encode_json(
                protocol.HELLO_ACK,
                {"name": socket.gethostname(), "pc": socket.gethostname()},
                seq=self._next_seq(),
            ))
            self.on_event("hello", self.hello)
        elif frame.type == protocol.AUDIO:
            self.frames += 1
            self.on_event("audio", frame)
        elif frame.type == protocol.STATUS:
            self.status = frame.json()
            self.on_event("status", self.status)
        elif frame.type == protocol.PING:
            self._send(protocol.encode(protocol.PONG, seq=self._next_seq()))


def _read_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        piece = sock.recv(size - len(chunks))
        if not piece:
            raise ConnectionError("USB 连接已断开")
        chunks.extend(piece)
    return bytes(chunks)


class HostApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.client = BridgeClient(self._on_bridge_event)
        self.sink = AudioSink()
        self.hw = HardwareMic()
        self.loopback = SpeakerLoopback()
        self.adb = adb_usb.find_adb()
        self.devices: list[str] = []
        self.connected = False
        self._serial = ""
        self._gain_sent_at = 0.0
        self._prev_render: tuple[str, str] | None = None
        self.play_peak = 0.0
        self.mic_enabled = tk.BooleanVar(value=True)
        self.spk_enabled = tk.BooleanVar(value=False)
        self.set_default_spk = tk.BooleanVar(value=True)
        self.volume_sync = tk.BooleanVar(value=False)
        self.inject_var = tk.StringVar()
        self.spk_dev_var = tk.StringVar()
        self._inject_devices: list[tuple[str, str | int, str]] = []
        self._spk_devices: list[tuple[str, str]] = []
        self._routes_ready = False
        self._spk_volume = None
        self._pc_volume = None
        self._pc_muted = False
        self._vol_ignore_pc_until = 0.0
        self._vol_ignore_spk_until = 0.0
        self._build()
        self._load_routes()
        self.refresh_devices()
        self.refresh_audio_devices()
        self._routes_ready = True
        self.root.after(400, self._tick)

    def _build(self) -> None:
        self.root.title("LX04 上位机")
        self.root.configure(bg=BG)
        self.root.geometry("860x800")
        self.root.minsize(760, 640)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 18))
        style.configure("Dim.TLabel", background=BG, foreground=DIM, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 11))
        style.configure("CardDim.TLabel", background=PANEL, foreground=DIM, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        # Windows ttk Combobox keeps a light native field; force dark text so it stays readable.
        combo_fg = "#1A2333"
        combo_bg = "#F3F6FB"
        style.configure(
            "TCombobox",
            fieldbackground=combo_bg,
            background=combo_bg,
            foreground=combo_fg,
            arrowcolor=combo_fg,
            insertcolor=combo_fg,
            padding=4,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", combo_bg), ("disabled", "#D7DCE6")],
            foreground=[("readonly", combo_fg), ("disabled", "#5B6B88")],
            selectbackground=[("readonly", "#C5E9D6")],
            selectforeground=[("readonly", combo_fg)],
        )
        self.root.option_add("*TCombobox*Listbox.background", combo_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", combo_fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#3DDC97")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#0B1220")
        self.root.option_add("*TCombobox*Listbox.font", "Segoe UI 10")

        ttk.Label(self.root, text="LX04 PC Bridge", style="Title.TLabel").pack(anchor="w", padx=20, pady=(16, 4))
        ttk.Label(
            self.root,
            text="USB 连接小爱触屏音箱 LX04。下面两条通路可单独开关、自选设备。",
            style="Dim.TLabel",
        ).pack(anchor="w", padx=20)

        card = ttk.Frame(self.root, style="Card.TFrame")
        card.pack(fill="x", padx=20, pady=16)

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", padx=16, pady=12)
        ttk.Label(row, text="USB 设备", style="Card.TLabel").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(row, textvariable=self.device_var, width=28, state="readonly")
        self.device_combo.pack(side="left", padx=8)
        ttk.Button(row, text="刷新", command=self.refresh_devices).pack(side="left")
        ttk.Button(row, text="连接", command=self.connect).pack(side="left", padx=6)
        ttk.Button(row, text="断开", command=self.disconnect).pack(side="left")

        mic_row = ttk.Frame(card, style="Card.TFrame")
        mic_row.pack(fill="x", padx=16, pady=(0, 8))
        tk.Checkbutton(
            mic_row,
            text="麦克风 → 电脑",
            variable=self.mic_enabled,
            command=self._on_mic_route_change,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#1E2A44",
            activebackground=PANEL,
            activeforeground=TEXT,
            highlightthickness=0,
            font=("Segoe UI", 10),
        ).pack(side="left")
        self.inject_combo = ttk.Combobox(mic_row, textvariable=self.inject_var, width=52, state="readonly")
        self.inject_combo.pack(side="left", padx=8, fill="x", expand=True)
        self.inject_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_mic_route_change())

        spk_row = ttk.Frame(card, style="Card.TFrame")
        spk_row.pack(fill="x", padx=16, pady=(0, 8))
        tk.Checkbutton(
            spk_row,
            text="电脑 → 音箱",
            variable=self.spk_enabled,
            command=self._on_spk_route_change,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#1E2A44",
            activebackground=PANEL,
            activeforeground=TEXT,
            highlightthickness=0,
            font=("Segoe UI", 10),
        ).pack(side="left")
        self.spk_combo = ttk.Combobox(spk_row, textvariable=self.spk_dev_var, width=36, state="readonly")
        self.spk_combo.pack(side="left", padx=8, fill="x", expand=True)
        self.spk_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_spk_route_change())
        tk.Checkbutton(
            spk_row,
            text="设为默认播放",
            variable=self.set_default_spk,
            command=self._on_spk_route_change,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#1E2A44",
            activebackground=PANEL,
            activeforeground=TEXT,
            highlightthickness=0,
            font=("Segoe UI", 10),
        ).pack(side="left")

        vol_row = ttk.Frame(card, style="Card.TFrame")
        vol_row.pack(fill="x", padx=16, pady=(0, 8))
        tk.Checkbutton(
            vol_row,
            text="同步系统音量",
            variable=self.volume_sync,
            command=self._on_volume_sync_change,
            bg=PANEL,
            fg=TEXT,
            selectcolor="#1E2A44",
            activebackground=PANEL,
            activeforeground=TEXT,
            highlightthickness=0,
            font=("Segoe UI", 10),
        ).pack(side="left")
        ttk.Label(
            vol_row,
            text="开了后电脑和音箱音量一起变；关掉则各自调节、互不影响。",
            style="CardDim.TLabel",
        ).pack(side="left", padx=8)

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Button(row2, text="试音", command=self._on_test_tone).pack(side="left")
        ttk.Button(row2, text="音箱试音", command=self._on_speaker_test_tone).pack(side="left", padx=6)
        ttk.Button(row2, text="静音切换", command=lambda: self.client.send_control("toggle_mute")).pack(side="left", padx=6)
        ttk.Button(row2, text="安装 VB-CABLE", command=self._install_vb).pack(side="right")
        ttk.Button(row2, text="安装 Hi-Fi Cable", command=self._install_hifi).pack(side="right", padx=6)

        row3 = ttk.Frame(card, style="Card.TFrame")
        row3.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Label(row3, text="微信请选麦克风", style="Card.TLabel").pack(side="left")
        self.mic_var = tk.StringVar(value="尚未识别")
        ttk.Label(row3, textvariable=self.mic_var, style="Card.TLabel").pack(side="left", padx=8)

        gain_row = ttk.Frame(card, style="Card.TFrame")
        gain_row.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Label(gain_row, text="麦克风增益", style="Card.TLabel").pack(side="left")
        self.gain_var = tk.DoubleVar(value=100)
        style.configure(
            "Gain.Horizontal.TScale",
            background=PANEL,
            troughcolor="#1E2A44",
            sliderthickness=16,
        )
        self.gain_scale = ttk.Scale(
            gain_row,
            from_=0,
            to=300,
            orient="horizontal",
            variable=self.gain_var,
            command=self._on_gain,
            style="Gain.Horizontal.TScale",
            length=280,
        )
        self.gain_scale.pack(side="left", padx=10, fill="x", expand=True)
        self.gain_label_var = tk.StringVar(value="100%  ·  0.0 dB")
        ttk.Label(gain_row, textvariable=self.gain_label_var, style="Card.TLabel").pack(side="left")

        self.headline = ttk.Label(card, text="未连接", style="Card.TLabel")
        self.headline.pack(anchor="w", padx=16)
        self.detail = ttk.Label(card, text="插入数据线后点刷新，再点连接。", style="CardDim.TLabel")
        self.detail.pack(anchor="w", padx=16, pady=(2, 8))

        ttk.Label(card, text="麦克风", style="CardDim.TLabel").pack(anchor="w", padx=16)
        self.meter = tk.Canvas(card, height=22, bg="#1E2A44", highlightthickness=0)
        self.meter.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Label(card, text="扬声器", style="CardDim.TLabel").pack(anchor="w", padx=16)
        self.spk_meter = tk.Canvas(card, height=22, bg="#1E2A44", highlightthickness=0)
        self.spk_meter.pack(fill="x", padx=16, pady=(0, 16))

        self.log = tk.Text(
            self.root,
            height=14,
            bg="#10182A",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 10),
        )
        self.log.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        hint = "CABLE Input 已从系统播放列表隐藏，上位机仍会把麦克风灌进去。微信选 CABLE Output。扬声器选 Hi-Fi Cable Input。"
        ttk.Label(self.root, text=hint, style="Dim.TLabel").pack(anchor="w", padx=20, pady=(0, 16))
        self._log("adb: " + (self.adb or "未找到内置 adb"))
        if not self.sink.available():
            self._log("音频库未安装：在 host 目录执行  pip install -r requirements.txt")

    def _selected_inject(self) -> tuple[str, str | int, str] | None:
        label = self.inject_var.get()
        for item in self._inject_devices:
            if item[2] == label:
                return item
        if self._inject_devices:
            return self._inject_devices[0]
        return None

    def _selected_speaker(self) -> tuple[str, str] | None:
        label = self.spk_dev_var.get()
        for device_id, name in self._spk_devices:
            if name == label:
                return device_id, name
        if self._spk_devices:
            return self._spk_devices[0]
        return None

    def _load_routes(self) -> None:
        try:
            data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        self.mic_enabled.set(bool(data.get("mic_enabled", True)))
        self.spk_enabled.set(bool(data.get("spk_enabled", False)))
        self.set_default_spk.set(bool(data.get("set_default_spk", True)))
        self.volume_sync.set(bool(data.get("volume_sync", False)))
        self._saved_inject = str(data.get("inject") or "")
        self._saved_spk = str(data.get("speaker") or "")

    def _save_routes(self) -> None:
        payload = {
            "mic_enabled": bool(self.mic_enabled.get()),
            "spk_enabled": bool(self.spk_enabled.get()),
            "set_default_spk": bool(self.set_default_spk.get()),
            "volume_sync": bool(self.volume_sync.get()),
            "inject": self.inject_var.get(),
            "speaker": self.spk_dev_var.get(),
        }
        try:
            ROUTES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def refresh_audio_devices(self, log: bool = True) -> None:
        hidden = win_endpoint.tidy_cable_endpoints()
        if log and hidden:
            self._log("已从系统播放列表隐藏：" + "、".join(hidden))
        previous_inject = self.inject_var.get() or getattr(self, "_saved_inject", "")
        previous_spk = self.spk_dev_var.get() or getattr(self, "_saved_spk", "")
        inject_items: list[tuple[str, str | int, str]] = []
        ks = find_hidden_cable_ks_output()
        cable = win_endpoint.find_cable_render()
        if ks is not None:
            label = (cable.FriendlyName if cable is not None else "CABLE Input") + "  [隐藏]"
            inject_items.append(("hidden", ks[0], label))
        for index, name in self.sink.list_playback_devices():
            if win_endpoint.is_cable_render(name):
                continue
            inject_items.append(("sd", index, name))
        self._inject_devices = inject_items
        inject_labels = [label for _kind, _handle, label in inject_items]
        self.inject_combo["values"] = inject_labels
        preferred = inject_labels[0] if inject_labels else None
        chosen = _pick_label(inject_labels, previous_inject, preferred)
        if chosen:
            self.inject_var.set(chosen)
        self._spk_devices = win_endpoint.list_render_endpoints()
        spk_labels = [name for _device_id, name in self._spk_devices]
        self.spk_combo["values"] = spk_labels
        hifi = next((name for _device_id, name in self._spk_devices if hifi_cable.is_hifi_render(name)), None)
        chosen_spk = _pick_label(spk_labels, previous_spk, hifi)
        if chosen_spk:
            self.spk_dev_var.set(chosen_spk)
        if log:
            if vb_cable.present():
                self._log("麦克风建议：隐藏的 CABLE Input，微信选 CABLE Output。")
            if hifi_cable.present():
                self._log("扬声器建议：Hi-Fi Cable Input。")

    def _on_mic_route_change(self) -> None:
        if not self._routes_ready:
            return
        self._save_routes()
        if not self.connected:
            return
        try:
            self._apply_mic_route()
        except Exception as exc:
            self._log("切换麦克风通路失败: " + str(exc))

    def _on_spk_route_change(self) -> None:
        if not self._routes_ready:
            return
        self._save_routes()
        if not self.connected:
            return
        try:
            self._apply_speaker_route()
        except Exception as exc:
            self._log("切换扬声器通路失败: " + str(exc))

    def _on_volume_sync_change(self) -> None:
        if not self._routes_ready:
            return
        self._save_routes()
        if not self.volume_sync.get():
            self._pc_muted = False
            self._log("音量同步已关闭，电脑和音箱可各自调节。")
            return
        if not self.connected:
            self._log("音量同步已打开，连接音箱后会跟着电脑系统音量走。")
            return
        self._push_pc_volume(force=True)
        self._log("音量同步已打开：调节电脑或音箱音量会一起变。")

    def _push_pc_volume(self, force: bool = False) -> None:
        if not self.connected or not self.volume_sync.get():
            return
        now = time.monotonic()
        if not force and now < self._vol_ignore_pc_until:
            return
        pc, muted = win_volume.get_state()
        if pc is None:
            return
        self._pc_muted = muted
        if (
            not force
            and self._pc_volume is not None
            and abs(pc - self._pc_volume) < 0.03
        ):
            return
        self._pc_volume = pc
        self._spk_volume = pc
        self._vol_ignore_spk_until = now + 0.45
        self.client.send_control("volume", level=round(pc, 3))

    def _apply_speaker_volume(self, level: float) -> None:
        if not self.connected or not self.volume_sync.get():
            self._spk_volume = level
            return
        now = time.monotonic()
        if now < self._vol_ignore_spk_until:
            self._spk_volume = level
            return
        if self._spk_volume is not None and abs(level - self._spk_volume) < 0.03:
            return
        self._spk_volume = level
        self._pc_volume = level
        self._vol_ignore_pc_until = now + 0.45
        win_volume.set_scalar(level)

    def _apply_mic_route(self) -> None:
        if not self.mic_enabled.get():
            self.hw.stop(self.adb, self._serial)
            self.sink.stop()
            self._log("已关闭麦克风通路")
            return
        self.sink.configure(48000, 1)
        self._start_inject()
        if self.adb and self._serial and not self.hw.running():
            try:
                self.hw.start(self.adb, self._serial, self.sink)
                self._log("已从音箱数字麦直采：48kHz 单声道（tinycap pcmC0D1c）")
                self.client.send_control("stop_mic")
            except Exception as exc:
                self._log("硬件直采失败，回退 APK 麦克风: " + str(exc))
                self.client.send_control("start_mic")

    def _apply_speaker_route(self) -> None:
        if not self.spk_enabled.get():
            self._restore_render()
            self._log("已关闭扬声器通路")
            return
        self._start_speaker()

    def _install_vb(self) -> None:
        if not messagebox.askokcancel("LX04", vb_cable.DONATE_TEXT):
            return
        self._log(vb_cable.run_official_setup())
        self.refresh_audio_devices()

    def _install_hifi(self) -> None:
        if not messagebox.askokcancel("LX04", hifi_cable.DONATE_TEXT):
            return
        self._log(hifi_cable.run_official_setup())
        self.refresh_audio_devices()

    def _start_inject(self) -> None:
        selected = self._selected_inject()
        if selected is None:
            raise RuntimeError("没有可用的播放设备。请先点刷新，或安装 VB-CABLE。")
        kind, handle, label = selected
        if win_endpoint.is_cable_render(label) or kind == "hidden":
            prepared = win_endpoint.prepare_vb_cable()
            for line in prepared.get("logs") or []:
                self._log(line)
        if kind == "hidden":
            self.sink.start_hidden_cable(label.replace("  [隐藏]", "").strip())
        else:
            self.sink.start(int(handle))
        rec = win_mic.matching_recording_device(self.sink.device_name)
        rec_name = rec[1] if rec else "CABLE Output"
        self.mic_var.set("请选择： " + rec_name)
        self._log("麦克风已送入: " + self.sink.device_name + "  /  " + label)
        self._log(
            f"注入格式: {self.sink.out_rate}Hz / {self.sink._dtype} / {self.sink.out_channels}ch"
        )
        self._log("语音软件请选择: " + rec_name)
        self._save_routes()

    def _start_speaker(self) -> None:
        selected = self._selected_speaker()
        if selected is None:
            self._log("没有可环回的播放设备，扬声器通路未打开。可用「音箱试音」检查喇叭。")
            return
        device_id, name = selected
        inject = self._selected_inject()
        if self.mic_enabled.get() and inject is not None and win_endpoint.is_cable_render(name) and win_endpoint.is_cable_render(inject[2]):
            self._log("警告：扬声器和麦克风都选了 VB-CABLE，微信里会串进系统声音。")
        self.loopback.stop()
        self.play_peak = 0.0
        prepared = win_endpoint.prepare_render_device(device_id)
        for line in prepared.get("logs") or []:
            self._log(line)
        device_id = prepared.get("device_id") or device_id
        if self.set_default_spk.get():
            current = win_endpoint.get_default_render()
            if current and current[0] != device_id and self._prev_render is None:
                self._prev_render = current
            if win_endpoint.set_default_render(device_id):
                self._log("已把系统播放切到: " + name)
            else:
                self._log("未能把系统播放切到选中的设备。")
        self.loopback.start(device_id, name, self._on_loopback_pcm)
        self._log("扬声器环回: " + name)
        self._save_routes()

    def _on_loopback_pcm(self, pcm: bytes, muted: bool) -> None:
        silent = muted or (self.volume_sync.get() and self._pc_muted)
        if silent:
            pcm = b"\x00" * len(pcm)
            self.play_peak = 0.0
        else:
            self.play_peak = self.loopback.peak
        self.client.send_play(pcm, muted=silent)

    def _restore_render(self) -> None:
        self.loopback.stop()
        prev = self._prev_render
        self._prev_render = None
        self.play_peak = 0.0
        if prev:
            if win_endpoint.set_default_render(prev[0]):
                self._log("已恢复系统播放设备: " + prev[1])

    def _pcm_peak(self, pcm: bytes) -> float:
        peak = 0
        for i in range(0, len(pcm) - 1, 2):
            sample = pcm[i] | (pcm[i + 1] << 8)
            if sample >= 32768:
                sample -= 65536
            value = -sample if sample < 0 else sample
            if value > peak:
                peak = value
        return peak / 32768.0

    def _on_speaker_test_tone(self) -> None:
        if not self.connected:
            messagebox.showerror("LX04", "请先连接音箱。")
            return
        rate = 48000
        frames = int(rate * 0.7)
        samples = array.array("h")
        for index in range(frames):
            value = int(9000 * math.sin(2.0 * math.pi * 440.0 * index / rate))
            samples.append(value)
            samples.append(value)
        pcm = samples.tobytes()
        step = (rate // 50) * 4

        def _send() -> None:
            for offset in range(0, len(pcm), step):
                if not self.connected:
                    break
                chunk = pcm[offset : offset + step]
                self.play_peak = max(self.play_peak, self._pcm_peak(chunk))
                self.client.send_play(chunk)
                time.sleep(0.02)

        threading.Thread(target=_send, daemon=True).start()
        self._log("已向音箱送出试音。应能从音箱喇叭听到「嘀」。")

    def _on_test_tone(self) -> None:
        if not self.mic_enabled.get():
            messagebox.showerror("LX04", "请先勾选「麦克风 → 电脑」，并选好 CABLE Input。")
            return
        try:
            if not self.sink.running():
                self.sink.configure(48000, 1)
                self._start_inject()
            self.sink.play_test_tone()
            self._log("已送出试音。请看语音软件里「CABLE Output」的音量条是否跳动。")
        except Exception as exc:
            messagebox.showerror("LX04", str(exc))
            self._log("试音失败: " + str(exc))

    def _on_gain(self, _value=None) -> None:
        percent = float(self.gain_var.get())
        gain = percent / 100.0
        self.sink.gain = gain
        if gain <= 0:
            self.gain_label_var.set("0%  ·  静音")
        else:
            db = 20.0 * math.log10(gain)
            self.gain_label_var.set(f"{percent:.0f}%  ·  {db:+.1f} dB")
        now = time.monotonic()
        if self.connected and now - self._gain_sent_at > 0.15:
            self._gain_sent_at = now
            self.client.send_control("gain", gain=round(gain, 3))

    def refresh_devices(self) -> None:
        if not self.adb:
            self.device_combo["values"] = ["未找到 adb"]
            self.device_var.set("未找到 adb")
            return
        try:
            self.devices = adb_usb.list_devices(self.adb)
        except Exception as exc:
            self._log("读取 adb 设备失败: " + str(exc))
            self.devices = []
        labels = self.devices or ["没有 USB 设备（检查数据线 / USB 调试）"]
        self.device_combo["values"] = labels
        self.device_var.set(labels[0])
        self._log("USB 设备: " + (", ".join(self.devices) if self.devices else "无"))
        self.refresh_audio_devices(log=False)

    def connect(self) -> None:
        if not self.adb:
            messagebox.showerror("LX04", "没有找到内置 adb。请重新打包上位机。")
            return
        serial = self.device_var.get()
        if not self.devices or serial.startswith("没有") or serial.startswith("未找到"):
            messagebox.showerror("LX04", "没有可用的 USB 设备。请拔掉数据线再插上，并打开 USB 调试。")
            return
        try:
            gadget = adb_usb.enable_usb_microphone(self.adb, serial)
            if gadget:
                self._log("USB 功能: " + " ".join(gadget.split()))
            mic = adb_usb.take_speaker_mic(self.adb, serial)
            self._log(mic)
            adb_usb.usb_forward(self.adb, serial)
            self.client.connect("127.0.0.1", protocol.PORT)
            self.connected = True
            self._serial = serial
            if self.mic_enabled.get():
                self._apply_mic_route()
            else:
                self._log("麦克风通路已关闭。")
            self._on_gain()
            self.client.send_control("gain", gain=round(self.sink.gain, 3))
            if self.volume_sync.get():
                self._push_pc_volume(force=True)
            if self.spk_enabled.get():
                self._apply_speaker_route()
            else:
                self._log("扬声器通路已关闭。可用「音箱试音」检查喇叭。")
            self.headline.configure(text="USB 已连接")
        except Exception as exc:
            self.connected = False
            self._restore_render()
            try:
                self.client.close()
            except Exception:
                pass
            try:
                self.hw.stop(self.adb, serial)
            except Exception:
                pass
            try:
                adb_usb.release_speaker_mic(self.adb, serial)
            except Exception:
                pass
            messagebox.showerror("LX04", str(exc))
            self._log("连接失败: " + str(exc))

    def disconnect(self) -> None:
        self.client.close()
        self.hw.stop(self.adb, self._serial)
        self.sink.stop()
        self._restore_render()
        self.connected = False
        if self.adb and self._serial:
            try:
                self._log(adb_usb.release_speaker_mic(self.adb, self._serial))
            except Exception as exc:
                self._log("恢复小爱麦失败: " + str(exc))
        self.headline.configure(text="已断开")
        self.detail.configure(text="可以重新点连接。")
        self._draw_meter(self.meter, 0)
        self._draw_meter(self.spk_meter, 0)

    def _on_bridge_event(self, kind: str, data) -> None:
        self.root.after(0, lambda: self._handle_event(kind, data))

    def _handle_event(self, kind: str, data) -> None:
        if kind == "hello":
            rate = int(data.get("sampleRate") or 48000)
            if not self.hw.running() and self.mic_enabled.get():
                self.sink.configure(rate, 1)
                if not self.sink.running():
                    try:
                        self._start_inject()
                    except Exception as exc:
                        self._log("音频输出失败: " + str(exc))
            model = data.get("model") or "LX04"
            source = data.get("audioSource") or ""
            apk = str(data.get("apkVersion") or "").strip()
            apk_label = ("v" + apk.lstrip("vV")) if apk else ""
            self.headline.configure(text=f"已连接 {model}" + (f"  {apk_label}" if apk_label else ""))
            self.detail.configure(text=f"Android {data.get('android', '?')} · USB 麦克风 + 状态屏")
            self._log(f"HELLO {data}")
            if apk_label:
                self._log("音箱 APK: " + apk_label)
            if self.hw.running():
                self._log("音频来自音箱硬件麦 48 kHz，不走 APK AudioRecord")
            else:
                if source:
                    self._log("音箱采集源: " + str(source))
                self._log(f"按单声道 {rate} Hz 接收音箱 PCM")
        elif kind == "audio":
            if self.sink.running() and not self.hw.running():
                self.sink.push(data.payload, muted=data.muted)
        elif kind == "status":
            if "volume" in data:
                try:
                    self._apply_speaker_volume(float(data.get("volume") or 0))
                except (TypeError, ValueError):
                    pass
            self.loopback.muted = bool(data.get("muted"))
            if self.loopback.error:
                self._log("扬声器环回: " + self.loopback.error)
                self.loopback.error = ""
            if self.hw.running():
                self.hw.muted = bool(data.get("muted"))
                muted = "静音" if data.get("muted") else "拾音中"
                usb = "USB" if data.get("usbConnected") else "USB断开"
                self.detail.configure(
                    text=f"{usb} · {muted} · 硬件麦 48kHz · 电平 {self.sink.peak:.2f} · 扬声器 {float(data.get('playLevel') or self.play_peak):.2f}"
                )
                if data.get("muted"):
                    self.headline.configure(text="音箱已静音")
                elif self.connected:
                    self.headline.configure(text="正在把 LX04 硬件麦送给语音软件")
                if self.sink.callback_error:
                    self._log("音频回调: " + self.sink.callback_error)
                    self.sink.callback_error = ""
                return
            rate = int(data.get("sampleRate") or 0)
            if (
                rate
                and self.sink.running()
                and abs(rate - self.sink.sample_rate) >= 50
            ):
                self.sink.configure(rate, 1)
                try:
                    self._start_inject()
                    self._log(f"音箱采样率变为 {rate} Hz，已重开注入")
                except Exception as exc:
                    self._log("按新采样率打开注入失败: " + str(exc))
            self.sink.peak = min(1.0, float(data.get("level") or 0) * self.sink.gain)
            muted = "静音" if data.get("muted") else "拾音中"
            usb = "USB" if data.get("usbConnected") else "USB断开"
            self.detail.configure(
                text=f"{usb} · {muted} · 电平 {float(data.get('level') or 0):.2f} · 扬声器 {float(data.get('playLevel') or self.play_peak):.2f} · 丢帧 {data.get('dropped', 0)}"
            )
            if data.get("muted"):
                self.headline.configure(text="音箱已静音")
            elif self.connected:
                self.headline.configure(text="正在把 LX04 麦克风送给语音软件")
            if self.sink.callback_error:
                self._log("音频回调: " + self.sink.callback_error)
                self.sink.callback_error = ""
        elif kind == "error":
            self._log("链路错误: " + str(data))
        elif kind == "disconnected":
            self.connected = False
            self.hw.stop(self.adb, self._serial)
            self.sink.stop()
            self._restore_render()
            if self.adb and self._serial:
                try:
                    adb_usb.release_speaker_mic(self.adb, self._serial)
                except Exception:
                    pass
            self.headline.configure(text="USB 已断开")
            self.detail.configure(text="检查数据线后重新连接。")
            self._draw_meter(self.meter, 0)
            self._draw_meter(self.spk_meter, 0)

    def _tick(self) -> None:
        spk = self.loopback.peak if self.loopback.running() else self.play_peak
        self._draw_meter(self.meter, self.sink.peak if self.connected else 0)
        self._draw_meter(self.spk_meter, spk if self.connected else 0)
        if not self.loopback.running():
            self.play_peak *= 0.82
        self._push_pc_volume()
        self.root.after(80, self._tick)

    def _draw_meter(self, canvas: tk.Canvas, level: float) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 10)
        fill = max(4, int(width * min(1.0, level * 2.2)))
        color = GREEN if level < 0.35 else AMBER if level < 0.7 else RED
        canvas.create_rectangle(0, 0, fill, 22, fill=color, outline="")

    def _log(self, line: str) -> None:
        self.log.insert("end", line + "\n")
        self.log.see("end")


def _pick_label(labels: list[str], saved: str, fallback: str | None) -> str:
    if saved and saved in labels:
        return saved
    if saved:
        key = saved.split("  [")[0].strip().lower()
        for label in labels:
            if label.split("  [")[0].strip().lower() == key:
                return label
            if key and key in label.lower():
                return label
    if fallback and fallback in labels:
        return fallback
    return labels[0] if labels else ""


def main() -> None:
    root = tk.Tk()
    app = HostApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.disconnect(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
