"""Locate, detect, and launch the official VB-CABLE installer."""
from __future__ import annotations

import ctypes
import sys
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

DONATE_TEXT = (
    "需要安装 VB-CABLE（VB-Audio 的虚拟声卡，捐赠软件）。\n"
    "来源：www.vb-cable.com\n"
    "这是官方安装程序，不是本上位机自带的驱动。觉得好用请向作者捐赠。\n\n"
    "将以管理员身份打开官方安装包。装完后通常需要重启电脑，再打开本程序。"
)

ZIP_NAME = "VBCABLE_Driver_Pack45.zip"
SETUP_X64 = "VBCABLE_Setup_x64.exe"
SETUP_X86 = "VBCABLE_Setup.exe"


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _candidate_dirs() -> list[Path]:
    folders = [
        _host_dir() / "vbcable" / "pack",
        _host_dir() / "vbcable",
        _host_dir().parent / "host" / "vbcable" / "pack",
        _host_dir().parent / "host" / "vbcable",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        folders.insert(0, Path(meipass) / "vbcable")
    return folders


def package_dir() -> Path | None:
    for folder in _candidate_dirs():
        if (folder / SETUP_X64).is_file() or (folder / SETUP_X86).is_file():
            return folder
    return None


def setup_exe() -> Path | None:
    folder = package_dir()
    if folder is None:
        return None
    x64 = folder / SETUP_X64
    x86 = folder / SETUP_X86
    if sys.maxsize > 2**32 and x64.is_file():
        return x64
    if x86.is_file():
        return x86
    if x64.is_file():
        return x64
    return None


def zip_path() -> Path | None:
    for folder in _candidate_dirs():
        candidate = folder / ZIP_NAME
        if candidate.is_file():
            return candidate
    return None


def _pack_dir() -> Path:
    folder = _host_dir() / "vbcable" / "pack"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ensure_installer() -> Path | None:
    found = setup_exe()
    if found is not None:
        return found
    archive = zip_path()
    if archive is None:
        return None
    want = SETUP_X64 if sys.maxsize > 2**32 else SETUP_X86
    pack = _pack_dir()
    try:
        with zipfile.ZipFile(archive) as zf:
            infos = {Path(info.filename).name.lower(): info for info in zf.infolist() if not info.is_dir()}
            info = infos.get(want.lower()) or infos.get(SETUP_X64.lower()) or infos.get(SETUP_X86.lower())
            if info is None:
                return None
            target = pack / Path(info.filename).name
            target.write_bytes(zf.read(info))
            return target
    except Exception:
        return None


def present() -> bool:
    try:
        import win_endpoint
    except Exception:
        return False
    return win_endpoint.find_cable_capture() is not None and win_endpoint.find_cable_render() is not None


def _is_hifi(name: str) -> bool:
    lowered = (name or "").lower()
    return "hi-fi" in lowered or "hifi" in lowered


def _is_vb_cable_input(name: str) -> bool:
    lowered = (name or "").lower()
    return "cable input" in lowered and not _is_hifi(name) and "16ch" not in lowered and "16 ch" not in lowered


def _is_vb_cable_output(name: str) -> bool:
    lowered = (name or "").lower()
    return "cable output" in lowered and not _is_hifi(name)


def run_official_setup() -> str:
    exe = ensure_installer()
    if exe is None:
        return "没有找到官方 VB-CABLE 安装程序。请从 www.vb-cable.com 下载 VBCABLE_Driver_Pack45.zip，解压后运行 VBCABLE_Setup_x64.exe。"
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
        return "VB-CABLE 已就绪。"
    return "官方安装程序已结束。若声音设置里还没有 CABLE Output，请重启电脑后再打开本程序。"
