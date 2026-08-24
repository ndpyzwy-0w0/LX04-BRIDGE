"""Locate, detect, and launch the official VB-CABLE installer."""
from __future__ import annotations

import ctypes
import sys
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


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def package_dir() -> Path | None:
    candidates = [
        _host_dir() / "vbcable" / "pack",
        _host_dir() / "vbcable",
        _host_dir().parent / "host" / "vbcable" / "pack",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.insert(0, Path(meipass) / "vbcable")
    for folder in candidates:
        if (folder / "VBCABLE_Setup_x64.exe").is_file() or (folder / "VBCABLE_Setup.exe").is_file():
            return folder
    return None


def setup_exe() -> Path | None:
    folder = package_dir()
    if folder is None:
        return None
    x64 = folder / "VBCABLE_Setup_x64.exe"
    x86 = folder / "VBCABLE_Setup.exe"
    if sys.maxsize > 2**32 and x64.is_file():
        return x64
    if x86.is_file():
        return x86
    if x64.is_file():
        return x64
    return None


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
    has_in = any(_is_vb_cable_input(name) for name in names)
    has_out = any(_is_vb_cable_output(name) for name in names)
    return has_in and has_out


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
    exe = setup_exe()
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
