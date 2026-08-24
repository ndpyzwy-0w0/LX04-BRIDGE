"""Install the bundled LX04 virtual microphone driver from this application."""
from __future__ import annotations

import ctypes
import subprocess
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_ACCESS_DENIED = 5
ERROR_ALREADY_EXISTS = 183
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

GUID_DEVCLASS_MEDIA = "{4d36e96c-e325-11ce-bfc1-08002be10318}"
HARDWARE_ID = "ROOT\\LX04Mic"
DICD_GENERATE_ID = 0x00000001
SPDRP_HARDWAREID = 1
DIF_REGISTERDEVICE = 0x00000019
INSTALLFLAG_FORCE = 0x00000001
DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


ole32 = ctypes.WinDLL("ole32", use_last_error=True)
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
newdev = ctypes.WinDLL("newdev", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
ole32.CLSIDFromString.restype = ctypes.HRESULT

setupapi.SetupDiCreateDeviceInfoList.argtypes = [ctypes.POINTER(GUID), wintypes.HWND]
setupapi.SetupDiCreateDeviceInfoList.restype = ctypes.c_void_p
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiCreateDeviceInfoW.argtypes = [
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVINFO_DATA),
]
setupapi.SetupDiCreateDeviceInfoW.restype = wintypes.BOOL
setupapi.SetupDiSetDeviceRegistryPropertyW.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
setupapi.SetupDiSetDeviceRegistryPropertyW.restype = wintypes.BOOL
setupapi.SetupDiCallClassInstaller.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiCallClassInstaller.restype = wintypes.BOOL
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

newdev.UpdateDriverForPlugAndPlayDevicesW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.BOOL),
]
newdev.UpdateDriverForPlugAndPlayDevicesW.restype = wintypes.BOOL

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0


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
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def package_dir() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "lx04mic")
    candidates.append(_host_dir() / "lx04mic")
    repo = _host_dir().parent / "driver" / "lx04-mic"
    candidates.extend(
        [
            repo / "x64" / "Release" / "package",
            repo / "x64" / "Debug" / "package",
        ]
    )
    for folder in candidates:
        if folder.is_dir() and any(folder.glob("*.inf")):
            return folder
    return None


def inf_path() -> Path | None:
    folder = package_dir()
    if folder is None:
        return None
    files = sorted(folder.glob("*.inf"))
    return files[0] if files else None


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def secure_boot_on() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\SecureBoot\State")
        try:
            value, _ = winreg.QueryValueEx(key, "UEFISecureBootEnabled")
        finally:
            winreg.CloseKey(key)
        return int(value) == 1
    except OSError:
        return False


def testsigning_on() -> bool:
    try:
        raw = subprocess.check_output(["bcdedit", "/enum", "{current}"], text=True, errors="ignore")
    except Exception:
        return False
    for line in raw.splitlines():
        if "testsigning" in line.lower() and "yes" in line.lower():
            return True
    return False


SECURE_BOOT_MSG = (
    "这台电脑开着安全启动，Windows 不允许加载自制麦克风驱动。"
    "语音软件请继续选「LX04 麦克风」。若要改用内置驱动，请在 BIOS 关闭安全启动后重启。"
)


def enable_testsigning() -> None:
    proc = subprocess.run(
        ["bcdedit", "/set", "testsigning", "on"],
        capture_output=True,
        text=True,
        errors="ignore",
    )
    if proc.returncode == 0:
        return
    text = ((proc.stdout or "") + (proc.stderr or "")).lower()
    if "secure boot" in text or "安全启动" in text:
        raise OSError("SECURE_BOOT")
    raise OSError((proc.stdout or proc.stderr or f"bcdedit failed ({proc.returncode})").strip())


def _guid(text: str) -> GUID:
    value = GUID()
    hr = ole32.CLSIDFromString(text, ctypes.byref(value))
    if hr != 0:
        raise OSError(f"CLSIDFromString failed: 0x{hr & 0xFFFFFFFF:08X}")
    return value


def hardware_ids(devinfo: ctypes.c_void_p, data: SP_DEVINFO_DATA) -> str:
    needed = wintypes.DWORD(0)
    setupapi.SetupDiGetDeviceRegistryPropertyW(
        devinfo, ctypes.byref(data), SPDRP_HARDWAREID, None, None, 0, ctypes.byref(needed)
    )
    if needed.value == 0:
        return ""
    buf = (ctypes.c_wchar * max(2, needed.value // 2 + 2))()
    if not setupapi.SetupDiGetDeviceRegistryPropertyW(
        devinfo,
        ctypes.byref(data),
        SPDRP_HARDWAREID,
        None,
        ctypes.cast(buf, ctypes.c_void_p),
        needed.value,
        ctypes.byref(needed),
    ):
        return ""
    return buf[:].split("\x00\x00")[0].replace("\x00", " ").lower()


def device_exists() -> bool:
    guid = _guid(GUID_DEVCLASS_MEDIA)
    devinfo = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT)
    if devinfo == INVALID_HANDLE_VALUE or not devinfo:
        return False
    try:
        data = SP_DEVINFO_DATA()
        data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        index = 0
        while setupapi.SetupDiEnumDeviceInfo(devinfo, index, ctypes.byref(data)):
            ids = hardware_ids(devinfo, data)
            if HARDWARE_ID.lower() in ids:
                return True
            index += 1
        return False
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devinfo)


def create_root_device() -> None:
    guid = _guid(GUID_DEVCLASS_MEDIA)
    devinfo = setupapi.SetupDiCreateDeviceInfoList(ctypes.byref(guid), None)
    if devinfo == INVALID_HANDLE_VALUE or not devinfo:
        raise OSError("SetupDiCreateDeviceInfoList failed")
    try:
        data = SP_DEVINFO_DATA()
        data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        ok = setupapi.SetupDiCreateDeviceInfoW(
            devinfo,
            "LX04Mic",
            ctypes.byref(guid),
            "LX04 麦克风",
            None,
            DICD_GENERATE_ID,
            ctypes.byref(data),
        )
        if not ok:
            err = ctypes.get_last_error()
            if err != ERROR_ALREADY_EXISTS:
                raise OSError(f"SetupDiCreateDeviceInfo failed ({err})")
            return
        hwid = (HARDWARE_ID + "\x00\x00").encode("utf-16-le")
        blob = (ctypes.c_char * len(hwid)).from_buffer_copy(hwid)
        if not setupapi.SetupDiSetDeviceRegistryPropertyW(
            devinfo, ctypes.byref(data), SPDRP_HARDWAREID, blob, len(hwid)
        ):
            raise OSError(f"SetupDiSetDeviceRegistryProperty failed ({ctypes.get_last_error()})")
        if not setupapi.SetupDiCallClassInstaller(DIF_REGISTERDEVICE, devinfo, ctypes.byref(data)):
            raise OSError(f"SetupDiCallClassInstaller failed ({ctypes.get_last_error()})")
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devinfo)


def add_driver_package(inf: Path) -> None:
    subprocess.check_call(["pnputil", "/add-driver", str(inf), "/install"])


def bind_driver(inf: Path) -> None:
    reboot = wintypes.BOOL(False)
    if not newdev.UpdateDriverForPlugAndPlayDevicesW(
        None, HARDWARE_ID, str(inf), INSTALLFLAG_FORCE, ctypes.byref(reboot)
    ):
        err = ctypes.get_last_error()
        if err not in (0, ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND):
            raise OSError(f"UpdateDriverForPlugAndPlayDevices failed ({err})")


def install_now() -> str:
    inf = inf_path()
    if inf is None:
        return "上位机里没有找到 LX04 麦克风驱动文件。"
    if secure_boot_on() and not testsigning_on():
        return "SECURE_BOOT"
    if not testsigning_on():
        try:
            enable_testsigning()
        except OSError as exc:
            if str(exc) == "SECURE_BOOT":
                return "SECURE_BOOT"
            raise
        return "NEEDS_REBOOT"
    if not device_exists():
        create_root_device()
    add_driver_package(inf)
    bind_driver(inf)
    return "OK"


def _run_elevated() -> int:
    if getattr(sys, "frozen", False):
        params = "--install-lx04-mic"
        workdir = str(Path(sys.executable).resolve().parent)
    else:
        params = f'"{Path(__file__).resolve()}" --install-lx04-mic'
        workdir = str(Path(__file__).resolve().parent)
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = sys.executable
    info.lpParameters = params
    info.lpDirectory = workdir
    info.nShow = SW_HIDE
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        err = ctypes.get_last_error()
        if err == 1223:
            return 1223
        raise OSError(f"无法请求管理员权限 ({err})")
    kernel32.WaitForSingleObject(info.hProcess, 180000)
    code = wintypes.DWORD(1)
    kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(info.hProcess)
    return int(code.value)


def ensure_installed() -> str | None:
    """Return a user-facing message, or None if the driver is already usable."""
    from virtual_mic import VirtualMic

    if VirtualMic().available():
        return None
    inf = inf_path()
    if inf is None:
        return "还没有编译出 LX04 麦克风驱动。开发机请先用 VS + WDK 编译 driver\\lx04-mic。"
    if secure_boot_on() and not testsigning_on():
        return SECURE_BOOT_MSG
    if is_admin():
        result = install_now()
        if result == "SECURE_BOOT":
            return SECURE_BOOT_MSG
        if result == "NEEDS_REBOOT":
            return "已打开 Windows 测试签名。请重启电脑后再打开本程序，麦克风驱动会自动装上。"
        if result == "OK":
            return "已安装 LX04 麦克风驱动。"
        return result
    marker = _host_dir() / "lx04mic-setup.log"
    code = _run_elevated()
    if code == 1223:
        return "需要管理员权限才能安装 LX04 麦克风驱动。"
    if marker.exists():
        text = marker.read_text(encoding="utf-8", errors="ignore").strip()
        try:
            marker.unlink()
        except OSError:
            pass
        if text == "SECURE_BOOT":
            return SECURE_BOOT_MSG
        return text or "驱动安装已结束。"
    return "驱动安装已结束，请再点一次连接。"


def _write_marker(text: str) -> None:
    path = _host_dir() / "lx04mic-setup.log"
    path.write_text(text, encoding="utf-8")


def cli_install() -> int:
    try:
        result = install_now()
        if result == "NEEDS_REBOOT":
            _write_marker("已打开 Windows 测试签名。请重启电脑后再打开本程序。")
            return 2
        if result == "SECURE_BOOT":
            _write_marker(SECURE_BOOT_MSG)
            return 3
        if result == "OK":
            _write_marker("已安装 LX04 麦克风驱动。")
            return 0
        _write_marker(result)
        return 1
    except Exception as exc:
        _write_marker("安装驱动失败: " + str(exc))
        return 1


if __name__ == "__main__":
    if "--install-lx04-mic" in sys.argv:
        raise SystemExit(cli_install())
    raise SystemExit(0)
