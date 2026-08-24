"""Locate, detect, and launch the official VB-Audio Hi-Fi Cable installer."""
from __future__ import annotations

import ctypes
import sys
import urllib.request
import zipfile
from ctypes import wintypes
from pathlib import Path

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_SHOWNORMAL = 1

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", ctypes.c_void_p),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", ctypes.c_void_p),
        ("hProcess", wintypes.HANDLE),
    ]


shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
shell32.ShellExecuteExW.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

DOWNLOAD_URL = "https://download.vb-audio.com/Download_CABLE/HiFiCableAsioBridgeSetup_v1007.zip"
SETUP_NAME = "HiFiCableAsioBridgeSetup.exe"
ZIP_NAME = "HiFiCableAsioBridgeSetup_v1007.zip"

DONATE_TEXT = (
    "要把电脑里正在播放的声音接到小爱音箱，需要再装一根虚拟线："
    "VB-Audio Hi-Fi Cable（捐赠软件，和已经装的 VB-CABLE 不是同一根）。\n"
    "来源：vb-audio.com\n"
    "这是官方安装程序。装完后通常需要重启电脑，再打开本程序。\n\n"
    "微信麦克风仍然选「CABLE Output」，不要选 Hi-Fi Cable。\n"
    "将以管理员身份打开官方安装包。"
)


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _candidate_dirs() -> list[Path]:
    folders = [
        _host_dir() / "hificable" / "pack",
        _host_dir() / "hificable",
        _host_dir().parent / "host" / "hificable" / "pack",
        _host_dir().parent / "host" / "hificable",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        folders.insert(0, Path(meipass) / "hificable")
    return folders


def zip_path() -> Path | None:
    for folder in _candidate_dirs():
        candidate = folder / ZIP_NAME
        if candidate.is_file():
            return candidate
    return None


def setup_exe() -> Path | None:
    for folder in _candidate_dirs():
        exe = folder / SETUP_NAME
        if exe.is_file():
            return exe
    return None


def _pack_dir() -> Path:
    folder = _host_dir() / "hificable" / "pack"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ensure_installer() -> Path | None:
    found = setup_exe()
    if found is not None:
        return found
    archive = zip_path()
    if archive is None:
        dest_zip = _host_dir() / "hificable" / ZIP_NAME
        dest_zip.parent.mkdir(parents=True, exist_ok=True)
        try:
            request = urllib.request.Request(
                DOWNLOAD_URL,
                headers={"User-Agent": "LX04-PC-Bridge"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                dest_zip.write_bytes(response.read())
            archive = dest_zip
        except Exception:
            return None
    pack = _pack_dir()
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = Path(info.filename).name
                if name.lower() == SETUP_NAME.lower():
                    target = pack / SETUP_NAME
                    target.write_bytes(zf.read(info))
                    return target
    except Exception:
        return None
    return setup_exe()


def is_hifi_name(name: str) -> bool:
    lowered = (name or "").lower()
    return "hi-fi cable" in lowered or "hifi cable" in lowered or "hi fi cable" in lowered


def is_hifi_render(name: str) -> bool:
    if not is_hifi_name(name):
        return False
    lowered = name.lower()
    if "output" in lowered:
        return False
    return "input" in lowered or "playback" in lowered or "播放" in name


def present() -> bool:
    try:
        import sounddevice as sd
    except ImportError:
        return False
    try:
        devices = list(sd.query_devices())
    except Exception:
        return False
    names = [str(info.get("name") or "") for info in devices]
    return any(is_hifi_render(name) for name in names)


def run_official_setup() -> str:
    exe = ensure_installer()
    if exe is None:
        return (
            "没有找到官方 Hi-Fi Cable 安装程序。请打开 vb-audio.com，"
            f"下载 {ZIP_NAME}，解压后运行 {SETUP_NAME}。"
        )
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = str(exe)
    info.lpDirectory = str(exe.parent)
    info.nShow = SW_SHOWNORMAL
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        err = ctypes.get_last_error()
        if err == 1223:
            return "已取消安装。"
        return f"无法启动官方安装程序 ({err})。"
    kernel32.WaitForSingleObject(info.hProcess, 600000)
    kernel32.CloseHandle(info.hProcess)
    if present():
        return "Hi-Fi Cable 已就绪。"
    return "官方安装程序已结束。若声音设置里还没有 Hi-Fi Cable Input，请重启电脑后再打开本程序。"
