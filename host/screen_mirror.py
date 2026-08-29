"""Capture a chosen Windows monitor as 800x480 JPEG for the LX04 screen."""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

SRCCOPY = 0x00CC0020
COLORONCOLOR = 3
MONITORINFOF_PRIMARY = 1
CCHDEVICENAME = 32
ENCODER_PARAMETER_LONG = 4
JPEG_QUALITY = 8
JPEG_QUALITY_SMALL = 5
MAX_JPEG = 20 * 1024
TARGET_W = 800
TARGET_H = 480
FRAME_INTERVAL = 0.04
MONITOR_REFRESH = 2.0
GRABBER_REOPEN_FRAMES = 400


@dataclass(frozen=True)
class QualityPreset:
    key: str
    quality: int
    quality_small: int
    max_jpeg: int
    ack_wait: float


QUALITY_PRESETS = (
    QualityPreset("流畅", 8, 5, 20 * 1024, 0.28),
    QualityPreset("清晰", 18, 12, 36 * 1024, 0.30),
    QualityPreset("高清", 36, 24, 56 * 1024, 0.35),
    QualityPreset("最高", 58, 40, 96 * 1024, 0.45),
)
QUALITY_KEYS = [item.key for item in QUALITY_PRESETS]
DEFAULT_QUALITY = "清晰"


def pick_quality(name: str) -> QualityPreset:
    wanted = (name or "").strip()
    for item in QUALITY_PRESETS:
        if item.key == wanted:
            return item
    return QUALITY_PRESETS[1]


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
user32.GetCursorInfo.argtypes = [ctypes.c_void_p]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
user32.GetIconInfo.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.DrawIconEx.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HANDLE,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint, wintypes.HANDLE, ctypes.c_uint,
]
user32.DrawIconEx.restype = wintypes.BOOL

gdiplus.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
gdiplus.GdipCreateBitmapFromHBITMAP.argtypes = [wintypes.HBITMAP, wintypes.HPALETTE, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
gdiplus.GdipSaveImageToStream.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_void_p,
]
gdiplus.GdipLoadImageFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipLoadImageFromFile.restype = ctypes.c_int
gdiplus.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
gdiplus.GdipGetImageWidth.restype = ctypes.c_int
gdiplus.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
gdiplus.GdipGetImageHeight.restype = ctypes.c_int
gdiplus.GdipCreateBitmapFromScan0.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
]
gdiplus.GdipCreateBitmapFromScan0.restype = ctypes.c_int
gdiplus.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
gdiplus.GdipDrawImageRectRectI.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
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
    """Per-monitor DPI for capture and monitor lists. Never call this on the Tk UI thread:
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


def letterbox(src_w: int, src_h: int, dst_w: int = TARGET_W, dst_h: int = TARGET_H) -> tuple[int, int, int, int]:
    scale = min(dst_w / max(1, src_w), dst_h / max(1, src_h))
    dest_w = max(1, int(src_w * scale))
    dest_h = max(1, int(src_h * scale))
    dest_x = (dst_w - dest_w) // 2
    dest_y = (dst_h - dest_h) // 2
    return dest_x, dest_y, dest_w, dest_h


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


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


def _draw_cursor(hdc, monitor: Monitor, dest: tuple[int, int, int, int]) -> None:
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)) or info.flags != 1 or not info.hCursor:
        return
    dest_x, dest_y, dest_w, dest_h = dest
    hot_x = hot_y = 0
    icon = ICONINFO()
    if user32.GetIconInfo(info.hCursor, ctypes.byref(icon)):
        hot_x, hot_y = int(icon.xHotspot), int(icon.yHotspot)
        if icon.hbmMask:
            gdi32.DeleteObject(icon.hbmMask)
        if icon.hbmColor:
            gdi32.DeleteObject(icon.hbmColor)
    sx = dest_w / max(1, monitor.width)
    sy = dest_h / max(1, monitor.height)
    x = dest_x + int((info.ptScreenPos.x - monitor.left - hot_x) * sx)
    y = dest_y + int((info.ptScreenPos.y - monitor.top - hot_y) * sy)
    cw = max(1, int(user32.GetSystemMetrics(13) * sx))
    ch = max(1, int(user32.GetSystemMetrics(14) * sy))
    user32.DrawIconEx(hdc, x, y, info.hCursor, cw, ch, 0, None, 3)


class _Grabber:
    def __init__(self) -> None:
        self.src_dc = None
        self.dst_dc = None
        self.bmp = None
        self.old = None
        self.brush = None
        self.stream = None
        self.frames = 0
        self._dxgi = None
        self._dxgi_skip = 0

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

    def grab(
        self,
        monitor: Monitor,
        quality: int | None = None,
        max_jpeg: int | None = None,
        quality_small: int | None = None,
    ) -> bytes:
        if not self.dst_dc or self.frames >= GRABBER_REOPEN_FRAMES:
            self._close_gdi()
            self.open()
        if self._blit_dxgi(monitor):
            return self._finish(quality, max_jpeg, quality_small)
        return self.grab_region(
            monitor.left, monitor.top, monitor.width, monitor.height,
            quality=quality, max_jpeg=max_jpeg, quality_small=quality_small,
        )

    def grab_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        quality: int | None = None,
        max_jpeg: int | None = None,
        quality_small: int | None = None,
    ) -> bytes:
        if not self.dst_dc or self.frames >= GRABBER_REOPEN_FRAMES:
            self._close_gdi()
            self.open()
        fill = RECT(0, 0, TARGET_W, TARGET_H)
        user32.FillRect(self.dst_dc, ctypes.byref(fill), self.brush)
        dest_x, dest_y, dest_w, dest_h = letterbox(width, height)
        ok = gdi32.StretchBlt(
            self.dst_dc, dest_x, dest_y, dest_w, dest_h,
            self.src_dc, left, top, width, height,
            SRCCOPY,
        )
        if not ok:
            self._close_gdi()
            self.open()
            ok = gdi32.StretchBlt(
                self.dst_dc, dest_x, dest_y, dest_w, dest_h,
                self.src_dc, left, top, width, height,
                SRCCOPY,
            )
        if not ok:
            raise RuntimeError("截取屏幕失败")
        return self._finish(quality, max_jpeg, quality_small)

    def _blit_dxgi(self, monitor: Monitor) -> bool:
        import dxgi_grab

        if self._dxgi_skip > 0:
            self._dxgi_skip -= 1
            return False
        try:
            if self._dxgi is None or self._dxgi.key != monitor.key:
                if self._dxgi is not None:
                    self._dxgi.close()
                    self._dxgi = None
                grab = dxgi_grab.DxgiGrab()
                if not grab.open(monitor.key):
                    self._dxgi_skip = 45
                    return False
                self._dxgi = grab
            box = letterbox(monitor.width, monitor.height)
            if not self._dxgi.blit(self.dst_dc, self.brush, box, TARGET_W, TARGET_H):
                return False
            _draw_cursor(self.dst_dc, monitor, box)
            return True
        except dxgi_grab.AccessLost:
            if self._dxgi is not None:
                self._dxgi.close()
                self._dxgi = None
            return False
        except Exception:
            if self._dxgi is not None:
                self._dxgi.close()
                self._dxgi = None
            self._dxgi_skip = 45
            return False

    def _finish(
        self,
        quality: int | None,
        max_jpeg: int | None,
        quality_small: int | None,
    ) -> bytes:
        q = JPEG_QUALITY if quality is None else quality
        cap = MAX_JPEG if max_jpeg is None else max_jpeg
        small = JPEG_QUALITY_SMALL if quality_small is None else quality_small
        data = self._encode(q)
        if len(data) > cap and small < q:
            data = self._encode(small)
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
        if self._dxgi is not None:
            try:
                self._dxgi.close()
            except Exception:
                pass
            self._dxgi = None
        self._close_gdi()

    def _close_gdi(self) -> None:
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
    quality_value = ctypes.c_uint32(max(1, min(100, int(quality))))
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


PixelFormat32bppARGB = 0x26200A
UnitPixel = 2
InterpolationHighQualityBicubic = 7
MAX_STILL_JPEG = 200 * 1024


def encode_still(path: str | Path, width: int = TARGET_W, height: int = TARGET_H) -> bytes:
    """Load a photo, cover-crop to the LX04 screen, and return a JPEG under the FILE payload limit."""
    _ensure_gdiplus()
    source = ctypes.c_void_p()
    status = gdiplus.GdipLoadImageFromFile(str(Path(path)), ctypes.byref(source))
    if status != 0 or not source:
        raise RuntimeError("无法打开图片")
    dest = ctypes.c_void_p()
    graphics = ctypes.c_void_p()
    stream = None
    try:
        src_w = ctypes.c_uint()
        src_h = ctypes.c_uint()
        if gdiplus.GdipGetImageWidth(source, ctypes.byref(src_w)) != 0 or src_w.value <= 0:
            raise RuntimeError("图片宽度无效")
        if gdiplus.GdipGetImageHeight(source, ctypes.byref(src_h)) != 0 or src_h.value <= 0:
            raise RuntimeError("图片高度无效")
        crop_x, crop_y, crop_w, crop_h = _cover_crop(src_w.value, src_h.value, width, height)
        status = gdiplus.GdipCreateBitmapFromScan0(
            width, height, 0, PixelFormat32bppARGB, None, ctypes.byref(dest)
        )
        if status != 0 or not dest:
            raise RuntimeError("无法创建背景图")
        if gdiplus.GdipGetImageGraphicsContext(dest, ctypes.byref(graphics)) != 0 or not graphics:
            raise RuntimeError("无法绘制背景图")
        gdiplus.GdipSetInterpolationMode(graphics, InterpolationHighQualityBicubic)
        status = gdiplus.GdipDrawImageRectRectI(
            graphics, source,
            0, 0, width, height,
            crop_x, crop_y, crop_w, crop_h,
            UnitPixel, None, None, None,
        )
        if status != 0:
            raise RuntimeError("缩放背景图失败")
        stream = _new_istream()
        last = b""
        for quality in (82, 70, 58, 46, 36):
            _istream_setsize(stream, 0)
            _istream_seek0(stream)
            last = _gpimage_to_jpeg(dest, quality, stream)
            if len(last) <= MAX_STILL_JPEG:
                return last
        if len(last) > protocol_max_payload():
            raise RuntimeError("图片太大，请换一张")
        return last
    finally:
        if graphics:
            gdiplus.GdipDeleteGraphics(graphics)
        if dest:
            gdiplus.GdipDisposeImage(dest)
        gdiplus.GdipDisposeImage(source)
        if stream:
            try:
                _istream_release(stream)
            except Exception:
                pass


def protocol_max_payload() -> int:
    try:
        import protocol
        return int(protocol.MAX_PAYLOAD)
    except Exception:
        return 256 * 1024


def _cover_crop(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int, int, int]:
    src_aspect = src_w / float(src_h)
    dst_aspect = dst_w / float(dst_h)
    if src_aspect > dst_aspect:
        crop_h = src_h
        crop_w = max(1, int(round(src_h * dst_aspect)))
        crop_x = max(0, (src_w - crop_w) // 2)
        crop_y = 0
    else:
        crop_w = src_w
        crop_h = max(1, int(round(src_w / dst_aspect)))
        crop_x = 0
        crop_y = max(0, (src_h - crop_h) // 2)
    if crop_x + crop_w > src_w:
        crop_w = src_w - crop_x
    if crop_y + crop_h > src_h:
        crop_h = src_h - crop_y
    return crop_x, crop_y, max(1, crop_w), max(1, crop_h)


def _gpimage_to_jpeg(image, quality: int, stream) -> bytes:
    quality_value = ctypes.c_uint32(max(1, min(100, int(quality))))
    params = EncoderParameters()
    params.Count = 1
    params.Parameter[0].Guid = ENCODER_QUALITY
    params.Parameter[0].NumberOfValues = 1
    params.Parameter[0].Type = ENCODER_PARAMETER_LONG
    params.Parameter[0].Value = ctypes.cast(ctypes.byref(quality_value), ctypes.c_void_p)
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
        self._need = threading.Event()
        self._preset = pick_quality(DEFAULT_QUALITY)
        self._send_s = FRAME_INTERVAL
        self._paused = False
        self.monitor_key = ""
        self.title = ""
        self.error = ""
        self.frames = 0

    def set_quality(self, name: str) -> QualityPreset:
        self._preset = pick_quality(name)
        return self._preset

    def quality_key(self) -> str:
        return self._preset.key

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
        self._need.clear()
        self._paused = False
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
        self._need.set()
        threads = [self._capture_thread, self._send_thread]
        self._capture_thread = None
        self._send_thread = None
        with self._slot:
            self._latest = None
        for thread in threads:
            if thread is not None and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=1.0)

    def pause(self) -> None:
        self._paused = True
        self._ack.set()
        self._need.set()
        self._new_frame.set()

    def resume(self) -> None:
        with self._slot:
            self._latest = None
        self._new_frame.clear()
        self._paused = False

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
                if not self._need.wait(timeout=0.2):
                    continue
                self._need.clear()
                if not self._alive or self._paused:
                    continue
                started = time.monotonic()
                try:
                    if chosen is None or started - last_enum >= MONITOR_REFRESH:
                        chosen = pick_monitor(_enum_monitors(), key)
                        last_enum = started
                        if chosen is not None:
                            self.title = chosen.label()
                    if chosen is None:
                        raise RuntimeError("显示器已断开")
                    preset = self._preset
                    quality = preset.quality_small if self._send_s > 0.08 else preset.quality
                    jpeg = grabber.grab(
                        chosen,
                        quality,
                        max_jpeg=preset.max_jpeg,
                        quality_small=preset.quality_small,
                    )
                    if self._alive and not self._paused and jpeg:
                        self._put(jpeg)
                        self.frames += 1
                except Exception as exc:
                    self.error = str(exc)
                    grabber.close()
                    time.sleep(0.4)
        finally:
            grabber.close()
            try:
                ole32.CoUninitialize()
            except Exception:
                pass

    def _send_loop(self) -> None:
        # ponytail: grab only after the previous JPEG is ACKed, so a frame never
        # sits in the slot aging by one USB RTT. Ceiling: JPEG encode/decode.
        while self._alive:
            if self._paused:
                time.sleep(0.05)
                continue
            self._take()
            self._new_frame.clear()
            self._need.set()
            self._new_frame.wait(timeout=0.8)
            jpeg, _captured_at = self._take()
            if not jpeg or not self._alive or self._paused:
                continue
            self._ack.clear()
            t0 = time.monotonic()
            try:
                self._send_jpeg(jpeg)
            except Exception as exc:
                self.error = str(exc)
            if self._alive:
                self._ack.wait(timeout=self._preset.ack_wait)
            self._send_s = self._send_s * 0.65 + (time.monotonic() - t0) * 0.35


def _self_check() -> None:
    sent: list[bytes] = []
    sender = ScreenSender(lambda jpeg: sent.append(jpeg) or sender.note_ack())
    sender._alive = True

    def capture() -> None:
        while sender._alive:
            if not sender._need.wait(timeout=0.2):
                continue
            sender._need.clear()
            if sender._alive:
                sender._put(b"\xff\xd8" + b"x" * 30)

    cap = threading.Thread(target=capture, daemon=True)
    send = threading.Thread(target=sender._send_loop, daemon=True)
    cap.start()
    send.start()
    deadline = time.monotonic() + 1.0
    while len(sent) < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    sender._alive = False
    sender._need.set()
    sender._new_frame.set()
    sender._ack.set()
    cap.join(timeout=1.0)
    send.join(timeout=1.0)
    assert len(sent) >= 3, len(sent)


if __name__ == "__main__":
    _self_check()
    print("screen_mirror ok")
