#!/usr/bin/env python3
"""Windows host for LX04: USB ADB tunnel + virtual-mic playback + status."""
from __future__ import annotations

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
if not getattr(sys, "frozen", False) and str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

import adb_usb
import protocol
import vb_cable
import win_endpoint
import win_mic
from audio_out import AudioSink

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

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFFFF
        return self.seq

    def _send(self, data: bytes) -> None:
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
        self.adb = adb_usb.find_adb()
        self.devices: list[str] = []
        self.connected = False
        self._gain_sent_at = 0.0
        self._build()
        self.refresh_devices()
        self.refresh_mic_status()
        self.root.after(400, self._tick)

    def _build(self) -> None:
        self.root.title("LX04 上位机")
        self.root.configure(bg=BG)
        self.root.geometry("780x620")
        self.root.minsize(700, 520)

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
            text="USB 数据线连接小爱触屏音箱 LX04。语音软件请选麦克风「CABLE Output」，不要选 CABLE Input，也不要选 16 Ch。",
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

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", padx=16, pady=(0, 8))
        ttk.Button(row2, text="试音", command=self._on_test_tone).pack(side="left")
        ttk.Button(row2, text="静音切换", command=lambda: self.client.send_control("toggle_mute")).pack(side="left", padx=6)

        row3 = ttk.Frame(card, style="Card.TFrame")
        row3.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Label(row3, text="电脑麦克风", style="Card.TLabel").pack(side="left")
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

        self.meter = tk.Canvas(card, height=22, bg="#1E2A44", highlightthickness=0)
        self.meter.pack(fill="x", padx=16, pady=(0, 16))

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
        hint = "连接后，微信 / QQ / 语音输入请选麦克风「CABLE Output」。"
        ttk.Label(self.root, text=hint, style="Dim.TLabel").pack(anchor="w", padx=20, pady=(0, 16))
        self._log("adb: " + (self.adb or "未找到内置 adb"))
        if vb_cable.present():
            self._log("已检测到 VB-CABLE，语音软件请选「CABLE Output」。")
        else:
            self._log("未检测到 VB-CABLE。连接时会打开官方安装程序（www.vb-cable.com，捐赠软件）。")
        if not self.sink.available():
            self._log("音频库未安装：在 host 目录执行  pip install -r requirements.txt")

    def _start_inject(self) -> None:
        if not vb_cable.present():
            if not messagebox.askokcancel("LX04", vb_cable.DONATE_TEXT):
                raise RuntimeError("未安装 VB-CABLE，无法把音箱声音送给微信。")
            result = vb_cable.run_official_setup()
            self._log(result)
            if not vb_cable.present():
                raise RuntimeError(result)
        prepared = win_endpoint.prepare_vb_cable()
        for line in prepared.get("logs") or []:
            self._log(line)
        device = self.sink.preferred_device()
        if device is None:
            raise RuntimeError("找不到 CABLE Input。若刚装完 VB-CABLE，请先重启电脑再打开本程序。")
        self.sink.start(device)
        rec = win_mic.matching_recording_device(self.sink.device_name)
        rec_name = rec[1] if rec else (prepared.get("capture") or "CABLE Output")
        self.mic_var.set("请选择： " + rec_name)
        self._log("已把音箱声音送入: " + self.sink.device_name)
        self._log(
            f"注入格式: {self.sink.out_rate}Hz / {self.sink._dtype} / {self.sink.out_channels}ch"
        )
        self._log("语音软件请选择麦克风: " + rec_name + "（不要选 CABLE Input）")
        self._log("若微信里仍无声：完全退出微信（托盘也退出），再打开并只选 CABLE Output。")
        if prepared.get("capture"):
            self._log("已设为系统默认麦克风: " + str(prepared["capture"]))

    def _on_test_tone(self) -> None:
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

    def refresh_mic_status(self) -> None:
        found = win_mic.find_usb_microphone()
        if found:
            self.mic_var.set("已识别： " + found[1])
            self._log("电脑麦克风: " + found[1])
            return
        inputs = win_mic.list_inputs()
        if inputs:
            names = "、".join(name for _, name in inputs[:6])
            self.mic_var.set("未出现 LX04，当前输入: " + names)
            self._log("电脑录音设备: " + names)
        else:
            self.mic_var.set("未识别到录音设备")
            self._log("电脑录音设备: 无")

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
            adb_usb.usb_forward(self.adb, serial)
            self.client.connect("127.0.0.1", protocol.PORT)
            self.connected = True
            try:
                self.sink.configure(48000, 1)
                self._start_inject()
            except Exception as exc:
                self._log("虚拟麦克风打开失败: " + str(exc))
                messagebox.showerror("LX04", "音箱已连接，但没能把声音送进微信麦克风：\n" + str(exc))
            self._on_gain()
            self.client.send_control("gain", gain=round(self.sink.gain, 3))
            self.headline.configure(text="USB 已连接")
        except Exception as exc:
            self.connected = False
            messagebox.showerror("LX04", str(exc))
            self._log("连接失败: " + str(exc))

    def disconnect(self) -> None:
        self.client.close()
        self.sink.stop()
        self.connected = False
        self.headline.configure(text="已断开")
        self.detail.configure(text="可以重新点连接。")
        self._draw_meter(0)

    def _on_bridge_event(self, kind: str, data) -> None:
        self.root.after(0, lambda: self._handle_event(kind, data))

    def _handle_event(self, kind: str, data) -> None:
        if kind == "hello":
            rate = int(data.get("sampleRate") or 48000)
            # APK always captures mono s16; treating it as stereo makes speech-gated static.
            self.sink.configure(rate, 1)
            try:
                self._start_inject()
            except Exception as exc:
                self._log("音频输出失败: " + str(exc))
            model = data.get("model") or "LX04"
            source = data.get("audioSource") or ""
            self.headline.configure(text=f"已连接 {model}")
            self.detail.configure(text=f"Android {data.get('android', '?')} · USB 麦克风 + 状态屏")
            self._log(f"HELLO {data}")
            if source:
                self._log("音箱采集源: " + str(source))
            self._log(f"按单声道 {rate} Hz 接收音箱 PCM")
        elif kind == "audio":
            if self.sink.running():
                self.sink.push(data.payload, muted=data.muted)
        elif kind == "status":
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
                text=f"{usb} · {muted} · 电平 {float(data.get('level') or 0):.2f} · 丢帧 {data.get('dropped', 0)}"
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
            self.sink.stop()
            self.headline.configure(text="USB 已断开")
            self.detail.configure(text="检查数据线后重新连接。")
            self._draw_meter(0)

    def _tick(self) -> None:
        self._draw_meter(self.sink.peak if self.connected else 0)
        self.root.after(80, self._tick)

    def _draw_meter(self, level: float) -> None:
        self.meter.delete("all")
        width = max(self.meter.winfo_width(), 10)
        fill = max(4, int(width * min(1.0, level * 2.2)))
        color = GREEN if level < 0.35 else AMBER if level < 0.7 else RED
        self.meter.create_rectangle(0, 0, fill, 22, fill=color, outline="")

    def _log(self, line: str) -> None:
        self.log.insert("end", line + "\n")
        self.log.see("end")


def main() -> None:
    root = tk.Tk()
    app = HostApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.disconnect(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
