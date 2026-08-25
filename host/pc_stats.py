"""Windows CPU / GPU / RAM / disk / network sample for the LX04 HUD.

No extra overlay is required to ship the host. Occupancy comes from bundled
psutil plus built-in Windows APIs. GPU numbers use the already-installed
NVIDIA/AMD driver DLL when present. MSI Afterburner shared memory is optional
and only improves CPU package temperature.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2
ERROR_SUCCESS = 0
NVML_TEMPERATURE_GPU = 0
MAHM_SIGNATURE = 0x4D41484D
FILE_MAP_READ = 0x0004

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
pdh = ctypes.WinDLL("pdh")

kernel32.GetLogicalDriveStringsW.argtypes = [wintypes.DWORD, wintypes.LPWSTR]
kernel32.GetLogicalDriveStringsW.restype = wintypes.DWORD
kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
kernel32.GetDriveTypeW.restype = wintypes.UINT
kernel32.GetVolumeInformationW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.LPWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPWSTR,
    wintypes.DWORD,
]
kernel32.GetVolumeInformationW.restype = wintypes.BOOL
kernel32.GetDiskFreeSpaceExW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
]
kernel32.GetDiskFreeSpaceExW.restype = wintypes.BOOL

DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_RAMDISK = 6

kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenFileMappingW.restype = wintypes.HANDLE
kernel32.MapViewOfFile.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_size_t,
]
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
kernel32.UnmapViewOfFile.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
pdh.PdhOpenQueryW.restype = wintypes.DWORD
pdh.PdhAddEnglishCounterW.argtypes = [
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
]
pdh.PdhAddEnglishCounterW.restype = wintypes.DWORD
pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
pdh.PdhCollectQueryData.restype = wintypes.DWORD
pdh.PdhGetFormattedCounterArrayW.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
pdh.PdhGetFormattedCounterArrayW.restype = wintypes.DWORD
pdh.PdhGetFormattedCounterValue.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
]
pdh.PdhGetFormattedCounterValue.restype = wintypes.DWORD


class PDH_FMT_COUNTERVALUE(ctypes.Structure):
    _fields_ = [
        ("CStatus", wintypes.DWORD),
        ("doubleValue", ctypes.c_double),
    ]


class PDH_FMT_COUNTERVALUE_ITEM_W(ctypes.Structure):
    _fields_ = [
        ("szName", wintypes.LPWSTR),
        ("FmtValue", PDH_FMT_COUNTERVALUE),
    ]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class NVMLMemory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


class NVMLUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class ADLTemperature(ctypes.Structure):
    _fields_ = [("iSize", ctypes.c_int), ("iTemperature", ctypes.c_int)]


class ADLPMActivity(ctypes.Structure):
    _fields_ = [
        ("iSize", ctypes.c_int),
        ("iEngineClock", ctypes.c_int),
        ("iMemoryClock", ctypes.c_int),
        ("iVddc", ctypes.c_int),
        ("iActivityPercent", ctypes.c_int),
        ("iCurrentPerformanceLevel", ctypes.c_int),
        ("iCurrentBusSpeed", ctypes.c_int),
        ("iCurrentBusLanes", ctypes.c_int),
        ("iMaximumBusLanes", ctypes.c_int),
        ("iReserved", ctypes.c_int),
    ]


class AdapterInfo(ctypes.Structure):
    _fields_ = [
        ("iSize", ctypes.c_int),
        ("iAdapterIndex", ctypes.c_int),
        ("strUDID", ctypes.c_char * 256),
        ("iBusNumber", ctypes.c_int),
        ("iDeviceNumber", ctypes.c_int),
        ("iFunctionNumber", ctypes.c_int),
        ("iVendorID", ctypes.c_int),
        ("strAdapterName", ctypes.c_char * 256),
        ("strDisplayName", ctypes.c_char * 256),
        ("iPresent", ctypes.c_int),
        ("iExist", ctypes.c_int),
        ("strDriverPath", ctypes.c_char * 256),
        ("strDriverPathExt", ctypes.c_char * 256),
        ("strPNPString", ctypes.c_char * 256),
        ("iOSDisplayIndex", ctypes.c_int),
    ]


class MahmHeader(ctypes.Structure):
    _fields_ = [
        ("dwSignature", ctypes.c_uint),
        ("dwVersion", ctypes.c_uint),
        ("dwHeaderSize", ctypes.c_uint),
        ("dwNumEntries", ctypes.c_uint),
        ("dwEntrySize", ctypes.c_uint),
        ("time", ctypes.c_int),
        ("dwGPUEntries", ctypes.c_uint),
    ]


ADL_MAIN_MALLOC_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)

_msvcrt = ctypes.CDLL("msvcrt")
_msvcrt.malloc.argtypes = [ctypes.c_size_t]
_msvcrt.malloc.restype = ctypes.c_void_p


@ADL_MAIN_MALLOC_CALLBACK
def _adl_malloc(size: int) -> int | None:
    return _msvcrt.malloc(size)


_lock = threading.Lock()
_sampler: "_Sampler | None" = None


def snapshot(drive: str | None = None) -> dict[str, Any]:
    global _sampler
    with _lock:
        if _sampler is None:
            _sampler = _Sampler()
        return _sampler.sample(drive)


def list_disks() -> list[dict[str, Any]]:
    """Fixed / removable / network volumes with a drive letter."""
    items: list[dict[str, Any]] = []
    system = _drive_letter(None)
    for root in _logical_roots():
        kind = int(kernel32.GetDriveTypeW(root))
        if kind not in (DRIVE_REMOVABLE, DRIVE_FIXED, DRIVE_REMOTE, DRIVE_RAMDISK):
            continue
        usage = _disk_usage(root)
        if usage is None:
            continue
        percent, used, total = usage
        letter = root[:2].upper()
        items.append(
            {
                "letter": letter,
                "label": _volume_label(root),
                "percent": percent,
                "used": used,
                "total": total,
                "system": letter == system,
            }
        )
    if not items:
        usage = _disk_usage(_drive_root(None))
        letter = _drive_letter(None)
        percent, used, total = usage if usage else (0.0, 0.0, 0.0)
        items.append(
            {
                "letter": letter,
                "label": "",
                "percent": percent,
                "used": used,
                "total": total,
                "system": True,
            }
        )
    return items


def disk_choice_label(item: dict[str, Any]) -> str:
    letter = str(item.get("letter") or "C:")
    name = str(item.get("label") or "").strip()
    mark = "  (系统)" if item.get("system") else ""
    if name:
        return f"{letter}  {name}{mark}"
    return f"{letter}{mark}"


def format_line(data: dict[str, Any]) -> str:
    parts = [f"CPU {int(round(float(data.get('cpu') or 0)))}%"]
    cpu_t = data.get("cpuT")
    if isinstance(cpu_t, (int, float)):
        parts[-1] += f" {int(round(cpu_t))}°"
    gpu = data.get("gpu")
    if isinstance(gpu, (int, float)):
        gpu_s = f"GPU {int(round(gpu))}%"
        gpu_t = data.get("gpuT")
        if isinstance(gpu_t, (int, float)):
            gpu_s += f" {int(round(gpu_t))}°"
        name = str(data.get("gpuN") or "").strip()
        if name:
            gpu_s += f" {name}"
        parts.append(gpu_s)
    ram = data.get("ram")
    if isinstance(ram, (int, float)):
        ram_s = f"内存 {int(round(ram))}%"
        used = data.get("ramU")
        total = data.get("ramT")
        if isinstance(used, (int, float)) and isinstance(total, (int, float)):
            ram_s += f" {used:.1f}/{total:.1f}G"
        parts.append(ram_s)
    disk = data.get("disk")
    if isinstance(disk, (int, float)):
        disk_n = str(data.get("diskN") or "磁盘").strip() or "磁盘"
        disk_s = f"{disk_n} {int(round(disk))}%"
        used = data.get("diskU")
        total = data.get("diskT")
        if isinstance(used, (int, float)) and isinstance(total, (int, float)):
            disk_s += f" {used:.0f}/{total:.0f}G"
        parts.append(disk_s)
    return "  ·  ".join(parts)


def _drive_root(drive: str | None) -> str:
    text = (drive or "").strip()
    if not text:
        text = os.environ.get("SystemDrive") or "C:"
    letter = text[:1].upper()
    if not letter.isalpha():
        letter = "C"
    return letter + ":\\"


def _drive_letter(drive: str | None) -> str:
    return _drive_root(drive)[:2]


def default_disk() -> str:
    return _drive_letter(None)


def _logical_roots() -> list[str]:
    buf = (ctypes.c_wchar * 512)()
    n = int(kernel32.GetLogicalDriveStringsW(512, buf) or 0)
    if n <= 0:
        return [_drive_root(None)]
    blob = "".join(buf[i] for i in range(min(n, 512)))
    return [part for part in blob.split("\x00") if part]


def _volume_label(root: str) -> str:
    label = ctypes.create_unicode_buffer(261)
    try:
        if kernel32.GetVolumeInformationW(root, label, 261, None, None, None, None, 0):
            return (label.value or "").strip()
    except Exception:
        return ""
    return ""


def _disk_usage(root: str) -> tuple[float, float, float] | None:
    """Return percent, used GiB, total GiB, or None if the volume is unusable."""
    max_gib = 1024.0 * 1024.0  # 1 PiB: skip stub network mappings with garbage sizes
    if psutil is not None:
        try:
            usage = psutil.disk_usage(root)
            used = usage.used / (1024 ** 3)
            total = usage.total / (1024 ** 3)
            if 0 < total <= max_gib:
                return float(usage.percent), used, total
        except Exception:
            pass
    free = ctypes.c_uint64()
    total_b = ctypes.c_uint64()
    if not kernel32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total_b), ctypes.byref(free)):
        return None
    if total_b.value <= 0:
        return None
    total = total_b.value / (1024 ** 3)
    if total > max_gib:
        return None
    used = (total_b.value - free.value) / (1024 ** 3)
    return 100.0 * used / total, used, total


class _Sampler:
    def __init__(self) -> None:
        self._last_net = None
        self._last_net_at = 0.0
        self._cpu_prev: tuple[int, int] | None = None
        self._pdh = _PdhQuery()
        self._nvml = _Nvml()
        self._adl = _Adl()
        self._mahm = _Mahm()
        if psutil is not None:
            psutil.cpu_percent(interval=None)
        self._read_cpu_times()
        self._pdh.collect()

    def sample(self, drive: str | None = None) -> dict[str, Any]:
        cpu = self._cpu_usage()
        ram = self._ram()
        root = _drive_root(drive)
        usage = _disk_usage(root)
        if usage is None:
            usage = _disk_usage(_drive_root(None)) or (0.0, 0.0, 0.0)
            root = _drive_root(None)
        disk, disk_used, disk_total = usage
        letter = root[:2]
        net_down, net_up = self._net()
        pdh = self._pdh.collect()
        overlay = self._mahm.read()
        cpu_temp = None
        if overlay:
            cpu_temp = overlay.get("cpuT")
        if cpu_temp is None:
            cpu_temp = _pick_temp(pdh.get("temps") or [])
        gpu_u, gpu_t, gpu_n, vram, gpu_w, gpu_fan = self._gpu(pdh, overlay)
        out: dict[str, Any] = {
            "cpu": round(cpu, 1),
            "ram": round(ram[0], 1),
            "ramU": round(ram[1], 1),
            "ramT": round(ram[2], 1),
            "disk": round(disk, 1),
            "diskN": letter,
            "diskU": round(disk_used, 1),
            "diskT": round(disk_total, 1),
            "netD": int(net_down),
            "netU": int(net_up),
            "up": int(self._uptime()),
            "cores": int(self._cores()),
        }
        if cpu_temp is not None:
            out["cpuT"] = round(float(cpu_temp), 1)
        disk_io = pdh.get("diskIo")
        if isinstance(disk_io, (int, float)):
            out["diskIo"] = round(min(100.0, max(0.0, float(disk_io))), 1)
        if gpu_u is not None:
            out["gpu"] = round(min(100.0, max(0.0, float(gpu_u))), 1)
        if gpu_t is not None:
            out["gpuT"] = round(float(gpu_t), 1)
        if gpu_n:
            out["gpuN"] = gpu_n
        if vram is not None:
            out["vram"] = round(min(100.0, max(0.0, float(vram))), 1)
        if gpu_w is not None:
            out["gpuW"] = round(float(gpu_w), 1)
        if gpu_fan is not None:
            out["gpuFan"] = round(float(gpu_fan), 1)
        return out

    def _cpu_usage(self) -> float:
        if psutil is not None:
            try:
                return float(psutil.cpu_percent(interval=None))
            except Exception:
                pass
        idle, total = self._read_cpu_times()
        prev = self._cpu_prev
        self._cpu_prev = (idle, total)
        if prev is None:
            return 0.0
        d_idle = idle - prev[0]
        d_total = total - prev[1]
        if d_total <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (1.0 - d_idle / d_total)))

    def _read_cpu_times(self) -> tuple[int, int]:
        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return 0, 1
        idle_t = _filetime(idle)
        total = _filetime(kernel) + _filetime(user)
        return idle_t, total

    def _ram(self) -> tuple[float, float, float]:
        if psutil is not None:
            try:
                mem = psutil.virtual_memory()
                used = (mem.total - mem.available) / (1024 ** 3)
                total = mem.total / (1024 ** 3)
                return float(mem.percent), used, total
            except Exception:
                pass
        info = MEMORYSTATUSEX()
        info.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            return 0.0, 0.0, 0.0
        total = info.ullTotalPhys / (1024 ** 3)
        avail = info.ullAvailPhys / (1024 ** 3)
        used = max(0.0, total - avail)
        return float(info.dwMemoryLoad), used, total

    def _net(self) -> tuple[float, float]:
        now = time.monotonic()
        if psutil is None:
            return 0.0, 0.0
        try:
            io = psutil.net_io_counters()
            recv = int(io.bytes_recv)
            sent = int(io.bytes_sent)
        except Exception:
            return 0.0, 0.0
        prev = self._last_net
        prev_at = self._last_net_at
        self._last_net = (recv, sent)
        self._last_net_at = now
        if prev is None or now <= prev_at:
            return 0.0, 0.0
        dt = now - prev_at
        return max(0.0, (recv - prev[0]) / dt), max(0.0, (sent - prev[1]) / dt)

    def _uptime(self) -> float:
        if psutil is not None:
            try:
                return max(0.0, time.time() - float(psutil.boot_time()))
            except Exception:
                pass
        return kernel32.GetTickCount64() / 1000.0

    def _cores(self) -> int:
        if psutil is not None:
            try:
                return int(psutil.cpu_count() or 0)
            except Exception:
                pass
        return int(os.cpu_count() or 0)

    def _gpu(
        self,
        pdh: dict[str, Any],
        overlay: dict[str, Any] | None,
    ) -> tuple[float | None, float | None, str, float | None, float | None, float | None]:
        usage = temp = vram = watts = fan = None
        name = ""
        nv = self._nvml.read()
        if nv is not None:
            usage, temp, name, vram, watts, fan = nv
        amd = self._adl.read()
        if amd is not None:
            a_u, a_t, a_name = amd
            if usage is None:
                usage = a_u
            if temp is None:
                temp = a_t
            if a_name and not name:
                name = a_name
        if overlay:
            if usage is None:
                usage = overlay.get("gpu")
            if temp is None:
                temp = overlay.get("gpuT")
            if watts is None:
                watts = overlay.get("gpuW")
            if fan is None:
                fan = overlay.get("gpuFan")
        if usage is None:
            usage = pdh.get("gpu")
        return usage, temp, _short_gpu_name(name), vram, watts, fan


class _PdhQuery:
    def __init__(self) -> None:
        self.hquery = ctypes.c_void_p()
        self.gpu = ctypes.c_void_p()
        self.temps = ctypes.c_void_p()
        self.temps_hi = ctypes.c_void_p()
        self.disk = ctypes.c_void_p()
        self._ready = False
        if pdh.PdhOpenQueryW(None, None, ctypes.byref(self.hquery)) != ERROR_SUCCESS:
            return
        pdh.PdhAddEnglishCounterW(
            self.hquery, "\\GPU Engine(*)\\Utilization Percentage", None, ctypes.byref(self.gpu)
        )
        pdh.PdhAddEnglishCounterW(
            self.hquery,
            "\\Thermal Zone Information(*)\\High Precision Temperature",
            None,
            ctypes.byref(self.temps_hi),
        )
        pdh.PdhAddEnglishCounterW(
            self.hquery, "\\Thermal Zone Information(*)\\Temperature", None, ctypes.byref(self.temps)
        )
        pdh.PdhAddEnglishCounterW(
            self.hquery, "\\PhysicalDisk(_Total)\\% Disk Time", None, ctypes.byref(self.disk)
        )
        self._ready = True
        pdh.PdhCollectQueryData(self.hquery)

    def collect(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if not self._ready:
            return out
        if pdh.PdhCollectQueryData(self.hquery) != ERROR_SUCCESS:
            return out
        gpu_items = _pdh_array(self.gpu)
        engine = 0.0
        for name, value in gpu_items:
            lowered = name.lower()
            if "engtype_3d" in lowered or lowered.endswith("_3d"):
                engine += max(0.0, value)
        if gpu_items:
            out["gpu"] = min(100.0, engine) if engine > 0 else min(
                100.0, max((v for _n, v in gpu_items), default=0.0)
            )
        temps: list[float] = []
        for _name, value in _pdh_array(self.temps_hi):
            celsius = value / 10.0 - 273.15
            if 32.0 <= celsius <= 115.0:
                temps.append(celsius)
        if not temps:
            for _name, value in _pdh_array(self.temps):
                raw = float(value)
                celsius = raw / 10.0 - 273.15 if raw > 200 else raw - 273.15
                if 32.0 <= celsius <= 115.0:
                    temps.append(celsius)
        if temps:
            out["temps"] = temps
        disk = _pdh_single(self.disk)
        if disk is not None:
            out["diskIo"] = disk
        return out


def _pdh_array(counter: ctypes.c_void_p) -> list[tuple[str, float]]:
    if not counter:
        return []
    size = wintypes.DWORD(0)
    count = wintypes.DWORD(0)
    status = pdh.PdhGetFormattedCounterArrayW(
        counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None
    )
    if status not in (PDH_MORE_DATA, ERROR_SUCCESS) or size.value <= 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    status = pdh.PdhGetFormattedCounterArrayW(
        counter, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), buf
    )
    if status != ERROR_SUCCESS or count.value <= 0:
        return []
    items = ctypes.cast(buf, ctypes.POINTER(PDH_FMT_COUNTERVALUE_ITEM_W))
    out: list[tuple[str, float]] = []
    for i in range(count.value):
        item = items[i]
        try:
            name = item.szName or ""
            value = float(item.FmtValue.doubleValue)
        except Exception:
            continue
        if item.FmtValue.CStatus == 0:
            out.append((name, value))
    return out


def _pdh_single(counter: ctypes.c_void_p) -> float | None:
    if not counter:
        return None
    value = PDH_FMT_COUNTERVALUE()
    status = pdh.PdhGetFormattedCounterValue(counter, PDH_FMT_DOUBLE, None, ctypes.byref(value))
    if status != ERROR_SUCCESS or value.CStatus != 0:
        return None
    return float(value.doubleValue)


def _pick_temp(temps: list[float]) -> float | None:
    real = [t for t in temps if t >= 32.0]
    return max(real) if real else None


def _filetime(ft: FILETIME) -> int:
    return (int(ft.dwHighDateTime) << 32) | int(ft.dwLowDateTime)


def _short_gpu_name(name: str) -> str:
    text = (name or "").strip()
    for prefix in (
        "NVIDIA GeForce ",
        "NVIDIA ",
        "AMD Radeon ",
        "AMD ",
        "Intel(R) ",
        "Intel ",
    ):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :].strip()
            break
    if len(text) > 22:
        text = text[:21] + "…"
    return text


def _c_str(blob: bytes) -> str:
    return blob.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()


class _Mahm:
    """Optional MSI Afterburner overlay sensors (CPU package temp, etc.)."""

    def read(self) -> dict[str, Any] | None:
        handle = None
        view = None
        try:
            for name in ("MAHMSharedMemory", "Global\\MAHMSharedMemory"):
                handle = kernel32.OpenFileMappingW(FILE_MAP_READ, False, name)
                if handle:
                    break
            if not handle:
                return None
            view = kernel32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)
            if not view:
                return None
            header = MahmHeader.from_address(view)
            if header.dwSignature != MAHM_SIGNATURE or header.dwNumEntries <= 0:
                return None
            entry_size = int(header.dwEntrySize)
            if entry_size < 64 or entry_size > 4096:
                return None
            data_off = 1300 if entry_size >= 1316 else max(0, entry_size - 16)
            sensors: dict[str, float] = {}
            base = view + int(header.dwHeaderSize)
            for i in range(min(int(header.dwNumEntries), 256)):
                blob = ctypes.string_at(base + i * entry_size, entry_size)
                key = _c_str(blob[:260]).lower()
                if not key:
                    continue
                try:
                    value = float(ctypes.c_float.from_buffer_copy(blob[data_off : data_off + 4]).value)
                except Exception:
                    continue
                sensors[key] = value
            out: dict[str, Any] = {}
            cpu_t = sensors.get("cpu temperature")
            if cpu_t is None:
                cores = [v for k, v in sensors.items() if k.startswith("cpu") and k.endswith("temperature") and k != "cpu temperature"]
                if cores:
                    cpu_t = max(cores)
            if isinstance(cpu_t, (int, float)) and 20.0 <= cpu_t <= 115.0:
                out["cpuT"] = float(cpu_t)
            gpu_t = sensors.get("gpu temperature")
            if isinstance(gpu_t, (int, float)) and 20.0 <= gpu_t <= 115.0:
                out["gpuT"] = float(gpu_t)
            gpu_u = sensors.get("gpu usage")
            if isinstance(gpu_u, (int, float)):
                out["gpu"] = float(gpu_u)
            gpu_w = sensors.get("power")
            if isinstance(gpu_w, (int, float)) and 1.0 <= gpu_w <= 800.0:
                out["gpuW"] = float(gpu_w)
            fan = sensors.get("fan speed")
            if isinstance(fan, (int, float)) and fan >= 0:
                out["gpuFan"] = float(fan)
            return out or None
        except Exception:
            return None
        finally:
            if view:
                kernel32.UnmapViewOfFile(view)
            if handle:
                kernel32.CloseHandle(handle)


class _Nvml:
    def __init__(self) -> None:
        self.dll = None
        self.ok = False
        for name in ("nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
            try:
                self.dll = ctypes.WinDLL(name)
                break
            except OSError:
                continue
        if self.dll is None:
            return
        try:
            fn = getattr(self.dll, "nvmlInit_v2", self.dll.nvmlInit)
            if int(fn()) != 0:
                return
            self.ok = True
        except Exception:
            self.ok = False

    def read(self) -> tuple[float, float, str, float | None, float | None, float | None] | None:
        if not self.ok or self.dll is None:
            return None
        try:
            handle = ctypes.c_void_p()
            get_handle = getattr(self.dll, "nvmlDeviceGetHandleByIndex_v2", self.dll.nvmlDeviceGetHandleByIndex)
            if int(get_handle(0, ctypes.byref(handle))) != 0:
                return None
            util = NVMLUtilization()
            if int(self.dll.nvmlDeviceGetUtilizationRates(handle, ctypes.byref(util))) != 0:
                return None
            temp = ctypes.c_uint()
            if int(self.dll.nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU, ctypes.byref(temp))) != 0:
                return None
            vram = None
            mem = NVMLMemory()
            if int(self.dll.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(mem))) == 0 and mem.total:
                vram = 100.0 * mem.used / mem.total
            watts = None
            mw = ctypes.c_uint()
            try:
                if int(self.dll.nvmlDeviceGetPowerUsage(handle, ctypes.byref(mw))) == 0:
                    watts = mw.value / 1000.0
            except Exception:
                watts = None
            fan = None
            speed = ctypes.c_uint()
            try:
                if int(self.dll.nvmlDeviceGetFanSpeed(handle, ctypes.byref(speed))) == 0:
                    fan = float(speed.value)
            except Exception:
                fan = None
            buf = ctypes.create_string_buffer(96)
            name = ""
            if int(self.dll.nvmlDeviceGetName(handle, buf, 96)) == 0:
                name = buf.value.decode("utf-8", errors="ignore")
            return float(util.gpu), float(temp.value), name, vram, watts, fan
        except Exception:
            return None


class _Adl:
    def __init__(self) -> None:
        self.dll = None
        self.ok = False
        for name in ("atiadlxx.dll", "atiadlxy.dll"):
            try:
                self.dll = ctypes.WinDLL(name)
                break
            except OSError:
                continue
        if self.dll is None:
            return
        try:
            create = self.dll.ADL_Main_Control_Create
            create.argtypes = [ADL_MAIN_MALLOC_CALLBACK, ctypes.c_int]
            create.restype = ctypes.c_int
            if int(create(_adl_malloc, 1)) != 0:
                return
            self.ok = True
        except Exception:
            self.ok = False

    def read(self) -> tuple[float, float | None, str] | None:
        if not self.ok or self.dll is None:
            return None
        try:
            count = ctypes.c_int()
            if int(self.dll.ADL_Adapter_NumberOfAdapters_Get(ctypes.byref(count))) != 0 or count.value <= 0:
                return None
            infos = (AdapterInfo * count.value)()
            infos[0].iSize = ctypes.sizeof(AdapterInfo)
            size = ctypes.c_int(ctypes.sizeof(infos))
            if int(self.dll.ADL_Adapter_AdapterInfo_Get(ctypes.byref(infos), size)) != 0:
                return None
            best: tuple[float, float | None, str] | None = None
            for info in infos:
                if not info.iPresent:
                    continue
                idx = int(info.iAdapterIndex)
                activity = ADLPMActivity()
                activity.iSize = ctypes.sizeof(ADLPMActivity)
                usage = None
                if int(self.dll.ADL_Overdrive5_CurrentActivity_Get(idx, ctypes.byref(activity))) == 0:
                    usage = float(activity.iActivityPercent)
                temp_s = ADLTemperature()
                temp_s.iSize = ctypes.sizeof(ADLTemperature)
                temp = None
                if int(self.dll.ADL_Overdrive5_Temperature_Get(idx, 0, ctypes.byref(temp_s))) == 0:
                    celsius = temp_s.iTemperature / 1000.0
                    if 20.0 <= celsius <= 115.0:
                        temp = celsius
                name = ""
                try:
                    name = info.strAdapterName.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
                except Exception:
                    name = ""
                if usage is None and temp is None:
                    continue
                candidate = (usage if usage is not None else 0.0, temp, name)
                if best is None or (candidate[1] or 0) > (best[1] or 0):
                    best = candidate
            return best
        except Exception:
            return None


if __name__ == "__main__":
    snapshot()
    time.sleep(1.0)
    data = snapshot()
    print(format_line(data))
    for key in sorted(data):
        print(f"  {key}: {data[key]}")
