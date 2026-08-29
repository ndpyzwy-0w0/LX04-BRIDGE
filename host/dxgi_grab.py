"""DXGI desktop duplication for one monitor. Falls back to GDI at the caller."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ERROR_ACCESS_LOST = 0x887A0026
DXGI_ERROR_WAIT_TIMEOUT = 0x887A0027
DXGI_ERROR_ACCESS_DENIED = 0x887A002B
DXGI_FORMAT_B8G8R8A8_UNORM = 87
D3D11_SDK_VERSION = 7
D3D_DRIVER_TYPE_UNKNOWN = 0
D3D11_USAGE_STAGING = 3
D3D11_CPU_ACCESS_READ = 0x20000
D3D11_MAP_READ = 1
D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
DXGI_MODE_ROTATION_IDENTITY = 1
BI_RGB = 0
DIB_RGB_COLORS = 0
SRCCOPY = 0x00CC0020
COLORONCOLOR = 3

dxgi = ctypes.WinDLL("dxgi")
d3d11 = ctypes.WinDLL("d3d11")
gdi32 = ctypes.WinDLL("gdi32")
user32 = ctypes.WinDLL("user32")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class DXGI_OUTPUT_DESC(ctypes.Structure):
    _fields_ = [
        ("DeviceName", wintypes.WCHAR * 32),
        ("DesktopCoordinates", RECT),
        ("AttachedToDesktop", wintypes.BOOL),
        ("Rotation", ctypes.c_uint),
        ("Monitor", wintypes.HANDLE),
    ]


class DXGI_SAMPLE_DESC(ctypes.Structure):
    _fields_ = [("Count", ctypes.c_uint), ("Quality", ctypes.c_uint)]


class D3D11_TEXTURE2D_DESC(ctypes.Structure):
    _fields_ = [
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("MipLevels", ctypes.c_uint),
        ("ArraySize", ctypes.c_uint),
        ("Format", ctypes.c_uint),
        ("SampleDesc", DXGI_SAMPLE_DESC),
        ("Usage", ctypes.c_uint),
        ("BindFlags", ctypes.c_uint),
        ("CPUAccessFlags", ctypes.c_uint),
        ("MiscFlags", ctypes.c_uint),
    ]


class D3D11_MAPPED_SUBRESOURCE(ctypes.Structure):
    _fields_ = [
        ("pData", ctypes.c_void_p),
        ("RowPitch", ctypes.c_uint),
        ("DepthPitch", ctypes.c_uint),
    ]


class DXGI_OUTDUPL_POINTER_POSITION(ctypes.Structure):
    _fields_ = [("Position", wintypes.POINT), ("Visible", wintypes.BOOL)]


class DXGI_OUTDUPL_FRAME_INFO(ctypes.Structure):
    _fields_ = [
        ("LastPresentTime", ctypes.c_int64),
        ("LastMouseUpdateTime", ctypes.c_int64),
        ("AccumulatedFrames", ctypes.c_uint),
        ("RectsCoalesced", wintypes.BOOL),
        ("ProtectedContentMaskedOut", wintypes.BOOL),
        ("PointerPosition", DXGI_OUTDUPL_POINTER_POSITION),
        ("TotalMetadataBufferSize", ctypes.c_uint),
        ("PointerShapeBufferSize", ctypes.c_uint),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]


def _guid(d1: int, d2: int, d3: int, d4: tuple[int, ...]) -> GUID:
    value = GUID()
    value.Data1 = d1
    value.Data2 = d2
    value.Data3 = d3
    value.Data4[:] = d4
    return value


IID_IDXGIFactory1 = _guid(0x770AAE78, 0xF26F, 0x4DBA, (0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87))
IID_IDXGIOutput1 = _guid(0x00CDDEA8, 0x939B, 0x4B83, (0xA3, 0x40, 0xA6, 0x85, 0x22, 0x66, 0x66, 0xCC))
IID_ID3D11Texture2D = _guid(0x6F15AAF2, 0xD208, 0x4E89, (0x9A, 0xB4, 0x48, 0x95, 0x35, 0xD3, 0x4F, 0x9C))

dxgi.CreateDXGIFactory1.argtypes = [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
dxgi.CreateDXGIFactory1.restype = ctypes.c_long
d3d11.D3D11CreateDevice.argtypes = [
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
    ctypes.POINTER(ctypes.c_uint), ctypes.c_uint, ctypes.c_uint,
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint),
    ctypes.POINTER(ctypes.c_void_p),
]
d3d11.D3D11CreateDevice.restype = ctypes.c_long
gdi32.StretchDIBits.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), ctypes.c_uint, wintypes.DWORD,
]
gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]


def _u(hr: int) -> int:
    return ctypes.c_uint32(hr).value


def _vtbl(ptr) -> ctypes.POINTER(ctypes.c_void_p):
    return ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents


def _release(ptr) -> None:
    if not ptr:
        return
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(_vtbl(ptr)[2])(ptr)


def _qi(ptr, iid: GUID):
    out = ctypes.c_void_p()
    hr = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
    )(_vtbl(ptr)[0])(ptr, ctypes.byref(iid), ctypes.byref(out))
    if hr != 0 or not out:
        return None
    return out


class AccessLost(Exception):
    pass


class DxgiGrab:
    def __init__(self) -> None:
        self.key = ""
        self.device = None
        self.ctx = None
        self.dup = None
        self.staging = None
        self.w = 0
        self.h = 0
        self._pack: ctypes.Array | None = None
        self._acquire = None
        self._release_frame = None
        self._copy = None
        self._map = None
        self._unmap = None
        self._getdesc = None
        self._create_tex = None

    def close(self) -> None:
        for ptr in (self.staging, self.dup, self.ctx, self.device):
            _release(ptr)
        self.device = self.ctx = self.dup = self.staging = None
        self.w = self.h = 0
        self.key = ""

    def open(self, key: str) -> bool:
        self.close()
        factory = ctypes.c_void_p()
        hr = dxgi.CreateDXGIFactory1(ctypes.byref(IID_IDXGIFactory1), ctypes.byref(factory))
        if hr != 0 or not factory:
            return False
        try:
            for adapter_i in range(8):
                adapter = ctypes.c_void_p()
                hr = ctypes.WINFUNCTYPE(
                    ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
                )(_vtbl(factory)[12])(factory, adapter_i, ctypes.byref(adapter))
                if _u(hr) == DXGI_ERROR_NOT_FOUND:
                    break
                if hr != 0 or not adapter:
                    continue
                try:
                    if self._open_adapter(adapter, key):
                        return True
                finally:
                    _release(adapter)
        finally:
            _release(factory)
        return False

    def _open_adapter(self, adapter, key: str) -> bool:
        for output_i in range(16):
            output = ctypes.c_void_p()
            hr = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
            )(_vtbl(adapter)[7])(adapter, output_i, ctypes.byref(output))
            if _u(hr) == DXGI_ERROR_NOT_FOUND:
                return False
            if hr != 0 or not output:
                continue
            try:
                desc = DXGI_OUTPUT_DESC()
                hr = ctypes.WINFUNCTYPE(
                    ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(DXGI_OUTPUT_DESC)
                )(_vtbl(output)[7])(output, ctypes.byref(desc))
                if hr != 0 or not desc.AttachedToDesktop:
                    continue
                if desc.DeviceName != key:
                    continue
                if desc.Rotation not in (0, DXGI_MODE_ROTATION_IDENTITY):
                    return False
                return self._duplicate(adapter, output, key)
            finally:
                _release(output)
        return False

    def _duplicate(self, adapter, output, key: str) -> bool:
        output1 = _qi(output, IID_IDXGIOutput1)
        if not output1:
            return False
        device = ctypes.c_void_p()
        ctx = ctypes.c_void_p()
        level = ctypes.c_uint()
        levels = (ctypes.c_uint * 4)(0xB100, 0xB000, 0xA100, 0xA000)
        hr = d3d11.D3D11CreateDevice(
            adapter, D3D_DRIVER_TYPE_UNKNOWN, None, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            levels, 4, D3D11_SDK_VERSION, ctypes.byref(device), ctypes.byref(level), ctypes.byref(ctx),
        )
        if hr != 0 or not device or not ctx:
            _release(output1)
            return False
        dup = ctypes.c_void_p()
        hr = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )(_vtbl(output1)[22])(output1, device, ctypes.byref(dup))
        _release(output1)
        if hr != 0 or not dup:
            _release(ctx)
            _release(device)
            return False
        self.device = device
        self.ctx = ctx
        self.dup = dup
        self.key = key
        self._acquire = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.POINTER(DXGI_OUTDUPL_FRAME_INFO),
            ctypes.POINTER(ctypes.c_void_p),
        )(_vtbl(dup)[8])
        self._release_frame = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(_vtbl(dup)[14])
        self._copy = ctypes.WINFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(_vtbl(ctx)[47])
        self._map = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(D3D11_MAPPED_SUBRESOURCE),
        )(_vtbl(ctx)[14])
        self._unmap = ctypes.WINFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
        )(_vtbl(ctx)[15])
        self._create_tex = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.POINTER(D3D11_TEXTURE2D_DESC),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )(_vtbl(device)[5])
        return True

    def blit(self, hdc, brush, dest: tuple[int, int, int, int], target_w: int, target_h: int) -> bool:
        # ponytail: CPU StretchDIBits 800x480. Ceiling: D3D shader scale then 800x480 readback.
        if not self.dup:
            return False
        self._pull()
        if not self.staging:
            return False
        mapped = D3D11_MAPPED_SUBRESOURCE()
        hr = self._map(self.ctx, self.staging, 0, D3D11_MAP_READ, 0, ctypes.byref(mapped))
        if hr != 0 or not mapped.pData:
            raise AccessLost()
        try:
            bits = self._packed(mapped)
            fill = RECT(0, 0, target_w, target_h)
            user32.FillRect(hdc, ctypes.byref(fill), brush)
            gdi32.SetStretchBltMode(hdc, COLORONCOLOR)
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = self.w
            info.bmiHeader.biHeight = -self.h
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = BI_RGB
            dest_x, dest_y, dest_w, dest_h = dest
            drawn = gdi32.StretchDIBits(
                hdc, dest_x, dest_y, dest_w, dest_h,
                0, 0, self.w, self.h,
                bits, ctypes.byref(info), DIB_RGB_COLORS, SRCCOPY,
            )
            return drawn != 0
        finally:
            self._unmap(self.ctx, self.staging, 0)

    def _pull(self) -> None:
        got = False
        while True:
            hr = self._take(0)
            if _u(hr) == DXGI_ERROR_WAIT_TIMEOUT:
                break
            if _u(hr) in (DXGI_ERROR_ACCESS_LOST, DXGI_ERROR_ACCESS_DENIED):
                raise AccessLost()
            if hr != 0:
                raise AccessLost()
            got = True
        if got or self.staging:
            return
        hr = self._take(80)
        if _u(hr) == DXGI_ERROR_WAIT_TIMEOUT:
            return
        if hr != 0:
            raise AccessLost()

    def _take(self, timeout_ms: int) -> int:
        info = DXGI_OUTDUPL_FRAME_INFO()
        resource = ctypes.c_void_p()
        hr = self._acquire(self.dup, timeout_ms, ctypes.byref(info), ctypes.byref(resource))
        if hr != 0:
            return hr
        try:
            tex = _qi(resource, IID_ID3D11Texture2D)
            if not tex:
                raise AccessLost()
            try:
                if self._getdesc is None:
                    self._getdesc = ctypes.WINFUNCTYPE(
                        None, ctypes.c_void_p, ctypes.POINTER(D3D11_TEXTURE2D_DESC)
                    )(_vtbl(tex)[10])
                desc = D3D11_TEXTURE2D_DESC()
                self._getdesc(tex, ctypes.byref(desc))
                if not self.staging or desc.Width != self.w or desc.Height != self.h:
                    self._make_staging(desc)
                self._copy(self.ctx, self.staging, tex)
            finally:
                _release(tex)
        finally:
            _release(resource)
            self._release_frame(self.dup)
        return 0

    def _make_staging(self, src: D3D11_TEXTURE2D_DESC) -> None:
        _release(self.staging)
        self.staging = None
        desc = D3D11_TEXTURE2D_DESC()
        desc.Width = src.Width
        desc.Height = src.Height
        desc.MipLevels = 1
        desc.ArraySize = 1
        desc.Format = src.Format or DXGI_FORMAT_B8G8R8A8_UNORM
        desc.SampleDesc.Count = 1
        desc.Usage = D3D11_USAGE_STAGING
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ
        staging = ctypes.c_void_p()
        hr = self._create_tex(self.device, ctypes.byref(desc), None, ctypes.byref(staging))
        if hr != 0 or not staging:
            raise AccessLost()
        self.staging = staging
        self.w = int(src.Width)
        self.h = int(src.Height)
        self._pack = None

    def _packed(self, mapped: D3D11_MAPPED_SUBRESOURCE):
        row = self.w * 4
        if int(mapped.RowPitch) == row:
            return mapped.pData
        need = row * self.h
        if self._pack is None or ctypes.sizeof(self._pack) < need:
            self._pack = (ctypes.c_char * need)()
        src = int(mapped.pData)
        dst = ctypes.addressof(self._pack)
        for y in range(self.h):
            ctypes.memmove(dst + y * row, src + y * mapped.RowPitch, row)
        return dst


def _self_check() -> None:
    import screen_mirror

    monitors = screen_mirror.list_monitors()
    assert monitors, "no monitor"
    grab = DxgiGrab()
    try:
        assert grab.open(monitors[0].key), "DXGI DuplicateOutput failed"
        hdc = user32.GetDC(None)
        assert hdc
        dst = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, 800, 480)
        old = gdi32.SelectObject(dst, bmp)
        brush = gdi32.CreateSolidBrush(0)
        try:
            box = screen_mirror.letterbox(monitors[0].width, monitors[0].height)
            assert grab.blit(dst, brush, box, 800, 480), "DXGI blit failed"
        finally:
            gdi32.SelectObject(dst, old)
            gdi32.DeleteObject(brush)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(dst)
            user32.ReleaseDC(None, hdc)
    finally:
        grab.close()


if __name__ == "__main__":
    _self_check()
    print("dxgi_grab ok")
