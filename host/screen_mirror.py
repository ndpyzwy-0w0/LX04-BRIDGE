"""Capture a chosen Windows monitor as 800x480 JPEG for the LX04 screen."""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

SRCCOPY = 0x00CC0020
COLORONCOLOR = 3
MONITORINFOF_PRIMARY = 1
CCHDEVICENAME = 32
ENCODER_PARAMETER_LONG = 4
JPEG_QUALITY = 16
JPEG_QUALITY_SMALL = 12
MAX_JPEG = 28 * 1024
TARGET_W = 800
TARGET_H = 480
FRAME_INTERVAL = 0.07
FRAME_INTERVAL_SLOW = 0.14
MONITOR_REFRESH = 2.0
GRABBER_REOPEN_FRAMES = 400
ACK_WAIT_S = 0.12

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
gdiplus = ctypes.WinDLL("gdiplus")
ole32 = ctypes.oledll.ole32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * CCHDEVICENAME),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class EncoderParameter(ctypes.Structure):
    _fields_ = [
        ("Guid", GUID),
        ("NumberOfValues", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("Value", ctypes.c_void_p),
    ]


class EncoderParameters(ctypes.Structure):
    _fields_ = [
        ("Count", ctypes.c_uint),
        ("Parameter", EncoderParameter * 1),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", ctypes.c_int),
        ("SuppressExternalCodecs", ctypes.c_int),
    ]


JPEG_CLSID = GUID()
JPEG_CLSID.Data1 = 0x557CF401
JPEG_CLSID.Data2 = 0x1A04
JPEG_CLSID.Data3 = 0x11D3
JPEG_CLSID.Data4[:] = (0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E)

ENCODER_QUALITY = GUID()
ENCODER_QUALITY.Data1 = 0x1D5BE4B5
ENCODER_QUALITY.Data2 = 0xFA4A
ENCODER_QUALITY.Data3 = 0x452D
ENCODER_QUALITY.Data4[:] = (0x9C, 0xDD, 0x5D, 0xB3, 0x51, 0x05, 0xE7, 0xEB)

MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(RECT),
    wintypes.LPARAM,
)

try:
    user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
except AttributeError:
    pass
user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MONITORENUMPROC, wintypes.LPARAM]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
]
gdi32.StretchBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
]
gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]

gdiplus.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
gdiplus.GdipCreateBitmapFromHBITMAP.argtypes = [wintypes.HBITMAP, wintypes.HPALETTE, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
gdiplus.GdipSaveImageToStream.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_void_p,
]
ole32.CreateStreamOnHGlobal.argtypes = [wintypes.HGLOBAL, wintypes.BOOL, ctypes.POINTER(ctypes.c_void_p)]
ole32.GetHGlobalFromStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HGLOBAL)]
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint]
ole32.CoUninitialize.argtypes = []
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

STREAM_SEEK_SET = 0
STATFLAG_NONAME = 1
COINIT_MULTITHREADED = 0


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class STATSTG(ctypes.Structure):
    _fields_ = [
        ("pwcsName", ctypes.c_void_p),
        ("type", wintypes.DWORD),
        ("cbSize", ctypes.c_uint64),
        ("mtime", FILETIME),
        ("ctime", FILETIME),
        ("atime", FILETIME),
        ("grfMode", wintypes.DWORD),
        ("grfLocksSupported", wintypes.DWORD),
        ("clsid", GUID),
        ("grfStateBits", wintypes.DWORD),
        ("reserved", wintypes.DWORD),
    ]


def _com_vtbl(ptr) -> ctypes.POINTER(ctypes.c_void_p):
    return ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents


def _istream_release(ptr) -> None:
    fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(_com_vtbl(ptr)[2])
    fn(ptr)


def _istream_seek0(ptr) -> None:
    fn = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.c_int64,
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_uint64),
    )(_com_vtbl(ptr)[5])
    pos = ctypes.c_uint64()
    hr = fn(ptr, 0, STREAM_SEEK_SET, ctypes.byref(pos))
    if hr != 0:
        raise RuntimeError("JPEG 流定位失败")


def _istream_setsize(ptr, size: int) -> None:
    fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint64)(_com_vtbl(ptr)[6])
    hr = fn(ptr, size)
    if hr != 0:
        raise RuntimeError("JPEG 流重置失败")


def _istream_size(ptr) -> int:
    fn = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.POINTER(STATSTG),
        ctypes.c_uint,
    )(_com_vtbl(ptr)[12])
    st = STATSTG()
    hr = fn(ptr, ctypes.byref(st), STATFLAG_NONAME)
    if hr != 0:
        raise RuntimeError("JPEG 流长度失败")
    return int(st.cbSize)


def _new_istream() -> ctypes.c_void_p:
    stream = ctypes.c_void_p()
    hr = ole32.CreateStreamOnHGlobal(None, True, ctypes.byref(stream))
    if hr != 0 or not stream:
        raise RuntimeError("无法写入 JPEG")
    return stream


_gdiplus_token = ctypes.c_ulong(0)
_gdiplus_ready = False
_gdiplus_lock = threading.Lock()


def _thread_dpi() -> None:
    """Per-monitor DPI for capture threads only. Never call this on the Tk UI thread:
    changing awareness after Tk() creates a window detaches the frame from the widgets."""
    try:
        user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception:
        pass


def _ensure_gdiplus() -> None:
    global _gdiplus_ready
    with _gdiplus_lock:
        if _gdiplus_ready:
            return
        startup = GdiplusStartupInput()
        startup.GdiplusVersion = 1
        status = gdiplus.GdiplusStartup(ctypes.byref(_gdiplus_token), ctypes.byref(startup), None)
        if status != 0:
            raise RuntimeError("GDI+ 启动失败: " + str(status))
        _gdiplus_ready = True


@dataclass
class Monitor:
    key: str
    index: int
    left: int
    top: int
    width: int
    height: int
    primary: bool

    def label(self) -> str:
        tag = "  主屏" if self.primary else ""
        return f"{self.index}  {self.width}×{self.height}{tag}"


def _enum_monitors() -> list[Monitor]:
    found: list[Monitor] = []

    def _enum(hmon, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return 1
        rect = info.rcMonitor
        found.append(
            Monitor(
                key=info.szDevice,
                index=len(found) + 1,
                left=int(rect.left),
                top=int(rect.top),
                width=max(1, int(rect.right - rect.left)),
                height=max(1, int(rect.bottom - rect.top)),
                primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            )
        )
        return 1

    cb = MONITORENUMPROC(_enum)
    user32.EnumDisplayMonitors(None, None, cb, 0)
    found.sort(key=lambda item: (not item.primary, item.left, item.top, item.key))
    for index, item in enumerate(found, start=1):
        item.index = index
    return found


def list_monitors() -> list[Monitor]:
    if threading.current_thread() is not threading.main_thread():
        _thread_dpi()
        return _enum_monitors()
    box: list[object] = []

    def worker() -> None:
        try:
            _thread_dpi()
            box.append(_enum_monitors())
        except BaseException as exc:
            box.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=2.0)
    if not box:
        return []
    if isinstance(box[0], BaseException):
        raise box[0]
    return list(box[0])  # type: ignore[arg-type]


def pick_monitor(monitors: list[Monitor], saved_key: str = "") -> Monitor | None:
    if not monitors:
        return None
    if saved_key:
        for item in monitors:
            if item.key == saved_key:
                return item
        for item in monitors:
            if item.label() == saved_key:
                return item
    for item in monitors:
        if item.primary:
            return item
    return monitors[0]


def capture_jpeg(monitor: Monitor, quality: int = JPEG_QUALITY) -> bytes:
    grabber = _Grabber()
    try:
        return grabber.grab(monitor, quality)
    finally:
        grabber.close()


def capture_jpeg_fit(monitor: Monitor) -> bytes:
    grabber = _Grabber()
    try:
        return grabber.grab(monitor)
    finally:
        grabber.close()


class _Grabber:
    def __init__(self) -> None:
        self.src_dc = None
        self.dst_dc = None
        self.bmp = None
        self.old = None
        self.brush = None
        self.stream = None
        self.frames = 0

    def open(self) -> None:
        _ensure_gdiplus()
        self.src_dc = user32.GetDC(None)
        if not self.src_dc:
            raise RuntimeError("无法读取屏幕")
        self.dst_dc = gdi32.CreateCompatibleDC(self.src_dc)
        self.bmp = gdi32.CreateCompatibleBitmap(self.src_dc, TARGET_W, TARGET_H)
        self.old = gdi32.SelectObject(self.dst_dc, self.bmp)
        self.brush = gdi32.CreateSolidBrush(0x000000)
        gdi32.SetStretchBltMode(self.dst_dc, COLORONCOLOR)
        self.stream = _new_istream()

    def grab(self, monitor: Monitor, quality: int | None = None) -> bytes:
        if not self.dst_dc or self.frames >= GRABBER_REOPEN_FRAMES:
            self.close()
            self.open()
        fill = RECT(0, 0, TARGET_W, TARGET_H)
        user32.FillRect(self.dst_dc, ctypes.byref(fill), self.brush)
        scale = min(TARGET_W / monitor.width, TARGET_H / monitor.height)
        dest_w = max(1, int(monitor.width * scale))
        dest_h = max(1, int(monitor.height * scale))
        dest_x = (TARGET_W - dest_w) // 2
        dest_y = (TARGET_H - dest_h) // 2
        ok = gdi32.StretchBlt(
            self.dst_dc, dest_x, dest_y, dest_w, dest_h,
            self.src_dc, monitor.left, monitor.top, monitor.width, monitor.height,
            SRCCOPY,
        )
        if not ok:
            self.close()
            self.open()
            ok = gdi32.StretchBlt(
                self.dst_dc, dest_x, dest_y, dest_w, dest_h,
                self.src_dc, monitor.left, monitor.top, monitor.width, monitor.height,
                SRCCOPY,
            )
        if not ok:
            raise RuntimeError("截取屏幕失败")
        q = JPEG_QUALITY if quality is None else quality
        data = self._encode(q)
        if quality is None and len(data) > MAX_JPEG:
            data = self._encode(JPEG_QUALITY_SMALL)
        self.frames += 1
        return data

    def _encode(self, quality: int) -> bytes:
        if not self.stream:
            self.stream = _new_istream()
        try:
            _istream_setsize(self.stream, 0)
            _istream_seek0(self.stream)
            return _hbitmap_to_jpeg(self.bmp, quality, self.stream)
        except Exception:
            if self.stream:
                try:
                    _istream_release(self.stream)
                except Exception:
                    pass
            self.stream = _new_istream()
            return _hbitmap_to_jpeg(self.bmp, quality, self.stream)

    def close(self) -> None:
        if self.stream:
            try:
                _istream_release(self.stream)
            except Exception:
                pass
            self.stream = None
        if self.dst_dc and self.old:
            gdi32.SelectObject(self.dst_dc, self.old)
        if self.brush:
            gdi32.DeleteObject(self.brush)
        if self.bmp:
            gdi32.DeleteObject(self.bmp)
        if self.dst_dc:
            gdi32.DeleteDC(self.dst_dc)
        if self.src_dc:
            user32.ReleaseDC(None, self.src_dc)
        self.src_dc = self.dst_dc = self.bmp = self.old = self.brush = None
        self.frames = 0


def _hbitmap_to_jpeg(hbitmap, quality: int, stream) -> bytes:
    image = ctypes.c_void_p()
    status = gdiplus.GdipCreateBitmapFromHBITMAP(hbitmap, None, ctypes.byref(image))
    if status != 0 or not image:
        raise RuntimeError("无法编码屏幕画面")
    quality_value = ctypes.c_uint32(max(15, min(80, int(quality))))
    params = EncoderParameters()
    params.Count = 1
    params.Parameter[0].Guid = ENCODER_QUALITY
    params.Parameter[0].NumberOfValues = 1
    params.Parameter[0].Type = ENCODER_PARAMETER_LONG
    params.Parameter[0].Value = ctypes.cast(ctypes.byref(quality_value), ctypes.c_void_p)
    try:
        status = gdiplus.GdipSaveImageToStream(
            image, stream, ctypes.byref(JPEG_CLSID), ctypes.byref(params)
        )
        if status != 0:
            raise RuntimeError("JPEG 编码失败: " + str(status))
        hglobal = wintypes.HGLOBAL()
        hr = ole32.GetHGlobalFromStream(stream, ctypes.byref(hglobal))
        if hr != 0 or not hglobal:
            raise RuntimeError("无法读取 JPEG")
        try:
            size = _istream_size(stream)
        except Exception:
            size = int(kernel32.GlobalSize(hglobal))
        alloc = int(kernel32.GlobalSize(hglobal))
        if size <= 0 or alloc <= 0:
            raise RuntimeError("JPEG 为空")
        size = min(size, alloc)
        ptr = kernel32.GlobalLock(hglobal)
        if not ptr:
            raise RuntimeError("JPEG 为空")
        try:
            data = ctypes.string_at(ptr, size)
        finally:
            kernel32.GlobalUnlock(hglobal)
        if len(data) < 24 or data[:2] != b"\xff\xd8":
            raise RuntimeError("JPEG 损坏")
        return data
    finally:
        gdiplus.GdipDisposeImage(image)


class ScreenSender:
    def __init__(self, send_jpeg) -> None:
        self._send_jpeg = send_jpeg
        self._alive = False
        self._capture_thread: threading.Thread | None = None
        self._send_thread: threading.Thread | None = None
        self._slot = threading.Lock()
        self._latest: bytes | None = None
        self._latest_at = 0.0
        self._new_frame = threading.Event()
        self._ack = threading.Event()
        self._send_s = FRAME_INTERVAL
        self.monitor_key = ""
        self.title = ""
        self.error = ""
        self.frames = 0

    def running(self) -> bool:
        return self._alive

    def start(self, monitor_key: str) -> Monitor | None:
        self.stop()
        chosen = pick_monitor(list_monitors(), monitor_key)
        if chosen is None:
            self.error = "没有可用的显示器"
            return None
        self.monitor_key = chosen.key
        self.title = chosen.label()
        self.error = ""
        self.frames = 0
        self._send_s = FRAME_INTERVAL
        with self._slot:
            self._latest = None
            self._latest_at = 0.0
        self._new_frame.clear()
        self._ack.clear()
        self._alive = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, args=(chosen.key,), daemon=True, name="lx04-mirror-cap"
        )
        self._send_thread = threading.Thread(
            target=self._send_loop, daemon=True, name="lx04-mirror-send"
        )
        self._capture_thread.start()
        self._send_thread.start()
        return chosen

    def stop(self) -> None:
        self._alive = False
        self._ack.set()
        self._new_frame.set()
        threads = [self._capture_thread, self._send_thread]
        self._capture_thread = None
        self._send_thread = None
        with self._slot:
            self._latest = None
        for thread in threads:
            if thread is not None and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def note_ack(self) -> None:
        self._ack.set()

    def _put(self, jpeg: bytes) -> None:
        with self._slot:
            self._latest = jpeg
            self._latest_at = time.monotonic()
        self._new_frame.set()

    def _take(self) -> tuple[bytes | None, float]:
        with self._slot:
            jpeg = self._latest
            at = self._latest_at
            self._latest = None
            return jpeg, at

    def _capture_loop(self, key: str) -> None:
        try:
            ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        except Exception:
            pass
        _thread_dpi()
        grabber = _Grabber()
        chosen: Monitor | None = None
        last_enum = 0.0
        try:
            while self._alive:
                started = time.monotonic()
                with self._slot:
                    waiting = self._latest is not None
                if waiting:
                    time.sleep(0.004)
                    continue
                try:
                    if chosen is None or started - last_enum >= MONITOR_REFRESH:
                        chosen = pick_monitor(_enum_monitors(), key)
                        last_enum = started
                        if chosen is not None:
                            self.title = chosen.label()
                    if chosen is None:
                        raise RuntimeError("显示器已断开")
                    quality = JPEG_QUALITY_SMALL if self._send_s > 0.08 else None
                    jpeg = grabber.grab(chosen, quality)
                    if self._alive and jpeg:
                        self._put(jpeg)
                        self.frames += 1
                except Exception as exc:
                    self.error = str(exc)
                    grabber.close()
                    time.sleep(0.4)
                    continue
                interval = min(FRAME_INTERVAL_SLOW, max(FRAME_INTERVAL, self._send_s * 1.4))
                remain = interval - (time.monotonic() - started)
                if remain > 0:
                    time.sleep(remain)
        finally:
            grabber.close()
            try:
                ole32.CoUninitialize()
            except Exception:
                pass

    def _send_loop(self) -> None:
        while self._alive:
            self._new_frame.wait(timeout=0.2)
            self._new_frame.clear()
            jpeg, _captured_at = self._take()
            if not jpeg or not self._alive:
                continue
            newer, _newer_at = self._take()
            if newer is not None:
                jpeg = newer
            self._ack.clear()
            t0 = time.monotonic()
            try:
                self._send_jpeg(jpeg)
            except Exception as exc:
                self.error = str(exc)
            if self._alive:
                self._ack.wait(timeout=ACK_WAIT_S)
            self._send_s = self._send_s * 0.65 + (time.monotonic() - t0) * 0.35
