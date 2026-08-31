#!/usr/bin/env python3
"""Windows host for LX04: USB ADB tunnel + virtual-mic playback + status."""
from __future__ import annotations

import array
import ctypes
import json
import math
import socket
import sys
import threading
import time
import winreg
from ctypes import wintypes
from pathlib import Path

from qt_ui import HostBridge, QtLoop, Var, apply_fluent_style, qml_dir


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


HOST_DIR = _host_dir()
ROUTES_FILE = HOST_DIR / "audio_routes.json"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "LX04 PC Bridge"
if not getattr(sys, "frozen", False) and str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

import adb_usb
import afterburner
import hifi_cable
import hud_preview
import pc_stats
import protocol
import screen_mirror
import toast_mirror
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
COMBO_FG = "#1A2333"
COMBO_BG = "#F3F6FB"


_user32 = ctypes.windll.user32
_shell32 = ctypes.windll.shell32
_kernel32 = ctypes.windll.kernel32
_LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_WM_NULL = 0x0000
_WM_TRAY = 0x8001
_WM_LBUTTONDOWN = 0x0201
_WM_LBUTTONUP = 0x0202
_WM_LBUTTONDBLCLK = 0x0203
_WM_RBUTTONDOWN = 0x0204
_WM_RBUTTONUP = 0x0205
_WM_CONTEXTMENU = 0x007B
_NIN_SELECT = 0x0400
_NIN_KEYSELECT = 0x0401
_NIM_ADD, _NIM_MODIFY, _NIM_DELETE = 0, 1, 2
_NIF_MESSAGE, _NIF_ICON, _NIF_TIP = 1, 2, 4
_IDI_APPLICATION = 32512
_TPM_RIGHTBUTTON = 0x0002
_TPM_BOTTOMALIGN = 0x0020
_TPM_RETURNCMD = 0x0100
_MF_STRING = 0x0000
_WS_POPUP = 0x80000000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_TOPMOST = 0x00000008
_SW_SHOW = 5
_SW_RESTORE = 9
_GA_ROOT = 2
_ERROR_CLASS_ALREADY_EXISTS = 1410
_TRAY_OPEN, _TRAY_QUIT = 1, 2
_TRAY_CLASS = "LX04BridgeTray"
_HOST_TITLE = "LX04 上位机"
_MUTEX_NAME = "Local\\LX04PCBridgeHost"
_EVENT_NAME = "Local\\LX04PCBridgeActivate"
_ERROR_ALREADY_EXISTS = 183
_WAIT_OBJECT_0 = 0


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


_kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_user32.DefWindowProcW.restype = _LRESULT
_user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.RegisterClassW.restype = wintypes.ATOM
_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
]
_user32.DestroyWindow.restype = wintypes.BOOL
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.CreatePopupMenu.restype = wintypes.HMENU
_user32.CreatePopupMenu.argtypes = []
_user32.AppendMenuW.restype = wintypes.BOOL
_user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
_user32.TrackPopupMenu.restype = wintypes.UINT
_user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, ctypes.c_void_p,
]
_user32.DestroyMenu.restype = wintypes.BOOL
_user32.DestroyMenu.argtypes = [wintypes.HMENU]
_user32.GetCursorPos.restype = wintypes.BOOL
_user32.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.ShowWindow.restype = wintypes.BOOL
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetAncestor.restype = wintypes.HWND
_user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_user32.PostMessageW.restype = wintypes.BOOL
_user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_shell32.ExtractIconExW.restype = wintypes.UINT
_shell32.ExtractIconExW.argtypes = [
    wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
    ctypes.POINTER(wintypes.HICON), wintypes.UINT,
]
_shell32.Shell_NotifyIconW.restype = wintypes.BOOL
_shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(_NOTIFYICONDATAW)]
_user32.LoadIconW.restype = wintypes.HICON
_user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
_user32.DestroyIcon.restype = wintypes.BOOL
_user32.DestroyIcon.argtypes = [wintypes.HICON]
_user32.RegisterWindowMessageW.restype = wintypes.UINT
_user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_k32err = ctypes.WinDLL("kernel32", use_last_error=True)
_k32err.CreateMutexW.restype = wintypes.HANDLE
_k32err.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_k32err.CreateEventW.restype = wintypes.HANDLE
_k32err.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_k32err.SetEvent.restype = wintypes.BOOL
_k32err.SetEvent.argtypes = [wintypes.HANDLE]
_k32err.ResetEvent.restype = wintypes.BOOL
_k32err.ResetEvent.argtypes = [wintypes.HANDLE]
_k32err.WaitForSingleObject.restype = wintypes.DWORD
_k32err.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_k32err.CloseHandle.restype = wintypes.BOOL
_k32err.CloseHandle.argtypes = [wintypes.HANDLE]

_TRAY_APP = None
_TASKBAR_CREATED = _user32.RegisterWindowMessageW("TaskbarCreated")
_SINGLE_MUTEX = 0
_ACTIVATE_EVENT = 0


def _claim_single_instance(mutex_name: str = _MUTEX_NAME, event_name: str = _EVENT_NAME) -> bool:
    global _SINGLE_MUTEX, _ACTIVATE_EVENT
    mutex = _k32err.CreateMutexW(None, False, mutex_name)
    already = ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
    event = _k32err.CreateEventW(None, True, False, event_name)
    if already:
        if event:
            _k32err.SetEvent(event)
            _k32err.CloseHandle(event)
        if mutex:
            _k32err.CloseHandle(mutex)
        return False
    _SINGLE_MUTEX = int(mutex or 0)
    _ACTIVATE_EVENT = int(event or 0)
    return True


def _release_single_instance() -> None:
    global _SINGLE_MUTEX, _ACTIVATE_EVENT
    for handle in (_SINGLE_MUTEX, _ACTIVATE_EVENT):
        if handle:
            _k32err.CloseHandle(handle)
    _SINGLE_MUTEX = 0
    _ACTIVATE_EVENT = 0


def _activate_running_host() -> None:
    hwnd = _user32.FindWindowW(None, _HOST_TITLE)
    if hwnd:
        _user32.ShowWindow(hwnd, _SW_RESTORE)
        _user32.SetForegroundWindow(hwnd)


def _poll_activate_event() -> bool:
    ev = _ACTIVATE_EVENT
    if ev and _k32err.WaitForSingleObject(ev, 0) == _WAIT_OBJECT_0:
        _k32err.ResetEvent(ev)
        return True
    return False


def _tray_kind(ev: int) -> str:
    if ev in (_WM_CONTEXTMENU, _WM_RBUTTONUP, _WM_RBUTTONDOWN):
        return "menu"
    if ev in (_NIN_SELECT, _NIN_KEYSELECT, _WM_LBUTTONDOWN, _WM_LBUTTONUP, _WM_LBUTTONDBLCLK):
        return "open"
    return ""


def _show_host_window(window) -> None:
    if window is None:
        return
    window.show()
    window.raise_()
    try:
        window.requestActivate()
    except Exception:
        pass
    try:
        hwnd = int(window.winId())
    except Exception:
        hwnd = 0
    if hwnd:
        _user32.ShowWindow(hwnd, _SW_RESTORE)
        _user32.SetForegroundWindow(hwnd)


def _tray_class_proc(hwnd, msg, wparam, lparam):
    app = _TRAY_APP
    if app is not None:
        handled = app._tray_on_msg(hwnd, msg, wparam, lparam)
        if handled is not None:
            return handled
    return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)


_TRAY_CLASS_PROC = _WNDPROC(_tray_class_proc)


def _enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            _user32.SetProcessDPIAware()
        except Exception:
            pass


def _ui_metrics(sw: int, sh: int, dpi: float) -> dict[str, float | int]:
    """Window and type scale from screen size + DPI. Design box is 920x640 at 96 DPI."""
    dpi_scale = max(0.85, min(2.0, float(dpi) / 96.0))
    size_scale = min(1.0, sw / 1280.0, sh / 800.0)
    scale = max(0.8, min(2.0, dpi_scale * max(0.85, size_scale)))
    font = max(9, min(16, round(10 * scale)))
    pad = max(8, min(28, round(16 * scale)))
    meter = max(14, min(32, round(22 * scale)))
    w = min(int(920 * scale), max(480, int(sw * 0.92)))
    h = min(int(640 * scale), max(360, int(sh * 0.88)))
    w = max(w, min(560, max(320, sw - 32)))
    h = max(h, min(420, max(280, sh - 64)))
    return {"scale": scale, "font": font, "pad": pad, "meter": meter, "w": w, "h": h}


class BridgeClient:
    def __init__(self, on_event) -> None:
        self.on_event = on_event
        self.sock: socket.socket | None = None
        self.video_sock: socket.socket | None = None
        self.toast_sock: socket.socket | None = None
        self.alive = False
        self.seq = 0
        self.hello: dict = {}
        self.status: dict = {}
        self.frames = 0
        self._thread: threading.Thread | None = None
        self._video_thread: threading.Thread | None = None
        self._toast_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._video_lock = threading.Lock()
        self._toast_lock = threading.Lock()
        self._seq_lock = threading.Lock()
        self.generation = 0

    def connect(self, host: str, port: int) -> None:
        self.generation += 1
        gen = self.generation
        self.close()
        sock = socket.create_connection((host, port), timeout=5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 64 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 64 * 1024)
        except OSError:
            pass
        sock.settimeout(8)
        self.sock = sock
        self.alive = True
        self.seq = 0
        self._thread = threading.Thread(target=self._loop, args=(gen,), daemon=True)
        self._thread.start()

    def connect_video(self, host: str, port: int) -> None:
        self.close_video()
        sock = socket.create_connection((host, port), timeout=5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024)
        except OSError:
            pass
        sock.settimeout(None)
        self.video_sock = sock
        self._video_thread = threading.Thread(target=self._video_loop, args=(sock,), daemon=True, name="lx04-video-ack")
        self._video_thread.start()

    def connect_toast(self, host: str, port: int) -> bool:
        self.close_toast()
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 * 1024)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024)
            except OSError:
                pass
            sock.settimeout(None)
        except OSError:
            return False
        self.toast_sock = sock
        self._toast_thread = threading.Thread(target=self._toast_loop, args=(sock,), daemon=True, name="lx04-toast-ch")
        self._toast_thread.start()
        return True

    def close_toast(self) -> None:
        sock = self.toast_sock
        self.toast_sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def close_video(self) -> None:
        sock = self.video_sock
        self.video_sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def close(self) -> None:
        self.alive = False
        self.close_video()
        self.close_toast()
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
        data = protocol.encode_json(protocol.CONTROL, payload, seq=self._next_seq())
        # Tk thread must not wait on USB sendall (socket timeout is 8s).
        if threading.current_thread() is threading.main_thread():
            threading.Thread(target=self._send, args=(data,), daemon=True, name="lx04-ctrl").start()
            return
        self._send(data)

    def send_toast(self, cmd: str, **fields) -> None:
        payload = {"cmd": cmd}
        payload.update(fields)
        data = protocol.encode_json(protocol.CONTROL, payload, seq=self._next_seq())
        sock = self.toast_sock
        if sock is not None:
            try:
                with self._toast_lock:
                    if self.toast_sock is not sock:
                        raise OSError("toast socket replaced")
                    sock.sendall(data)
                return
            except OSError:
                self.close_toast()
        self._send(data)

    def toast_channel(self) -> str:
        return "17892" if self.toast_sock is not None else "17890"

    def send_file(self, jpeg: bytes, slot: int) -> None:
        if not jpeg or len(jpeg) > protocol.MAX_PAYLOAD:
            return
        flags = max(0, min(255, int(slot)))
        self._send(protocol.encode(protocol.FILE, jpeg, flags=flags, seq=self._next_seq()))

    def send_play(self, pcm: bytes, muted: bool = False) -> None:
        flags = protocol.FLAG_MUTED if muted else 0
        self._send(protocol.encode(protocol.PLAY, pcm or b"", flags=flags, seq=self._next_seq()))

    def send_video(self, jpeg: bytes) -> None:
        if not jpeg or len(jpeg) > protocol.MAX_PAYLOAD:
            return
        sock = self.video_sock
        if sock is None:
            return
        try:
            with self._video_lock:
                if self.video_sock is not sock:
                    return
                sock.sendall(protocol.encode(protocol.VIDEO, jpeg, seq=self._next_seq()))
        except OSError:
            self.close_video()

    def _video_loop(self, sock: socket.socket) -> None:
        try:
            while self.alive and sock is self.video_sock:
                header = _read_exact(sock, protocol.HEADER.size)
                decoded = protocol.try_decode_header(header)
                if decoded is None:
                    break
                msg_type, _flags, seq, _timestamp_ms, length = decoded
                if length:
                    _read_exact(sock, length)
                if msg_type == protocol.VIDEO_ACK:
                    self.on_event("video_ack", seq)
        except Exception:
            pass
        if sock is self.video_sock:
            self.close_video()

    def _toast_loop(self, sock: socket.socket) -> None:
        try:
            while self.alive and sock is self.toast_sock:
                header = _read_exact(sock, protocol.HEADER.size)
                decoded = protocol.try_decode_header(header)
                if decoded is None:
                    break
                msg_type, _flags, _seq, _timestamp_ms, length = decoded
                payload = _read_exact(sock, length) if length else b""
                if msg_type == protocol.EVENT:
                    try:
                        self.on_event("event", json.loads(payload.decode("utf-8")) if payload else {})
                    except Exception:
                        pass
        except Exception:
            pass
        if sock is self.toast_sock:
            self.close_toast()

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

    def _loop(self, gen: int) -> None:
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
            if self.alive and gen == self.generation:
                self.on_event("error", str(exc))
        finally:
            self.alive = False
            if gen == self.generation:
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
        elif frame.type == protocol.EVENT:
            try:
                self.on_event("event", frame.json())
            except Exception:
                pass
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


class ChoiceDrop:
    """Label list pushed to the QML ComboBox."""

    def __init__(self, kind: str, bridge: HostBridge) -> None:
        self.kind = kind
        self.bridge = bridge
        self.labels: list[str] = []

    def set_labels(self, labels: list[str]) -> None:
        self.labels = list(labels)
        self.bridge.set_labels(self.kind, self.labels)


class HostApp:
    def __init__(self, root: QtLoop, bridge: HostBridge) -> None:
        self.root = root
        self.bridge = bridge
        self.client = BridgeClient(self._on_bridge_event)
        self.sink = AudioSink()
        self.hw = HardwareMic()
        self.loopback = SpeakerLoopback()
        self.adb = adb_usb.find_adb()
        self.devices: list[str] = []
        self.connected = False
        self._session = False
        self._reviving = False
        self._serial = ""
        self._gain_sent_at = 0.0
        self._prev_render: tuple[str, str] | None = None
        self.play_peak = 0.0
        self.mic_enabled = Var(True)
        self.spk_enabled = Var(False)
        self.set_default_spk = Var(True)
        self.volume_sync = Var(False)
        self.pc_stats_enabled = Var(True)
        self.upside_down = Var(False)
        self.light_theme = Var(False)
        self.toast_mirror = Var(False)
        self.autostart = Var(False)
        self.minimize_to_tray = Var(False)
        self.disk_var = Var("")
        self.monitor_var = Var("")
        self.quality_var = Var(screen_mirror.DEFAULT_QUALITY)
        self._saved_disk = ""
        self._saved_monitor = ""
        self._monitors: list[screen_mirror.Monitor] = []
        self.mirror = screen_mirror.ScreenSender(self._send_mirror_frame)
        self._mirror_logged = False
        self.toast = toast_mirror.ToastSender(self._on_toast_change, self._on_toast_log)
        self._toast_logged = False
        self._toast_sync_after = None
        self.inject_var = Var("")
        self.spk_dev_var = Var("")
        self.device_var = Var("正在扫描…")
        self.mic_var = Var("尚未识别")
        self.gain_var = Var(100)
        self.gain_label_var = Var("100%  ·  0.0 dB")
        self.device_drop = ChoiceDrop("device", bridge)
        self.inject_drop = ChoiceDrop("inject", bridge)
        self.spk_drop = ChoiceDrop("spk", bridge)
        self.disk_drop = ChoiceDrop("disk", bridge)
        self.monitor_drop = ChoiceDrop("monitor", bridge)
        self.quality_drop = ChoiceDrop("quality", bridge)
        self.quality_drop.set_labels(list(screen_mirror.QUALITY_KEYS))
        self._inject_devices: list[tuple[str, str | int, str]] = []
        self._spk_devices: list[tuple[str, str]] = []
        self._routes_ready = False
        self._spk_volume = None
        self._pc_volume = None
        self._pc_muted = False
        self._vol_ignore_pc_until = 0.0
        self._vol_ignore_spk_until = 0.0
        self._stats_ticks = 0
        self._stats_logged = False
        self._hud_need_reconcile = False
        self._hud_from_apk = False
        self._hud_bg = {"sel": -1, "used": [False, False, False], "alpha": 100}
        self._hud_tk = None
        self._hud_pump = None
        self._route_lock = threading.Lock()
        self._route_gen = 0
        self._cable_key = None
        self._stats_busy = False
        self._closing = False
        self._stop_lock = threading.Lock()
        self._tray_hwnd = 0
        self._tray_icon = 0
        self._tray_icon_owned = False
        self._tray_shown = False
        self._tray_restore_after = None
        self._tray_menu_open = False
        self._tray_ignore_open_until = 0.0
        self._tray_last_kind = ""
        self._tray_last_at = 0.0
        self._tray_ping_at = 0.0
        self._host_hwnd = 0
        threading.Thread(target=pc_stats.snapshot, daemon=True).start()
        self._load_route_vars()

    def _boot_ui(self) -> None:
        self._log("adb: " + (self.adb or "未找到内置 adb"))
        if not self.sink.available():
            self._log("音频库未安装：在 host 目录执行  pip install -r requirements.txt")
        self._boot()

    def _ui(self, fn) -> None:
        try:
            if threading.current_thread() is threading.main_thread():
                fn()
                return
            self.root.after(0, fn)
        except Exception:
            pass

    def _after_paint(self, fn) -> None:
        self.root.after_idle(fn)

    def _spawn_route(self, fn) -> None:
        self._route_gen += 1
        gen = self._route_gen

        def work() -> None:
            with self._route_lock:
                if gen != self._route_gen:
                    return
                try:
                    fn()
                except Exception as exc:
                    self._log("切换通路失败: " + str(exc))

        threading.Thread(target=work, daemon=True, name="lx04-route").start()

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

    def _load_route_vars(self) -> None:
        try:
            data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        self.mic_enabled.set(bool(data.get("mic_enabled", True)))
        self.spk_enabled.set(bool(data.get("spk_enabled", False)))
        self.set_default_spk.set(bool(data.get("set_default_spk", True)))
        self.volume_sync.set(bool(data.get("volume_sync", False)))
        self.pc_stats_enabled.set(bool(data.get("pc_stats", True)))
        self.upside_down.set(bool(data.get("upside_down", False)))
        self.light_theme.set(bool(data.get("light_theme", False)))
        self.toast_mirror.set(bool(data.get("toast_mirror", False)))
        self.minimize_to_tray.set(bool(data.get("minimize_to_tray", False)))
        self._saved_inject = str(data.get("inject") or "")
        self._saved_spk = str(data.get("speaker") or "")
        self._saved_disk = str(data.get("pc_disk") or "")
        self._saved_monitor = str(data.get("pc_monitor") or "")
        self.quality_var.set(screen_mirror.pick_quality(str(data.get("mirror_quality") or "")).key)
        self.mirror.set_quality(self.quality_var.get())
        on = _autostart_enabled()
        self.autostart.set(on)
        if on:
            try:
                _set_autostart(True)
            except OSError:
                pass

    def _boot(self) -> None:
        threading.Thread(target=self._boot_scan, daemon=True, name="lx04-boot").start()

    def _boot_scan(self) -> None:
        hidden: list[str] = []
        devices: list[str] = []
        err = ""
        try:
            hidden = win_endpoint.tidy_cable_endpoints()
        except Exception as exc:
            err = str(exc)
        if self.adb:
            try:
                devices = adb_usb.list_devices(self.adb)
            except Exception as exc:
                err = (err + " " + str(exc)).strip()
        try:
            self.root.after(0, lambda: self._boot_apply(hidden, devices, err))
        except Exception:
            pass

    def _boot_apply(self, hidden: list[str], devices: list[str], err: str) -> None:
        if self._closing:
            return
        if hidden:
            self._log("已从系统播放列表隐藏：" + "、".join(hidden))
        if err:
            self._log("启动扫描: " + err)
        self.devices = devices
        if not self.adb:
            labels = ["未找到 adb"]
        else:
            labels = devices or ["没有 USB 设备（检查数据线 / USB 调试）"]
        self.device_drop.set_labels(labels)
        self.device_var.set(labels[0])
        self._log("USB 设备: " + (", ".join(devices) if devices else "无"))
        self.refresh_audio_devices(log=True, tidy=False)
        self._refresh_disks()
        self._refresh_monitors()
        self._routes_ready = True

    def _save_routes(self) -> None:
        payload = {
            "mic_enabled": bool(self.mic_enabled.get()),
            "spk_enabled": bool(self.spk_enabled.get()),
            "set_default_spk": bool(self.set_default_spk.get()),
            "volume_sync": bool(self.volume_sync.get()),
            "pc_stats": bool(self.pc_stats_enabled.get()),
            "upside_down": bool(self.upside_down.get()),
            "light_theme": bool(self.light_theme.get()),
            "toast_mirror": bool(self.toast_mirror.get()),
            "minimize_to_tray": bool(self.minimize_to_tray.get()),
            "pc_disk": self._selected_disk(),
            "pc_monitor": self._selected_monitor_key(),
            "mirror_quality": self.quality_var.get(),
            "inject": self.inject_var.get(),
            "speaker": self.spk_dev_var.get(),
        }
        try:
            ROUTES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def refresh_audio_devices(self, log: bool = True, tidy: bool = True) -> None:
        if tidy:
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
        self.inject_drop.set_labels(inject_labels)
        preferred = inject_labels[0] if inject_labels else None
        chosen = _pick_label(inject_labels, previous_inject, preferred)
        if chosen:
            self.inject_var.set(chosen)
        self._spk_devices = win_endpoint.list_render_endpoints()
        spk_labels = [name for _device_id, name in self._spk_devices]
        self.spk_drop.set_labels(spk_labels)
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
        self._after_paint(self._mic_route_job)

    def _mic_route_job(self) -> None:
        self._save_routes()
        if not self.connected:
            return
        on = bool(self.mic_enabled.get())
        inject = self._selected_inject()
        self._spawn_route(lambda: self._apply_mic_route(on=on, inject=inject))

    def _on_spk_route_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._spk_route_job)

    def _spk_route_job(self) -> None:
        self._save_routes()
        if not self.connected:
            return
        on = bool(self.spk_enabled.get())
        set_default = bool(self.set_default_spk.get())
        mic_on = bool(self.mic_enabled.get())
        speaker = self._selected_speaker()
        inject = self._selected_inject()
        self._spawn_route(
            lambda: self._apply_speaker_route(
                on=on,
                speaker=speaker,
                set_default=set_default,
                inject=inject,
                mic_on=mic_on,
            )
        )

    def _on_upside_down_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._upside_down_job)

    def _upside_down_job(self) -> None:
        self._save_routes()
        self._push_upside_down()
        if self.connected:
            self._log("音箱屏幕: " + ("吊装倒转" if self.upside_down.get() else "正向"))

    def _push_upside_down(self) -> None:
        if not self.connected:
            return
        self.client.send_control("upside_down", on=bool(self.upside_down.get()))

    def _on_light_theme_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._light_theme_job)

    def _light_theme_job(self) -> None:
        self._save_routes()
        if self._hud_from_apk:
            return
        self._push_light_theme()
        if self.connected:
            self._log("音箱屏幕: " + ("浅色" if self.light_theme.get() else "深色"))

    def _push_light_theme(self) -> None:
        if not self.connected:
            return
        self.client.send_control("light_theme", on=bool(self.light_theme.get()))

    def _on_disk_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._disk_job)

    def _disk_job(self) -> None:
        self._save_routes()
        if self.connected and self.pc_stats_enabled.get():
            self._spawn_stats(force=True)

    def _selected_disk(self) -> str:
        label = (self.disk_var.get() or "").strip()
        if label:
            token = label.split()[0].upper()
            if token[:1].isalpha():
                return token[:1] + ":"
        saved = str(getattr(self, "_saved_disk", "") or "").strip()
        if saved:
            return saved[:1].upper() + ":" if saved[:1].isalpha() else saved
        return pc_stats.default_disk()

    def _refresh_disks(self) -> None:
        previous = self._selected_disk()
        items = pc_stats.list_disks()
        labels = [pc_stats.disk_choice_label(item) for item in items]
        self.disk_drop.set_labels(labels)
        chosen = ""
        want = (previous or getattr(self, "_saved_disk", "") or "").upper()[:2]
        for item, label in zip(items, labels):
            if str(item.get("letter") or "").upper()[:2] == want:
                chosen = label
                break
        if not chosen:
            system = next((label for item, label in zip(items, labels) if item.get("system")), "")
            chosen = system or (labels[0] if labels else "")
        if chosen:
            self.disk_var.set(chosen)

    def _refresh_monitors(self) -> None:
        previous = self._selected_monitor_key() or getattr(self, "_saved_monitor", "")
        try:
            self._monitors = screen_mirror.list_monitors()
        except Exception:
            self._monitors = []
        labels = [item.label() for item in self._monitors]
        if hasattr(self, "monitor_drop"):
            self.monitor_drop.set_labels(labels or ["没有显示器"])
        chosen = screen_mirror.pick_monitor(self._monitors, previous)
        if chosen:
            self.monitor_var.set(chosen.label())
            self._saved_monitor = chosen.key
        elif labels:
            self.monitor_var.set(labels[0])

    def _selected_monitor_key(self) -> str:
        label = (self.monitor_var.get() or "").strip()
        for item in self._monitors:
            if item.label() == label:
                return item.key
        return str(getattr(self, "_saved_monitor", "") or "")

    def _on_monitor_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._monitor_job)

    def _monitor_job(self) -> None:
        self._save_routes()
        if self.mirror.running():
            self._start_mirror(restart=True)

    def _on_quality_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._quality_job)

    def _quality_job(self) -> None:
        preset = self.mirror.set_quality(self.quality_var.get())
        self.quality_var.set(preset.key)
        self._save_routes()
        self._log("镜像码率: " + preset.key)

    def _send_mirror_frame(self, jpeg: bytes) -> None:
        if not self.connected or not self.mirror.running() or self.toast.showing():
            return
        self.client.send_video(jpeg)

    def _on_toast_log(self, line: str) -> None:
        try:
            self.root.after(0, lambda l=line: self._log(l))
        except Exception:
            pass

    def _on_toast_change(self, showing: bool, content) -> None:
        if self.connected:
            try:
                if showing:
                    payload = content.as_control() if content is not None else {"title": "系统弹窗"}
                    self.client.send_toast("toast_overlay", on=True, **payload)
                else:
                    self.client.send_toast("toast_overlay", on=False)
            except Exception:
                pass
        try:
            self.root.after(0, lambda s=showing, c=content: self._apply_toast_ui(s, c))
        except Exception:
            pass

    def _apply_toast_ui(self, showing: bool, content) -> None:
        if showing:
            self.mirror.pause()
            title = ""
            buttons = ""
            if content is not None:
                title = content.title or content.app
                if content.buttons:
                    buttons = "  按钮[" + "][".join(b.label for b in content.buttons) + "]"
            fp = (title, buttons)
            if fp != getattr(self, "_toast_ui_fp", None):
                self._toast_ui_fp = fp
                via = self.client.toast_channel()
                self._log("系统弹窗已同步到音箱（" + via + "）" + ((": " + title) if title else "") + buttons)
            return
        self._toast_ui_fp = None
        self._toast_logged = False
        self.mirror.resume()

    def _on_autostart_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._autostart_job)

    def _autostart_job(self) -> None:
        want = bool(self.autostart.get())
        try:
            _set_autostart(want)
        except OSError as exc:
            self.autostart.set(_autostart_enabled())
            self._log("开机自启动设置失败: " + str(exc))
            return
        self._log("开机自启动: " + ("已开启，登录 Windows 后自动打开上位机" if want else "已关闭"))

    def _on_tray_pref_change(self) -> None:
        if not self._routes_ready:
            return
        self._save_routes()
        on = bool(self.minimize_to_tray.get())
        self._log("关闭后最小化到托盘: " + ("已开启" if on else "已关闭"))
        if not on and self._tray_shown:
            self._restore_from_tray()
            self._tray_remove()

    def _on_toast_mirror_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._toast_mirror_job)

    def _toast_mirror_job(self) -> None:
        self._save_routes()
        if self._toast_sync_after is not None:
            try:
                self.root.after_cancel(self._toast_sync_after)
            except Exception:
                pass
        self._toast_sync_after = self.root.after(250, self._apply_toast_mirror_toggle)

    def _apply_toast_mirror_toggle(self) -> None:
        self._toast_sync_after = None
        on = bool(self.toast_mirror.get())
        connected = self.connected

        def work() -> None:
            self._sync_toast_mirror(on=on)
            err = self.toast.error
            self.toast.error = ""
            if err:
                self._log("系统弹窗: " + err)
            if on:
                via = self.client.toast_channel() if connected else "17892"
                self._log(
                    "已开启系统弹窗同步（独立通道 "
                    + via
                    + "）：系统通知的标题、正文、按钮会显示在音箱上，点按即点电脑通知。"
                )
            else:
                self._log("已关闭系统弹窗同步")

        threading.Thread(target=work, daemon=True, name="lx04-toast-tog").start()

    def _sync_toast_mirror(self, on: bool | None = None) -> None:
        try:
            if on is None:
                on = bool(self.toast_mirror.get())
            if self.connected and on:
                self.toast.start()
                return
            was_showing = self.toast.showing()
            self.toast.stop()
            self._toast_logged = False
            if was_showing and self.connected:
                try:
                    self.client.send_toast("toast_overlay", on=False)
                except Exception:
                    pass
            self.mirror.resume()
        except Exception as exc:
            self._log("系统弹窗同步失败: " + str(exc))

    def _apply_mirror_request(self, on: bool) -> None:
        if on and self.connected:
            if not self.mirror.running():
                self._start_mirror()
            return
        if self.mirror.running():
            self.mirror.stop()
            self._mirror_logged = False
            self._log("屏幕镜像已关闭，已停止推画面")
            if self.pc_stats_enabled.get():
                self._spawn_stats(force=True)

    def _start_mirror(self, restart: bool = False) -> None:
        if not self.connected:
            return
        if self.client.video_sock is None:
            try:
                self.client.connect_video("127.0.0.1", protocol.VIDEO_PORT)
            except Exception as exc:
                self._log("屏幕通道未打开: " + str(exc))
                return
        self._refresh_monitors()
        chosen = self.mirror.start(self._selected_monitor_key())
        self._mirror_logged = False
        if chosen is None:
            self._log("屏幕镜像失败: " + (self.mirror.error or "没有可用的显示器"))
            return
        self.monitor_var.set(chosen.label())
        self._saved_monitor = chosen.key
        self.client.send_control("mirror_info", title=chosen.label())
        self._save_routes()
        self._log(("屏幕镜像已切换到: " if restart else "屏幕镜像: ") + chosen.label())

    def _on_pc_stats_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._pc_stats_job)

    def _pc_stats_job(self) -> None:
        self._save_routes()
        if not self.pc_stats_enabled.get():
            self.pc_line.configure(text="电脑状态：已关闭，音箱屏幕只显示桥接信息。")
            return
        if self.connected:
            self._spawn_stats(force=True)

    def _spawn_stats(self, force: bool = False) -> None:
        if not self.connected:
            return
        want_full = bool(self.pc_stats_enabled.get()) and (force or not self.mirror.running())
        if not want_full:
            try:
                self.client.send_control("pc_stats", **pc_stats.clock_fields())
            except Exception:
                pass
            return
        if self._stats_busy:
            return
        self._stats_busy = True
        disk = self._selected_disk()
        threading.Thread(
            target=self._push_pc_stats,
            kwargs={"force": force, "disk": disk},
            daemon=True,
            name="lx04-stats",
        ).start()

    def _push_pc_stats(self, force: bool = False, disk: str | None = None) -> None:
        try:
            if not self.connected:
                return
            if self.mirror.running() and not force:
                return
            snap = pc_stats.snapshot(disk or "C:")
            payload = {key: value for key, value in snap.items() if value is not None and value != ""}
            self.client.send_control("pc_stats", **payload)
            line = pc_stats.format_line(snap)
            self._ui(lambda t=line: self.pc_line.configure(text=t))
            if not self._stats_logged:
                self._stats_logged = True
                extra = ""
                if "cpuT" not in payload:
                    extra = "（CPU 温度未读到；可点「CPU 温度 / Afterburner」打开官网，占用仍会显示）"
                self._log("已向音箱发送电脑状态" + extra)
        except Exception as exc:
            err = str(exc)
            self._ui(lambda t=err: self.pc_line.configure(text="电脑状态读取失败: " + t))
            if force:
                self._log("电脑状态: " + err)
        finally:
            self._stats_busy = False

    def _on_volume_sync_change(self) -> None:
        if not self._routes_ready:
            return
        self._after_paint(self._volume_sync_job)

    def _volume_sync_job(self) -> None:
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

    def _apply_mic_route(self, on: bool | None = None, inject=None) -> None:
        if on is None:
            on = bool(self.mic_enabled.get())
        if not on:
            self.hw.stop(self.adb, self._serial)
            self.sink.stop()
            self._log("已关闭麦克风通路")
            return
        self.sink.configure(48000, 1)
        self._start_inject(inject)
        if self.adb and self._serial and not self.hw.running():
            try:
                self.hw.start(self.adb, self._serial, self.sink)
                self._log("已从音箱数字麦直采：48kHz 单声道（tinycap pcmC0D1c）")
                self.client.send_control("stop_mic")
            except Exception as exc:
                self._log("硬件直采失败，回退 APK 麦克风: " + str(exc))
                self.client.send_control("start_mic")

    def _apply_speaker_route(
        self,
        on: bool | None = None,
        speaker=None,
        set_default: bool | None = None,
        inject=None,
        mic_on: bool | None = None,
    ) -> None:
        if on is None:
            on = bool(self.spk_enabled.get())
        if not on:
            self._restore_render()
            self._log("已关闭扬声器通路")
            return
        self._start_speaker(speaker=speaker, set_default=set_default, inject=inject, mic_on=mic_on)

    def _install_vb(self) -> None:
        if not self.bridge.askokcancel(vb_cable.DONATE_TEXT):
            return
        self._log(vb_cable.run_official_setup())
        self.refresh_audio_devices()

    def _install_hifi(self) -> None:
        if not self.bridge.askokcancel(hifi_cable.DONATE_TEXT):
            return
        self._log(hifi_cable.run_official_setup())
        self.refresh_audio_devices()

    def _on_afterburner(self) -> None:
        if afterburner.sensors_live():
            self.bridge.showinfo(afterburner.RUNNING_TEXT)
            return
        exe = afterburner.find_exe()
        if exe is not None:
            if not self.bridge.askokcancel(afterburner.LAUNCH_TEXT):
                return
            self._log(afterburner.launch(exe))
            self.root.after(2000, lambda: self._spawn_stats(force=True))
            return
        if not self.bridge.askokcancel(afterburner.DOWNLOAD_TEXT):
            return
        self._log(afterburner.open_download())

    def _open_hud_preview(self) -> None:
        import tkinter as tk
        from PySide6.QtCore import QTimer

        if self._hud_tk is None:
            self._hud_tk = tk.Tk()
            self._hud_tk.withdraw()
            pump = QTimer(self.bridge)
            pump.timeout.connect(self._pump_hud)
            pump.start(33)
            self._hud_pump = pump
        hud_preview.open_window(
            self._hud_tk,
            light=bool(self.light_theme.get()),
            on_change=self._on_hud_style_change,
        )

    def _pump_hud(self) -> None:
        tk_root = self._hud_tk
        if tk_root is None:
            return
        try:
            tk_root.update()
        except Exception:
            pass

    def _on_hud_bg_status(self, data: dict) -> None:
        payload = data.get("hudBg")
        if not isinstance(payload, dict):
            return
        used = payload.get("used") or []
        flags = []
        for i in range(3):
            flags.append(bool(used[i]) if i < len(used) else False)
        try:
            sel = int(payload.get("sel", -1))
        except (TypeError, ValueError):
            sel = -1
        try:
            alpha = int(payload.get("alpha", 100))
        except (TypeError, ValueError):
            alpha = 100
        self._hud_bg = {"sel": sel, "used": flags, "alpha": alpha}

    def _upload_hud_bg(self) -> None:
        if not self.connected:
            self.bridge.showinfo("请先连接音箱，再上传监视页背景。")
            return
        path = self.bridge.pick_image()
        if not path:
            return
        try:
            jpeg = screen_mirror.encode_still(path)
        except Exception as exc:
            self.bridge.showerror("无法处理这张图片：\n" + str(exc))
            return
        slot = self._pick_hud_bg_slot()
        if slot is None:
            return
        self.client.send_file(jpeg, slot)
        self._log(f"已上传监视页背景到槽位 {slot + 1}（{len(jpeg) // 1024} KB）")

    def _pick_hud_bg_slot(self) -> int | None:
        used = list(self._hud_bg.get("used") or [False, False, False])
        while len(used) < 3:
            used.append(False)
        for i, taken in enumerate(used):
            if not taken:
                return i
        return self.bridge.pick_bg_slot()

    def _on_hud_style_change(self, state: dict, reset: bool = False) -> None:
        if self._hud_from_apk:
            return
        self.light_theme.set(bool(state.get("light")))
        if self._routes_ready:
            self._save_routes()
        self._push_light_theme()
        self._push_hud_style(reset=reset)
        if self.connected and reset:
            self._log("已将音箱屏幕样式恢复默认")

    def _push_hud_style(self, reset: bool = False) -> None:
        if not self.connected:
            return
        if reset:
            rev = int(hud_preview.live_state(bool(self.light_theme.get())).get("rev") or 0)
            self.client.send_control("hud_style", reset=True, rev=rev)
            return
        payload = hud_preview.control_payload(hud_preview.live_state(bool(self.light_theme.get())))
        self.client.send_control("hud_style", **payload)

    def _begin_hud_reconcile(self) -> None:
        self._hud_need_reconcile = True
        self.root.after(900, self._hud_reconcile_timeout)

    def _hud_reconcile_timeout(self) -> None:
        if not self.connected or not self._hud_need_reconcile:
            return
        self._hud_need_reconcile = False
        self._push_light_theme()
        self._push_hud_style()

    def _on_hud_status(self, data: dict) -> None:
        if self._hud_need_reconcile:
            if "hudStyle" in data or "lightTheme" in data:
                self._reconcile_hud(data)
            return
        if "lightTheme" in data:
            self._sync_light_theme_from_apk(bool(data["lightTheme"]))
        payload = data.get("hudStyle")
        if not isinstance(payload, dict):
            return
        apk_rev = int(payload.get("rev") or 0)
        host_rev = int(hud_preview.live_state(bool(self.light_theme.get())).get("rev") or 0)
        if apk_rev > host_rev:
            self._apply_hud_from_apk(data)

    def _sync_light_theme_from_apk(self, light: bool) -> None:
        if bool(self.light_theme.get()) == bool(light):
            return
        self._hud_from_apk = True
        try:
            self.light_theme.set(light)
            if self._routes_ready:
                self._save_routes()
            hud_preview.set_light(light)
        finally:
            self._hud_from_apk = False

    def _reconcile_hud(self, data: dict) -> None:
        self._hud_need_reconcile = False
        payload = data.get("hudStyle")
        apk_rev = int(payload.get("rev") or 0) if isinstance(payload, dict) else 0
        host_state = hud_preview.live_state(bool(self.light_theme.get()))
        host_rev = int(host_state.get("rev") or 0)
        if apk_rev > host_rev and isinstance(payload, dict):
            self._apply_hud_from_apk(data)
            return
        self._push_light_theme()
        self._push_hud_style()

    def _apply_hud_from_apk(self, data: dict) -> None:
        payload = data.get("hudStyle") or {}
        light = bool(data["lightTheme"]) if "lightTheme" in data else bool(self.light_theme.get())
        state = hud_preview.state_from_payload(payload, light)
        state["light"] = light
        self._hud_from_apk = True
        try:
            hud_preview.replace_state(state)
            self.light_theme.set(light)
            if self._routes_ready:
                self._save_routes()
        finally:
            self._hud_from_apk = False

    def _start_inject(self, selected=None) -> None:
        if selected is None:
            selected = self._selected_inject()
        if selected is None:
            raise RuntimeError("没有可用的播放设备。请先点刷新，或安装 VB-CABLE。")
        kind, handle, label = selected
        if win_endpoint.is_cable_render(label) or kind == "hidden":
            key = (kind, handle)
            if self._cable_key != key:
                prepared = win_endpoint.prepare_vb_cable()
                self._cable_key = key
                for line in prepared.get("logs") or []:
                    self._log(line)
        if kind == "hidden":
            self.sink.start_hidden_cable(label.replace("  [隐藏]", "").strip())
        else:
            self.sink.start(int(handle))
        rec = win_mic.matching_recording_device(self.sink.device_name)
        rec_name = rec[1] if rec else "CABLE Output"
        self._ui(lambda n=rec_name: self.mic_var.set("请选择： " + n))
        self._log("麦克风已送入: " + self.sink.device_name + "  /  " + label)
        self._log(
            f"注入格式: {self.sink.out_rate}Hz / {self.sink._dtype} / {self.sink.out_channels}ch"
        )
        self._log("语音软件请选择: " + rec_name)

    def _start_speaker(self, speaker=None, set_default: bool | None = None, inject=None, mic_on: bool | None = None) -> None:
        selected = speaker if speaker is not None else self._selected_speaker()
        if selected is None:
            self._log("没有可环回的播放设备，扬声器通路未打开。可用「音箱试音」检查喇叭。")
            return
        device_id, name = selected
        if inject is None:
            inject = self._selected_inject()
        if set_default is None:
            set_default = bool(self.set_default_spk.get())
        if mic_on is None:
            mic_on = bool(self.mic_enabled.get())
        if mic_on and inject is not None and win_endpoint.is_cable_render(name) and win_endpoint.is_cable_render(inject[2]):
            self._log("警告：扬声器和麦克风都选了 VB-CABLE，微信里会串进系统声音。")
        self.loopback.stop()
        self.play_peak = 0.0
        prepared = win_endpoint.prepare_render_device(device_id)
        for line in prepared.get("logs") or []:
            self._log(line)
        device_id = prepared.get("device_id") or device_id
        if set_default:
            current = win_endpoint.get_default_render()
            if current and current[0] != device_id and self._prev_render is None:
                self._prev_render = current
            if win_endpoint.set_default_render(device_id):
                self._log("已把系统播放切到: " + name)
            else:
                self._log("未能把系统播放切到选中的设备。")
        self.loopback.start(device_id, name, self._on_loopback_pcm)
        self._log("扬声器环回: " + name)

    def _on_loopback_pcm(self, pcm: bytes, muted: bool) -> None:
        silent = muted or (self.volume_sync.get() and self._pc_muted)
        if silent:
            pcm = b"\x00" * len(pcm)
            self.play_peak = 0.0
        else:
            self.play_peak = self.loopback.peak
        self.client.send_play(pcm, muted=silent)

    def _restore_render(self, log: bool = True) -> None:
        self.loopback.stop()
        prev = self._prev_render
        self._prev_render = None
        self.play_peak = 0.0
        if prev:
            if win_endpoint.set_default_render(prev[0]) and log:
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
            self.bridge.showerror("请先连接音箱。")
            return
        rate = 48000
        frames = int(rate * 0.7)
        samples = array.array("h")
        for index in range(frames):
            value = int(9000 * math.sin(2.0 * math.pi * 440.0 * index / rate))
            samples.append(value)
            samples.append(value)
        pcm = samples.tobytes()
        step = (rate // 100) * 4

        def _send() -> None:
            for offset in range(0, len(pcm), step):
                if not self.connected:
                    break
                chunk = pcm[offset : offset + step]
                self.play_peak = max(self.play_peak, self._pcm_peak(chunk))
                self.client.send_play(chunk)
                time.sleep(0.01)

        threading.Thread(target=_send, daemon=True).start()
        self._log("已向音箱送出试音。应能从音箱喇叭听到「嘀」。")

    def _on_test_tone(self) -> None:
        if not self.mic_enabled.get():
            self.bridge.showerror("请先勾选「麦克风 → 电脑」，并选好 CABLE Input。")
            return
        try:
            if not self.sink.running():
                self.sink.configure(48000, 1)
                self._start_inject()
            self.sink.play_test_tone()
            self._log("已送出试音。请看语音软件里「CABLE Output」的音量条是否跳动。")
        except Exception as exc:
            self.bridge.showerror(str(exc))
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
            self.device_drop.set_labels(["未找到 adb"])
            self.device_var.set("未找到 adb")
            self._refresh_disks()
            return
        try:
            self.devices = adb_usb.list_devices(self.adb)
        except Exception as exc:
            self._log("读取 adb 设备失败: " + str(exc))
            self.devices = []
        labels = self.devices or ["没有 USB 设备（检查数据线 / USB 调试）"]
        self.device_drop.set_labels(labels)
        self.device_var.set(labels[0])
        self._log("USB 设备: " + (", ".join(self.devices) if self.devices else "无"))
        self.refresh_audio_devices(log=False)
        self._refresh_disks()
        self._refresh_monitors()

    def connect(self) -> None:
        if not self.adb:
            self.bridge.showerror("没有找到内置 adb。请重新打包上位机。")
            return
        serial = self.device_var.get()
        if not self.devices or serial.startswith("没有") or serial.startswith("未找到"):
            self.bridge.showerror("没有可用的 USB 设备。请拔掉数据线再插上，并打开 USB 调试。")
            return
        try:
            gadget = adb_usb.enable_usb_microphone(self.adb, serial)
            if gadget:
                self._log("USB 功能: " + " ".join(gadget.split()))
            mic = adb_usb.take_speaker_mic(self.adb, serial)
            self._log(mic)
            self._log(adb_usb.ensure_bridge_running(self.adb, serial))
            adb_usb.usb_forward(self.adb, serial)
            self._connect_tcp(serial)
            self._session = True
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
            self._spawn_stats(force=True)
            self._push_upside_down()
            self._begin_hud_reconcile()
            if self.spk_enabled.get():
                self._apply_speaker_route()
            else:
                self._log("扬声器通路已关闭。可用「音箱试音」检查喇叭。")
            self._sync_toast_mirror()
            self.headline.configure(text="USB 已连接")
        except Exception as exc:
            self._session = False
            self.connected = False
            self._restore_render()
            try:
                self.client.close()
            except Exception:
                pass
            try:
                self.toast.stop()
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
            self.bridge.showerror(str(exc))
            self._log("连接失败: " + str(exc))

    def _connect_tcp(self, serial: str) -> None:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                if attempt:
                    self._log(adb_usb.ensure_bridge_running(self.adb, serial))
                    adb_usb.usb_forward(self.adb, serial)
                    time.sleep(0.35 * attempt)
                self.client.connect("127.0.0.1", protocol.PORT)
                try:
                    self.client.connect_video("127.0.0.1", protocol.VIDEO_PORT)
                except Exception:
                    pass
                toast_ok = False
                for toast_try in range(4):
                    if self.client.connect_toast("127.0.0.1", protocol.TOAST_PORT):
                        toast_ok = True
                        break
                    time.sleep(0.12 * (toast_try + 1))
                if toast_ok:
                    self._log("系统弹窗走独立通道 17892")
                else:
                    self._log("系统弹窗通道 17892 未接通，暂走 17890")
                return
            except Exception as exc:
                last_err = exc
        raise last_err if last_err else RuntimeError("无法连上音箱后台服务")

    def disconnect(self) -> None:
        self._session = False
        self.connected = False
        self._mirror_logged = False
        self._toast_logged = False
        self._stats_logged = False
        if not self._closing:
            self.headline.configure(text="已断开")
            self.detail.configure(text="可以重新点连接。")
            self._draw_meter("mic", 0)
            self._draw_meter("spk", 0)
        threading.Thread(target=self._shutdown_work, daemon=True, name="lx04-disc").start()

    def _shutdown_work(self) -> None:
        with self._stop_lock:
            try:
                self.client.close()
                if self._serial:
                    self.hw.stop(self.adb, self._serial)
                else:
                    self.hw.stop()
                self.sink.stop()
                self._restore_render(log=not self._closing)
                self.mirror.stop()
                self.toast.stop()
                if self.adb and self._serial:
                    try:
                        msg = adb_usb.release_speaker_mic(self.adb, self._serial)
                        if not self._closing:
                            self._log(msg)
                    except Exception as exc:
                        if not self._closing:
                            self._log("恢复小爱麦失败: " + str(exc))
            except Exception:
                pass

    def _on_close(self, force: bool = False) -> None:
        if _close_goes_to_tray(self._closing, force, bool(self.minimize_to_tray.get())):
            self._hide_to_tray()
            return
        self._closing = True
        self._session = False
        self.connected = False
        self._tray_remove()
        pump = getattr(self, "_hud_pump", None)
        if pump is not None:
            pump.stop()
        if self._hud_tk is not None:
            try:
                self._hud_tk.destroy()
            except Exception:
                pass
            self._hud_tk = None
        try:
            self.root.withdraw()
            self.root.update_idletasks()
        except Exception:
            pass
        threading.Thread(target=self._shutdown_work, daemon=False, name="lx04-quit").start()
        self.root.destroy()

    def _tray_load_icon(self) -> int:
        if self._tray_icon:
            return self._tray_icon
        small = (wintypes.HICON * 1)()
        n = _shell32.ExtractIconExW(str(Path(sys.executable).resolve()), 0, None, small, 1)
        if n:
            self._tray_icon = int(small[0] or 0)
            self._tray_icon_owned = bool(self._tray_icon)
        if not self._tray_icon:
            self._tray_icon = int(_user32.LoadIconW(None, _IDI_APPLICATION) or 0)
            self._tray_icon_owned = False
        return self._tray_icon

    def _tray_ensure_hwnd(self) -> bool:
        if self._tray_hwnd:
            return True
        hinst = _kernel32.GetModuleHandleW(None)
        wc = _WNDCLASSW()
        wc.lpfnWndProc = _TRAY_CLASS_PROC
        wc.hInstance = hinst
        wc.lpszClassName = _TRAY_CLASS
        if not _user32.RegisterClassW(ctypes.byref(wc)):
            if ctypes.GetLastError() != _ERROR_CLASS_ALREADY_EXISTS:
                return False
        global _TRAY_APP
        _TRAY_APP = self
        hwnd = _user32.CreateWindowExW(
            _WS_EX_TOOLWINDOW, _TRAY_CLASS, "LX04 Tray", _WS_POPUP,
            -32000, -32000, 1, 1, None, None, hinst, None,
        )
        if not hwnd:
            _TRAY_APP = None
            return False
        self._tray_hwnd = int(hwnd)
        return True

    def _tray_on_msg(self, hwnd, msg, wparam, lparam):
        if msg == _TASKBAR_CREATED:
            self._tray_shown = False
            self._tray_add()
            return 0
        if msg != _WM_TRAY or int(hwnd) != int(self._tray_hwnd):
            return None
        kind = _tray_kind(int(lparam) & 0xFFFF)
        if not kind:
            return 0
        now = time.monotonic()
        if kind == self._tray_last_kind and now - self._tray_last_at < 0.4:
            return 0
        self._tray_last_kind = kind
        self._tray_last_at = now
        if kind == "menu":
            self._show_tray_menu()
        elif kind == "open":
            if self._host_hwnd:
                _user32.ShowWindow(self._host_hwnd, _SW_RESTORE)
                _user32.SetForegroundWindow(self._host_hwnd)
            self.root.after(0, self._restore_from_tray)
        return 0

    def _cancel_tray_restore(self) -> None:
        after_id = self._tray_restore_after
        self._tray_restore_after = None
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass

    def _tray_ping(self) -> None:
        if self._closing or not self._tray_hwnd:
            return
        nid = self._tray_nid()
        if _shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(nid)):
            self._tray_shown = True
            return
        self._tray_shown = False
        self._tray_add()

    def _tray_nid(self) -> _NOTIFYICONDATAW:
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self._tray_hwnd
        nid.uID = 1
        nid.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        nid.uCallbackMessage = _WM_TRAY
        nid.hIcon = self._tray_load_icon()
        nid.szTip = _HOST_TITLE
        return nid

    def _tray_add(self) -> bool:
        if self._tray_shown:
            return True
        if not self._tray_ensure_hwnd():
            return False
        nid = self._tray_nid()
        ok = bool(_shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(nid)))
        if not ok:
            ok = bool(_shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(nid)))
        self._tray_shown = ok
        if not ok:
            self._tray_remove()
        return ok

    def _tray_remove(self) -> None:
        global _TRAY_APP
        self._cancel_tray_restore()
        if self._tray_shown and self._tray_hwnd:
            try:
                _shell32.Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(self._tray_nid()))
            except Exception:
                pass
        self._tray_shown = False
        if self._tray_hwnd:
            try:
                _user32.DestroyWindow(self._tray_hwnd)
            except Exception:
                pass
            self._tray_hwnd = 0
        if _TRAY_APP is self:
            _TRAY_APP = None
        if self._tray_icon and self._tray_icon_owned:
            try:
                _user32.DestroyIcon(self._tray_icon)
            except Exception:
                pass
        self._tray_icon = 0
        self._tray_icon_owned = False

    def _hide_to_tray(self) -> None:
        try:
            self._host_hwnd = int(self.root.winfo_id())
        except Exception:
            self._host_hwnd = 0
        if not self._tray_add():
            self._log("无法创建托盘图标，将正常退出")
            self._on_close(force=True)
            return
        try:
            self.root.withdraw()
        except Exception:
            pass
        self._log("已最小化到托盘。右键选“打开”或左键可恢复窗口。")

    def _restore_from_tray(self) -> None:
        self._tray_restore_after = None
        if self._closing or self._tray_menu_open:
            return
        if time.monotonic() < self._tray_ignore_open_until:
            return
        try:
            if self._host_hwnd:
                _user32.ShowWindow(self._host_hwnd, _SW_RESTORE)
                _user32.SetForegroundWindow(self._host_hwnd)
            _show_host_window(self.root.window)
            self._log("已打开窗口")
        except Exception as exc:
            self._log("恢复窗口失败: " + str(exc))

    def _show_tray_menu(self) -> None:
        if self._closing or self._tray_menu_open:
            return
        self._cancel_tray_restore()
        menu = _user32.CreatePopupMenu()
        if not menu:
            return
        cmd = 0
        owner = 0
        self._tray_menu_open = True
        try:
            _user32.AppendMenuW(menu, _MF_STRING, _TRAY_OPEN, "打开")
            _user32.AppendMenuW(menu, _MF_STRING, _TRAY_QUIT, "退出")
            pt = _POINT()
            _user32.GetCursorPos(ctypes.byref(pt))
            owner = _user32.CreateWindowExW(
                _WS_EX_TOOLWINDOW | _WS_EX_TOPMOST, _TRAY_CLASS, "", _WS_POPUP,
                pt.x, pt.y, 1, 1, None, None, _kernel32.GetModuleHandleW(None), None,
            )
            if owner:
                _user32.ShowWindow(owner, _SW_SHOW)
                _user32.SetForegroundWindow(owner)
            owner_hwnd = owner or self._tray_hwnd
            cmd = int(_user32.TrackPopupMenu(
                menu,
                _TPM_RIGHTBUTTON | _TPM_BOTTOMALIGN | _TPM_RETURNCMD,
                pt.x, pt.y, 0, owner_hwnd, None,
            ) or 0)
            if owner:
                _user32.PostMessageW(owner, _WM_NULL, 0, 0)
        finally:
            if owner:
                try:
                    _user32.DestroyWindow(owner)
                except Exception:
                    pass
            _user32.DestroyMenu(menu)
            self._tray_menu_open = False
            self._cancel_tray_restore()
            self._tray_ignore_open_until = time.monotonic() + 0.3
        if cmd == _TRAY_OPEN:
            self._tray_ignore_open_until = 0.0
            self._restore_from_tray()
        elif cmd == _TRAY_QUIT:
            self._on_close(force=True)

    def _begin_revive(self) -> None:
        if self._reviving or not self._session:
            return
        self._reviving = True
        threading.Thread(target=self._revive_worker, daemon=True).start()

    def _revive_worker(self) -> None:
        last_err = "unknown"
        try:
            for attempt in range(8):
                if not self._session:
                    self._reviving = False
                    return
                try:
                    serial = self._serial
                    status = adb_usb.ensure_bridge_running(self.adb, serial)
                    self.root.after(0, lambda s=status: self._log(s))
                    try:
                        adb_usb.take_speaker_mic(self.adb, serial)
                    except Exception:
                        pass
                    adb_usb.usb_forward(self.adb, serial)
                    time.sleep(0.4)
                    if not self._session:
                        self._reviving = False
                        return
                    self.client.connect("127.0.0.1", protocol.PORT)
                    try:
                        self.client.connect_video("127.0.0.1", protocol.VIDEO_PORT)
                    except Exception:
                        pass
                    for toast_try in range(4):
                        if self.client.connect_toast("127.0.0.1", protocol.TOAST_PORT):
                            break
                        time.sleep(0.12 * (toast_try + 1))
                    if not self._session:
                        self.client.close()
                        self._reviving = False
                        return
                    self.root.after(0, self._on_revived)
                    return
                except Exception as exc:
                    last_err = str(exc)
                    n = attempt + 1
                    self.root.after(0, lambda e=last_err, n=n: self._log(f"拉起失败 ({n}/8): {e}"))
                    time.sleep(min(6.0, 0.45 * (2 ** attempt)))
            self.root.after(0, lambda: self._revive_gave_up(last_err))
        except Exception as exc:
            self.root.after(0, lambda e=str(exc): self._revive_gave_up(e))

    def _on_revived(self) -> None:
        self._reviving = False
        if not self._session:
            return
        self.connected = True
        self.headline.configure(text="USB 已连接")
        self.detail.configure(text="后台服务已恢复，音箱窗口无需打开。")
        self._log("已重新拉起音箱后台服务（未打开窗口）")
        try:
            if self.mic_enabled.get():
                if self.hw.running():
                    self.client.send_control("stop_mic")
                elif self.sink.running():
                    self.client.send_control("start_mic")
                else:
                    self._apply_mic_route()
            self._on_gain()
            self.client.send_control("gain", gain=round(self.sink.gain, 3))
            if self.volume_sync.get():
                self._push_pc_volume(force=True)
            self._spawn_stats(force=True)
            self._push_upside_down()
            self._begin_hud_reconcile()
        except Exception as exc:
            self._log("重连后恢复通路失败: " + str(exc))
        self._sync_toast_mirror()

    def _revive_gave_up(self, err: str) -> None:
        self._reviving = False
        self._session = False
        self.connected = False
        self.hw.stop(self.adb, self._serial)
        self.sink.stop()
        self._restore_render()
        self.mirror.stop()
        self._mirror_logged = False
        self.toast.stop()
        self._toast_logged = False
        if self.adb and self._serial:
            try:
                adb_usb.release_speaker_mic(self.adb, self._serial)
            except Exception:
                pass
        self.headline.configure(text="USB 已断开")
        self.detail.configure(text="多次拉起失败。请检查 USB，或在音箱上打开一次应用。")
        self._log("无法拉起后台服务: " + err)
        self._draw_meter("mic", 0)
        self._draw_meter("spk", 0)

    def _apply_mute_headline(self, mic_muted: bool, spk_muted: bool) -> None:
        if mic_muted and spk_muted:
            self.headline.configure(text="音箱麦克风和扬声器已静音")
        elif mic_muted:
            self.headline.configure(text="音箱麦克风已静音")
        elif spk_muted:
            self.headline.configure(text="音箱扬声器已静音")
        elif self.connected:
            if self.hw.running():
                self.headline.configure(text="正在把 LX04 硬件麦送给语音软件")
            else:
                self.headline.configure(text="正在把 LX04 麦克风送给语音软件")

    def _on_bridge_event(self, kind: str, data) -> None:
        if kind == "video_ack":
            self.mirror.note_ack()
            return
        if kind == "event":
            data = data if isinstance(data, dict) else {}
            cmd = str(data.get("cmd") or "")
            if cmd == "toast_ack":
                title = str(data.get("title") or "")
                if data.get("on"):
                    self._on_toast_log("音箱已显示弹窗" + (("「" + title + "」") if title else ""))
                else:
                    self._on_toast_log("音箱已退出弹窗页")
                return
            if cmd == "toast_dismiss":
                self._toast_logged = False
                try:
                    self.client.send_toast("toast_overlay", on=False)
                except Exception:
                    pass
                self.mirror.resume()
            self.toast.handle_event(data)
            return
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
            self._on_hud_status(data)
            self._on_hud_bg_status(data)
            if "screenMirror" in data:
                self._apply_mirror_request(bool(data.get("screenMirror")))
            if "volume" in data:
                try:
                    self._apply_speaker_volume(float(data.get("volume") or 0))
                except (TypeError, ValueError):
                    pass
            fallback = bool(data.get("muted"))
            mic_muted = bool(data["micMuted"]) if "micMuted" in data else fallback
            spk_muted = bool(data["spkMuted"]) if "spkMuted" in data else fallback
            self.loopback.muted = spk_muted
            if self.loopback.error:
                self._log("扬声器环回: " + self.loopback.error)
                self.loopback.error = ""
            if self.hw.running():
                self.hw.muted = mic_muted
                muted = "麦静音" if mic_muted else "拾音中"
                if spk_muted:
                    muted += " · 喇叭静音"
                usb = "USB" if data.get("usbConnected") else "USB断开"
                self.detail.configure(
                    text=f"{usb} · {muted} · 硬件麦 48kHz · 电平 {self.sink.peak:.2f} · 扬声器 {float(data.get('playLevel') or self.play_peak):.2f}"
                )
                self._apply_mute_headline(mic_muted, spk_muted)
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
            muted = "麦静音" if mic_muted else "拾音中"
            if spk_muted:
                muted += " · 喇叭静音"
            usb = "USB" if data.get("usbConnected") else "USB断开"
            self.detail.configure(
                text=f"{usb} · {muted} · 电平 {float(data.get('level') or 0):.2f} · 扬声器 {float(data.get('playLevel') or self.play_peak):.2f} · 丢帧 {data.get('dropped', 0)}"
            )
            self._apply_mute_headline(mic_muted, spk_muted)
            if self.sink.callback_error:
                self._log("音频回调: " + self.sink.callback_error)
                self.sink.callback_error = ""
        elif kind == "error":
            self._log("链路错误: " + str(data))
        elif kind == "disconnected":
            self.connected = False
            self.mirror.stop()
            self._mirror_logged = False
            self.toast.stop()
            self._toast_logged = False
            self._draw_meter("mic", 0)
            self._draw_meter("spk", 0)
            if not self._session:
                return
            if self._reviving:
                return
            self.headline.configure(text="音箱后台被杀，正在拉起…")
            self.detail.configure(text="不用打开音箱窗口，电脑会自动重启服务。")
            self._log("与音箱 TCP 断开，尝试无窗口拉起后台服务")
            self._begin_revive()

    def _tick(self) -> None:
        if self._closing:
            return
        if _poll_activate_event():
            try:
                _show_host_window(self.root.window)
                self._log("已切换到正在运行的上位机")
            except Exception:
                pass
        spk = self.loopback.peak if self.loopback.running() else self.play_peak
        self._draw_meter("mic", self.sink.peak if self.connected else 0)
        self._draw_meter("spk", spk if self.connected else 0)
        if not self.loopback.running():
            self.play_peak *= 0.82
        self._push_pc_volume()
        self._stats_ticks += 1
        if self._stats_ticks >= 12:
            self._stats_ticks = 0
            self._spawn_stats()
        if self.mirror.error:
            self._log("屏幕镜像: " + self.mirror.error)
            self.mirror.error = ""
        if self.mirror.running() and self.mirror.frames and not self._mirror_logged:
            self._mirror_logged = True
            self._log("屏幕镜像已出画面: " + (self.mirror.title or self.monitor_var.get()))
        if self.toast.error:
            self._log("系统弹窗: " + self.toast.error)
            self.toast.error = ""
        if self._tray_hwnd and time.monotonic() - self._tray_ping_at > 3:
            self._tray_ping_at = time.monotonic()
            self._tray_ping()
        try:
            self.root.after(80, self._tick)
        except Exception:
            return

    def _draw_meter(self, which: str, level: float) -> None:
        if which == "mic":
            self.bridge.set_levels(level, self.bridge._spk_level)
        else:
            self.bridge.set_levels(self.bridge._mic_level, level)

    def _log(self, line: str) -> None:
        if self._closing:
            return
        if threading.current_thread() is not threading.main_thread():
            self._ui(lambda l=line: self._log(l))
            return
        self.log.insert("end", line + "\n")
        self.log.see("end")


def _autostart_command() -> str:
    exe = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    return f'"{exe}" "{Path(__file__).resolve()}"'


def _autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _typ = winreg.QueryValueEx(key, _RUN_NAME)
        return bool(str(value or "").strip())
    except OSError:
        return False


def _set_autostart(on: bool) -> None:
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY)
    try:
        if on:
            winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, _RUN_NAME)
            except FileNotFoundError:
                pass
    finally:
        key.Close()


def _close_goes_to_tray(closing: bool, force: bool, enabled: bool) -> bool:
    return (not force) and (not closing) and enabled


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
    if not _claim_single_instance():
        _activate_running_host()
        return
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    apply_fluent_style()
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName("LX04 PC Bridge")
    loop = QtLoop()
    bridge = HostBridge()
    host = HostApp(loop, bridge)
    bridge.bind(host)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("host", bridge)
    qml = qml_dir() / "Main.qml"
    engine.load(str(qml))
    if not engine.rootObjects():
        print("QML load failed:", qml)
        return
    window = engine.rootObjects()[0]
    loop.window = window
    # HostApp._on_close is wired from QML onClosing via HostBridge.onWindowClosing
    screen = qapp.primaryScreen()
    geo = screen.availableGeometry()
    m = _ui_metrics(geo.width(), geo.height(), screen.logicalDotsPerInch())
    window.setWidth(int(m["w"]))
    window.setHeight(int(m["h"]))
    host._boot_ui()
    loop.after(400, host._tick)
    raise SystemExit(qapp.exec())


if __name__ == "__main__":
    main()
