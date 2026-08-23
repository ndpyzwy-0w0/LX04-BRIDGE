#!/usr/bin/env python3
"""Windows host for LX04: USB ADB tunnel + virtual-mic playback + status."""
from __future__ import annotations

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

    def send_control(self, cmd: str) -> None:
        self._send(protocol.encode_json(protocol.CONTROL, {"cmd": cmd}, seq=self._next_seq()))

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
        self._build()
        self.refresh_devices()
        self.refresh_audio_devices()
        self.root.after(400, self._tick)

    def _build(self) -> None:
        self.root.title("LX04 上位机")
        self.root.configure(bg=BG)
        self.root.geometry("760x560")
        self.root.minsize(680, 480)

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
        style.configure("TCombobox", fieldbackground="#1E2A44", background="#1E2A44", foreground=TEXT)

        ttk.Label(self.root, text="LX04 PC Bridge", style="Title.TLabel").pack(anchor="w", padx=20, pady=(16, 4))
        ttk.Label(
            self.root,
            text="USB 数据线连接小爱触屏音箱 LX04，把麦克风送给电脑，屏幕显示链路状态。",
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
        row2.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Label(row2, text="虚拟麦克风输出", style="Card.TLabel").pack(side="left")
        self.audio_var = tk.StringVar()
        self.audio_combo = ttk.Combobox(row2, textvariable=self.audio_var, width=42, state="readonly")
        self.audio_combo.pack(side="left", padx=8)
        ttk.Button(row2, text="静音切换", command=lambda: self.client.send_control("toggle_mute")).pack(side="left")

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
        hint = (
            "会议软件要用音箱麦克风：安装 VB-Audio Virtual Cable，"
            "上方输出选 CABLE Input，微信/腾讯会议的麦克风选 CABLE Output。"
        )
        ttk.Label(self.root, text=hint, style="Dim.TLabel").pack(anchor="w", padx=20, pady=(0, 16))
        self._log("adb: " + (self.adb or "未找到 adb，请安装 Android platform-tools"))
        if not self.sink.available():
            self._log("音频库未安装：在 host 目录执行  pip install -r requirements.txt")

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

    def refresh_audio_devices(self) -> None:
        outputs = self.sink.list_outputs()
        labels = [f"{idx}: {name}" for idx, name in outputs] or ["无可播放设备"]
        self.audio_combo["values"] = labels
        preferred = self.sink.preferred_device()
        if preferred is not None:
            for label in labels:
                if label.startswith(f"{preferred}:"):
                    self.audio_var.set(label)
                    return
        if labels:
            self.audio_var.set(labels[0])

    def connect(self) -> None:
        if not self.adb:
            messagebox.showerror("LX04", "没有 adb。请安装 Android SDK platform-tools 并加入 PATH。")
            return
        serial = self.device_var.get()
        if not self.devices or serial.startswith("没有") or serial.startswith("未找到"):
            messagebox.showerror("LX04", "没有可用的 USB 设备。请用能传数据的 Micro USB 线连接，并打开 USB 调试。")
            return
        try:
            adb_usb.usb_forward(self.adb, serial)
            self.client.connect("127.0.0.1", protocol.PORT)
            device = self._selected_audio_device()
            if self.sink.available():
                self.sink.start(device)
            self.connected = True
            self.headline.configure(text="正在通过 USB 连接…")
            self._log(f"已建立 USB 隧道 localhost:{protocol.PORT} -> 音箱:{protocol.PORT}")
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

    def _selected_audio_device(self) -> int | None:
        raw = self.audio_var.get()
        if ":" in raw:
            try:
                return int(raw.split(":", 1)[0])
            except ValueError:
                return None
        return None

    def _on_bridge_event(self, kind: str, data) -> None:
        self.root.after(0, lambda: self._handle_event(kind, data))

    def _handle_event(self, kind: str, data) -> None:
        if kind == "hello":
            rate = int(data.get("sampleRate") or 48000)
            channels = int(data.get("channels") or 1)
            self.sink.configure(rate, channels)
            try:
                self.sink.start(self._selected_audio_device())
            except Exception as exc:
                self._log("音频输出失败: " + str(exc))
            model = data.get("model") or "LX04"
            self.headline.configure(text=f"已连接 {model}")
            self.detail.configure(text=f"Android {data.get('android', '?')} · {rate} Hz · {channels} ch · USB ADB")
            self._log(f"HELLO {data}")
        elif kind == "audio":
            self.sink.push(data.payload, muted=data.muted)
        elif kind == "status":
            muted = "静音" if data.get("muted") else "拾音中"
            usb = "USB" if data.get("usbConnected") else "USB断开"
            self.detail.configure(
                text=f"{usb} · {muted} · 电平 {float(data.get('level') or 0):.2f} · 丢帧 {data.get('dropped', 0)}"
            )
            if data.get("muted"):
                self.headline.configure(text="音箱已静音")
            elif self.connected:
                self.headline.configure(text="正在把 LX04 麦克风送给电脑")
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
