"""Capture a chosen Windows monitor as 800x480 JPEG for the LX04 screen."""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass

SRCCOPY = 0x00CC0020
HALFTONE = 4
CAPTUREBLT = 0x40000000
MONITORINFOF_PRIMARY = 1
CCHDEVICENAME = 32
ENCODER_PARAMETER_LONG = 4
JPEG_QUALITY = 42
JPEG_QUALITY_SMALL = 28
MAX_JPEG = 96 * 1024
TARGET_W = 800
TARGET_H = 480
FRAME_INTERVAL = 0.10

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
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

_gdiplus_token = ctypes.c_ulong(0)
_gdiplus_ready = False
_gdiplus_lock = threading.Lock()


def _thread_dpi() -> None:
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


def list_monitors() -> list[Monitor]:
    _thread_dpi()
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
    _thread_dpi()
    _ensure_gdiplus()
    src_dc = user32.GetDC(None)
    if not src_dc:
        raise RuntimeError("无法读取屏幕")
    dst_dc = gdi32.CreateCompatibleDC(src_dc)
    bmp = gdi32.CreateCompatibleBitmap(src_dc, TARGET_W, TARGET_H)
    old = gdi32.SelectObject(dst_dc, bmp)
    brush = gdi32.CreateSolidBrush(0x000000)
    try:
        fill = RECT(0, 0, TARGET_W, TARGET_H)
        user32.FillRect(dst_dc, ctypes.byref(fill), brush)
        scale = min(TARGET_W / monitor.width, TARGET_H / monitor.height)
        dest_w = max(1, int(monitor.width * scale))
        dest_h = max(1, int(monitor.height * scale))
        dest_x = (TARGET_W - dest_w) // 2
        dest_y = (TARGET_H - dest_h) // 2
        gdi32.SetStretchBltMode(dst_dc, HALFTONE)
        gdi32.SetBrushOrgEx(dst_dc, 0, 0, None)
        ok = gdi32.StretchBlt(
            dst_dc, dest_x, dest_y, dest_w, dest_h,
            src_dc, monitor.left, monitor.top, monitor.width, monitor.height,
            SRCCOPY | CAPTUREBLT,
        )
        if not ok:
            ok = gdi32.StretchBlt(
                dst_dc, dest_x, dest_y, dest_w, dest_h,
                src_dc, monitor.left, monitor.top, monitor.width, monitor.height,
                SRCCOPY,
            )
        if not ok:
            raise RuntimeError("截取屏幕失败")
        return _hbitmap_to_jpeg(bmp, quality)
    finally:
        gdi32.SelectObject(dst_dc, old)
        gdi32.DeleteObject(brush)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(dst_dc)
        user32.ReleaseDC(None, src_dc)


def capture_jpeg_fit(monitor: Monitor) -> bytes:
    data = capture_jpeg(monitor, JPEG_QUALITY)
    if len(data) > MAX_JPEG:
        data = capture_jpeg(monitor, JPEG_QUALITY_SMALL)
    return data


def _hbitmap_to_jpeg(hbitmap, quality: int) -> bytes:
    image = ctypes.c_void_p()
    status = gdiplus.GdipCreateBitmapFromHBITMAP(hbitmap, None, ctypes.byref(image))
    if status != 0 or not image:
        raise RuntimeError("无法编码屏幕画面")
    stream = ctypes.c_void_p()
    quality_value = ctypes.c_uint32(max(15, min(80, int(quality))))
    params = EncoderParameters()
    params.Count = 1
    params.Parameter[0].Guid = ENCODER_QUALITY
    params.Parameter[0].NumberOfValues = 1
    params.Parameter[0].Type = ENCODER_PARAMETER_LONG
    params.Parameter[0].Value = ctypes.cast(ctypes.byref(quality_value), ctypes.c_void_p)
    try:
        hr = ole32.CreateStreamOnHGlobal(None, True, ctypes.byref(stream))
        if hr != 0 or not stream:
            raise RuntimeError("无法写入 JPEG")
        status = gdiplus.GdipSaveImageToStream(
            image, stream, ctypes.byref(JPEG_CLSID), ctypes.byref(params)
        )
        if status != 0:
            raise RuntimeError("JPEG 编码失败: " + str(status))
        hglobal = wintypes.HGLOBAL()
        hr = ole32.GetHGlobalFromStream(stream, ctypes.byref(hglobal))
        if hr != 0 or not hglobal:
            raise RuntimeError("无法读取 JPEG")
        size = int(kernel32.GlobalSize(hglobal))
        ptr = kernel32.GlobalLock(hglobal)
        if not ptr or size <= 0:
            raise RuntimeError("JPEG 为空")
        try:
            data = ctypes.string_at(ptr, size)
        finally:
            kernel32.GlobalUnlock(hglobal)
        return data
    finally:
        gdiplus.GdipDisposeImage(image)
        if stream:
            try:
                _release_istream(stream)
            except Exception:
                pass


def _release_istream(stream) -> None:
    class IUnknown(ctypes.Structure):
        pass

    class IUnknownVTable(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", ctypes.c_void_p),
            ("AddRef", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
            ("Release", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ]

    IUnknown._fields_ = [("lpVtbl", ctypes.POINTER(IUnknownVTable))]
    obj = ctypes.cast(stream, ctypes.POINTER(IUnknown))
    obj.contents.lpVtbl.contents.Release(obj)


class ScreenSender:
    def __init__(self, send_jpeg) -> None:
        self._send_jpeg = send_jpeg
        self._alive = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
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
        self._alive = True
        self._thread = threading.Thread(target=self._loop, args=(chosen.key,), daemon=True)
        self._thread.start()
        return chosen

    def stop(self) -> None:
        self._alive = False
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.2)

    def _loop(self, key: str) -> None:
        while self._alive:
            started = time.monotonic()
            try:
                monitors = list_monitors()
                chosen = pick_monitor(monitors, key)
                if chosen is None:
                    raise RuntimeError("显示器已断开")
                self.title = chosen.label()
                jpeg = capture_jpeg_fit(chosen)
                if self._alive and jpeg:
                    self._send_jpeg(jpeg)
                    self.frames += 1
            except Exception as exc:
                self.error = str(exc)
                time.sleep(0.8)
                continue
            remain = FRAME_INTERVAL - (time.monotonic() - started)
            if remain > 0:
                time.sleep(remain)
