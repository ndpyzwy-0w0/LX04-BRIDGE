"""Find adb.exe, list USB devices, and open TCP 17890/17891/17892 over the USB cable."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
PORT = 17890
VIDEO_PORT = 17891
TOAST_PORT = 17892
PKG = "com.lx04.pcbridge"
SERVICE = PKG + "/.BridgeService"


def _bundled_adb_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    paths = [here / "adb" / "adb.exe"]
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", "."))
        exe_dir = Path(sys.executable).resolve().parent
        paths = [
            meipass / "adb" / "adb.exe",
            exe_dir / "adb" / "adb.exe",
            exe_dir / "adb.exe",
        ] + paths
    return paths


def find_adb() -> str | None:
    env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    candidates: list[str] = [str(path) for path in _bundled_adb_paths()]
    candidates.extend(
        [
            shutil.which("adb") or "",
            str(Path(r"D:\AndroidSDK\platform-tools\adb.exe")),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
            r"C:\Android\platform-tools\adb.exe",
            r"C:\platform-tools\adb.exe",
        ]
    )
    if env:
        candidates.insert(len(_bundled_adb_paths()), str(Path(env) / "platform-tools" / "adb.exe"))
    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if Path(path).exists():
            return path
    return None


def _run(adb: str, args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        cwd=str(Path(adb).resolve().parent),
    )


def kill_server(adb: str) -> None:
    if not adb:
        return
    _run(adb, ["kill-server"], timeout=5)


def list_devices(adb: str) -> list[str]:
    result = _run(adb, ["devices"])
    devices: list[str] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def wait_for_device(adb: str, serial: str | None = None, timeout: float = 25.0) -> None:
    args = ["-s", serial] if serial else []
    try:
        result = _run(adb, [*args, "wait-for-device"], timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("音箱 USB 暂时掉线，请拔掉数据线再插上。") from exc
    if result.returncode != 0:
        raise RuntimeError("音箱 USB 暂时掉线，请拔掉数据线再插上。")


def enable_usb_microphone(adb: str, serial: str | None = None) -> str:
    """Keep USB as ADB-only.

    LX04 can enumerate a USB Audio gadget named "LX04 Microphone", but Windows
    usbaudio.sys fails to start (code 10 / protocol error). Switching the gadget
    also drops ADB. Do not change persist.sys.usb.config away from adb.
    """
    args = ["-s", serial] if serial else []
    script = (
        "setprop persist.sys.usb.config adb; "
        "getprop persist.sys.usb.config; echo; getprop sys.usb.config; echo; "
        "ls -l /config/usb_gadget/g1/configs/b.1/"
    )
    result = _run(adb, [*args, "shell", script], timeout=8)
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def usb_mic_links_ok(status_text: str) -> bool:
    return "audio_source" in status_text.replace("\n", " ")


def restore_adb_only(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    script = (
        "setprop persist.sys.usb.config adb; "
        "setprop sys.usb.config adb; "
        "(stop adbd; sleep 1; start adbd) >/dev/null 2>&1 &"
    )
    _run(adb, [*args, "shell", script], timeout=6)


def take_speaker_mic(adb: str, serial: str | None = None) -> str:
    """Stop XiaoAi always-on VPM so tinycap can use the dual digital mics."""
    args = ["-s", serial] if serial else []
    last = ""
    text = ""
    for _ in range(8):
        result = _run(adb, [*args, "shell", "stop mivpm; getprop init.svc.mivpm"], timeout=8)
        text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
        status = (result.stdout or "").strip().splitlines()
        last = status[-1].strip() if status else ""
        if last == "stopped":
            return "已暂停小爱唤醒麦，音箱麦克风交给桥接"
        time.sleep(0.15)
    return "小爱唤醒麦未能释放（mivpm=" + (last or text or "unknown") + "）"


def release_speaker_mic(adb: str, serial: str | None = None) -> str:
    args = ["-s", serial] if serial else []
    result = _run(adb, [*args, "shell", "start mivpm; getprop init.svc.mivpm"], timeout=8)
    text = ((result.stdout or "") + " " + (result.stderr or "")).strip()
    status = (result.stdout or "").strip().splitlines()
    last = status[-1].strip() if status else ""
    if last not in {"running", "restarting"}:
        return "小爱唤醒麦未恢复（mivpm=" + (last or text or "unknown") + "）"
    return "已恢复小爱唤醒麦"


def usb_forward(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    last_err = ""
    for port in (PORT, VIDEO_PORT, TOAST_PORT):
        _run(adb, [*args, "forward", "--remove", f"tcp:{port}"])
        result = _run(adb, [*args, "forward", f"tcp:{port}", f"tcp:{port}"])
        if result.returncode != 0:
            last_err = (result.stderr or result.stdout or f"adb forward {port} failed").strip()
            raise RuntimeError(last_err)


def install_apk(adb: str, apk: Path, serial: str | None = None) -> str:
    args = ["-s", serial] if serial else []
    result = _run(adb, [*args, "install", "-r", "-t", str(apk)], timeout=120)
    text = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(text.strip() or "adb install failed")
    grant_bridge_permission(adb, serial)
    whitelist_bridge(adb, serial)
    start_bridge_service(adb, serial)
    return text.strip()


ROTATION_LABELS = ("正向", "倒转")


def clamp_rotation(value: object) -> int:
    """Only Surface.ROTATION_0 and ROTATION_180."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    n = ((n % 4) + 4) % 4
    return 2 if n >= 2 else 0


def rotation_choice(value: object) -> int:
    """0 = 正向, 1 = 倒转."""
    return 1 if clamp_rotation(value) == 2 else 0


def rotation_label(value: object) -> str:
    return ROTATION_LABELS[rotation_choice(value)]


def set_user_rotation(adb: str, rotation: int, serial: str | None = None) -> None:
    """Lock the speaker display to Surface.ROTATION_* via system settings.

    LX04 has no gyro, so accelerometer_rotation stays off. Shell can write
    Settings.System.USER_ROTATION; `wm user-rotation` is a no-op on 8.1.
    """
    rotation = clamp_rotation(rotation)
    args = ["-s", serial] if serial else []
    script = (
        "settings put system accelerometer_rotation 0; "
        f"settings put system user_rotation {rotation}; "
        f"wm user-rotation lock {rotation} >/dev/null 2>&1; "
        "true"
    )
    result = _run(adb, [*args, "shell", script], timeout=8)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "user_rotation failed").strip()
        raise RuntimeError(err)


def grant_bridge_permission(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    _run(adb, [*args, "shell", "pm", "grant", PKG, "android.permission.RECORD_AUDIO"])
    _run(adb, [*args, "shell", "appops", "set", PKG, "WRITE_SETTINGS", "allow"])


def whitelist_bridge(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    script = (
        f"dumpsys deviceidle whitelist +{PKG} >/dev/null 2>&1; "
        f"am set-inactive {PKG} false >/dev/null 2>&1; "
        f"cmd appops set {PKG} RUN_IN_BACKGROUND allow >/dev/null 2>&1; "
        f"cmd appops set {PKG} RUN_ANY_IN_BACKGROUND allow >/dev/null 2>&1; "
        f"cmd appops set {PKG} WRITE_SETTINGS allow >/dev/null 2>&1; "
        "true"
    )
    _run(adb, [*args, "shell", script], timeout=10)


def start_bridge_service(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    result = _run(
        adb,
        [*args, "shell", "am", "start-foreground-service", "-n", SERVICE],
        timeout=10,
    )
    if result.returncode != 0:
        _run(adb, [*args, "shell", "am", "startservice", "-n", SERVICE], timeout=10)


def start_bridge_ui(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    _run(adb, [*args, "shell", "am", "start", "-n", f"{PKG}/.MainActivity"], timeout=8)


def hide_bridge_ui(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    _run(adb, [*args, "shell", "input", "keyevent", "KEYCODE_HOME"], timeout=8)


def bridge_pid(adb: str, serial: str | None = None) -> str:
    args = ["-s", serial] if serial else []
    result = _run(adb, [*args, "shell", "pidof", PKG])
    return (result.stdout or "").strip().split()[0] if (result.stdout or "").strip() else ""


def ensure_bridge_running(adb: str, serial: str | None = None) -> str:
    grant_bridge_permission(adb, serial)
    whitelist_bridge(adb, serial)
    start_bridge_service(adb, serial)
    time.sleep(0.5)
    pid = bridge_pid(adb, serial)
    if pid:
        return "后台服务已运行 pid=" + pid
    start_bridge_service(adb, serial)
    time.sleep(0.7)
    pid = bridge_pid(adb, serial)
    if pid:
        return "后台服务已拉起 pid=" + pid
    args = ["-s", serial] if serial else []
    err = _run(adb, [*args, "shell", "am", "start-foreground-service", "-n", SERVICE], timeout=10)
    detail = ((err.stderr or "") + " " + (err.stdout or "")).strip()
    raise RuntimeError("无法在音箱上拉起后台服务（未打开窗口）。" + (detail or "请确认已安装 APK。"))
