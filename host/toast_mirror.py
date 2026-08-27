"""Capture Windows toast / bottom-right popups and click them from the LX04."""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

import screen_mirror
from screen_mirror import TARGET_H, TARGET_W, _Grabber, letterbox

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ole32 = ctypes.oledll.ole32
try:
    dwmapi = ctypes.WinDLL("dwmapi")
except OSError:
    dwmapi = None

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(screen_mirror.RECT)]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.MonitorFromRect.argtypes = [ctypes.POINTER(screen_mirror.RECT), wintypes.DWORD]
user32.MonitorFromRect.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(screen_mirror.MONITORINFOEXW)]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
if dwmapi is not None:
    dwmapi.DwmGetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    ]

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTONEAREST = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
WM_CLOSE = 0x0010
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
COINIT_MULTITHREADED = 0
PAD_PX = 10
POLL_IDLE_S = 0.12
POLL_LIVE_S = 0.055
ACK_WAIT_S = 0.28
JPEG_QUALITY = 52
JPEG_QUALITY_SMALL = 36
MAX_JPEG = 72 * 1024

SKIP_CLASSES = {
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow",
    "Progman",
    "WorkerW",
    "ForegroundStaging",
    "IME",
    "MSCTFIME UI",
    "tooltips_class32",
    "#32768",
    "#32769",
    "DummyDWMListenerWindow",
    "TaskListOverlayWnd",
    "TaskListThumbnailWnd",
    "Windows.Internal.Shell.TabProxyWindow",
    "EdgeUiInputTopWndClass",
    "ApplicationManager_DesktopShellWindow",
    "Windows.UI.Input.InputSite.WindowClass",
}
TOAST_CLASSES = {
    "Windows.UI.Core.CoreWindow",
    "Windows.UI.Composition.DesktopWindowContentBridge",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
    "Microsoft.UI.Content.DesktopChildSiteBridge",
    "Xaml_WindowedPopupClass",
    "NativeHWNDHost",
    "ApplicationFrameWindow",
}
TOAST_TITLES = {
    "new notification",
    "new notifications",
    "notification",
    "notifications",
    "新通知",
    "通知",
}
TOAST_PROCESSES = {
    "explorer.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "cursor.exe",
    "code.exe",
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


@dataclass
class ToastHit:
    hwnds: tuple[int, ...]
    left: int
    top: int
    width: int
    height: int
    title: str


@dataclass
class ToastMap:
    src_left: int
    src_top: int
    src_w: int
    src_h: int
    dst_x: int
    dst_y: int
    dst_w: int
    dst_h: int
    hwnds: tuple[int, ...]


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    n = user32.GetClassNameW(hwnd, buf, 256)
    return buf.value if n else ""


def _title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    n = user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value if n else ""


def _cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    value = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value))
    return hr == 0 and value.value != 0


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def _virtual_screen() -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = max(1, int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)))
    height = max(1, int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)))
    return left, top, width, height


def _work_area(rect: screen_mirror.RECT) -> screen_mirror.RECT | None:
    hmon = user32.MonitorFromRect(ctypes.byref(rect), MONITOR_DEFAULTTONEAREST)
    if not hmon:
        return None
    info = screen_mirror.MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(screen_mirror.MONITORINFOEXW)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    return info.rcWork


def _in_toast_dock(left: int, top: int, right: int, bottom: int, work: screen_mirror.RECT) -> bool:
    work_w = max(1, int(work.right - work.left))
    work_h = max(1, int(work.bottom - work.top))
    dock_left = int(work.right) - min(520, int(work_w * 0.46))
    dock_top = int(work.bottom) - min(640, int(work_h * 0.62))
    overlap_w = min(right, int(work.right)) - max(left, dock_left)
    overlap_h = min(bottom, int(work.bottom)) - max(top, dock_top)
    if overlap_w <= 8 or overlap_h <= 8:
        return False
    margin_r = int(work.right) - right
    margin_b = int(work.bottom) - bottom
    return margin_r <= 96 and margin_b <= 96


def _looks_like_toast(
    class_name: str,
    title: str,
    width: int,
    height: int,
    work: screen_mirror.RECT,
    ex_style: int,
    proc: str,
) -> bool:
    work_w = max(1, int(work.right - work.left))
    work_h = max(1, int(work.bottom - work.top))
    if width < 160 or height < 48:
        return False
    if width > min(720, int(work_w * 0.55)) or height > min(560, int(work_h * 0.58)):
        return False
    title_l = title.strip().lower()
    if title_l in TOAST_TITLES:
        return True
    if class_name in TOAST_CLASSES:
        return True
    if proc in TOAST_PROCESSES and (ex_style & WS_EX_TOPMOST or class_name.startswith("Chrome_WidgetWin_")):
        return True
    if class_name.startswith("Chrome_WidgetWin_") and (ex_style & (WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)):
        return True
    return bool(ex_style & WS_EX_TOPMOST) and proc in TOAST_PROCESSES


def find_toasts() -> ToastHit | None:
    screen_mirror._thread_dpi()
    found: list[tuple[int, int, int, int, int, str]] = []
    our_pid = os.getpid()

    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or _cloaked(hwnd):
            return 1
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) == our_pid:
            return 1
        class_name = _class_name(hwnd)
        if class_name in SKIP_CLASSES:
            return 1
        rect = screen_mirror.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return 1
        left, top, right, bottom = int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
        width, height = right - left, bottom - top
        work = _work_area(rect)
        if work is None:
            return 1
        if not _in_toast_dock(left, top, right, bottom, work):
            return 1
        style = int(user32.GetWindowLongW(hwnd, GWL_STYLE) or 0)
        ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0)
        if ex_style & WS_EX_TRANSPARENT:
            return 1
        if not (style & WS_VISIBLE):
            return 1
        proc = _process_name(int(pid.value))
        title = _title(hwnd)
        if not _looks_like_toast(class_name, title, width, height, work, ex_style, proc):
            return 1
        found.append((int(hwnd), left, top, right, bottom, title or class_name or proc))
        return 1

    cb = WNDENUMPROC(_enum)
    user32.EnumWindows(cb, 0)
    if not found:
        return None
    left = min(item[1] for item in found)
    top = min(item[2] for item in found)
    right = max(item[3] for item in found)
    bottom = max(item[4] for item in found)
    vs_l, vs_t, vs_w, vs_h = _virtual_screen()
    left = max(vs_l, left - PAD_PX)
    top = max(vs_t, top - PAD_PX)
    right = min(vs_l + vs_w, right + PAD_PX)
    bottom = min(vs_t + vs_h, bottom + PAD_PX)
    width = max(1, right - left)
    height = max(1, bottom - top)
    title = found[0][5]
    for item in found:
        low = item[5].strip().lower()
        if low in TOAST_TITLES or "cursor" in low:
            title = item[5]
            break
    return ToastHit(tuple(item[0] for item in found), left, top, width, height, title)


def _send_mouse(flags: int, x: int | None = None, y: int | None = None) -> None:
    inp = INPUT()
    inp.type = INPUT_MOUSE
    if x is not None and y is not None:
        vs_l, vs_t, vs_w, vs_h = _virtual_screen()
        inp.mi.dx = int(round((x - vs_l) * 65535 / max(1, vs_w)))
        inp.mi.dy = int(round((y - vs_t) * 65535 / max(1, vs_h)))
        inp.mi.dwFlags = flags | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    else:
        inp.mi.dwFlags = flags
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def click_screen(x: float, y: float, down: bool = False, up: bool = False) -> None:
    screen_mirror._thread_dpi()
    px, py = int(round(x)), int(round(y))
    user32.SetCursorPos(px, py)
    _send_mouse(MOUSEEVENTF_MOVE, px, py)
    if down:
        _send_mouse(MOUSEEVENTF_LEFTDOWN)
    if up:
        _send_mouse(MOUSEEVENTF_LEFTUP)


def dismiss_toasts(hwnds: tuple[int, ...]) -> None:
    for hwnd in hwnds:
        if hwnd and user32.IsWindow(hwnd):
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


class ToastSender:
    def __init__(self, send_jpeg, on_change=None) -> None:
        self._send_jpeg = send_jpeg
        self.on_change = on_change
        self._alive = False
        self._showing = False
        self._thread: threading.Thread | None = None
        self._ack = threading.Event()
        self._lock = threading.Lock()
        self._map: ToastMap | None = None
        self._cursor: wintypes.POINT | None = None
        self._press_at: tuple[float, float] | None = None
        self.title = ""
        self.error = ""
        self.frames = 0

    def running(self) -> bool:
        return self._alive

    def showing(self) -> bool:
        return self._alive and self._showing

    def start(self) -> None:
        if self._alive:
            return
        self.error = ""
        self.frames = 0
        self._showing = False
        self._alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="lx04-toast")
        self._thread.start()

    def stop(self) -> None:
        was_showing = self._showing
        self._alive = False
        self._showing = False
        self._ack.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        with self._lock:
            self._map = None
        if was_showing:
            self._emit(False, "")

    def note_ack(self) -> None:
        self._ack.set()

    def handle_pointer(self, data: dict) -> None:
        if not self._showing:
            return
        try:
            nx = float(data.get("x") or 0)
            ny = float(data.get("y") or 0)
        except (TypeError, ValueError):
            return
        act = str(data.get("act") or "")
        with self._lock:
            mapping = self._map
            hwnds = mapping.hwnds if mapping is not None else ()
        px = nx * TARGET_W
        py = ny * TARGET_H
        inside = mapping is not None and _inside_dest(px, py, mapping)
        sx = sy = 0.0
        if inside and mapping is not None:
            sx = mapping.src_left + (px - mapping.dst_x) / max(1, mapping.dst_w) * mapping.src_w
            sy = mapping.src_top + (py - mapping.dst_y) / max(1, mapping.dst_h) * mapping.src_h
        if act == "down":
            if not inside:
                return
            self._remember_cursor()
            self._press_at = (sx, sy)
            click_screen(sx, sy, down=True, up=False)
            return
        if act == "up":
            if inside:
                click_screen(sx, sy, down=False, up=True)
            elif self._press_at is not None:
                click_screen(self._press_at[0], self._press_at[1], down=False, up=True)
            self._press_at = None
            self._restore_cursor()
            if not inside:
                dismiss_toasts(hwnds)
            return
        if act == "cancel":
            if self._press_at is not None:
                click_screen(self._press_at[0], self._press_at[1], down=False, up=True)
            self._press_at = None
            self._restore_cursor()

    def _remember_cursor(self) -> None:
        screen_mirror._thread_dpi()
        pt = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            self._cursor = pt
        else:
            self._cursor = None

    def _restore_cursor(self) -> None:
        pt = self._cursor
        self._cursor = None
        if pt is not None:
            user32.SetCursorPos(int(pt.x), int(pt.y))

    def _emit(self, showing: bool, title: str) -> None:
        cb = self.on_change
        if cb is not None:
            try:
                cb(showing, title)
            except Exception:
                pass

    def _loop(self) -> None:
        try:
            ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        except Exception:
            pass
        screen_mirror._thread_dpi()
        grabber = _Grabber()
        try:
            while self._alive:
                started = time.monotonic()
                try:
                    hit = find_toasts()
                except Exception as exc:
                    self.error = str(exc)
                    hit = None
                if hit is None:
                    if self._showing:
                        if self._press_at is not None:
                            click_screen(self._press_at[0], self._press_at[1], down=False, up=True)
                            self._press_at = None
                            self._restore_cursor()
                        self._showing = False
                        with self._lock:
                            self._map = None
                        self._emit(False, "")
                    remain = POLL_IDLE_S - (time.monotonic() - started)
                    if remain > 0 and self._alive:
                        time.sleep(remain)
                    continue
                dest = letterbox(hit.width, hit.height)
                mapping = ToastMap(
                    src_left=hit.left,
                    src_top=hit.top,
                    src_w=hit.width,
                    src_h=hit.height,
                    dst_x=dest[0],
                    dst_y=dest[1],
                    dst_w=dest[2],
                    dst_h=dest[3],
                    hwnds=hit.hwnds,
                )
                with self._lock:
                    self._map = mapping
                self.title = hit.title
                if not self._showing:
                    self._showing = True
                    self._emit(True, hit.title)
                try:
                    jpeg = grabber.grab_region(
                        hit.left, hit.top, hit.width, hit.height,
                        quality=JPEG_QUALITY,
                        max_jpeg=MAX_JPEG,
                        quality_small=JPEG_QUALITY_SMALL,
                    )
                except Exception as exc:
                    self.error = str(exc)
                    grabber.close()
                    time.sleep(0.25)
                    continue
                if not self._alive or not jpeg:
                    continue
                self._ack.clear()
                try:
                    self._send_jpeg(jpeg)
                    self.frames += 1
                except Exception as exc:
                    self.error = str(exc)
                if self._alive:
                    self._ack.wait(timeout=ACK_WAIT_S)
                remain = POLL_LIVE_S - (time.monotonic() - started)
                if remain > 0 and self._alive:
                    time.sleep(remain)
        finally:
            grabber.close()
            try:
                ole32.CoUninitialize()
            except Exception:
                pass


def _inside_dest(px: float, py: float, mapping: ToastMap) -> bool:
    return (
        mapping.dst_x <= px <= mapping.dst_x + mapping.dst_w
        and mapping.dst_y <= py <= mapping.dst_y + mapping.dst_h
    )
