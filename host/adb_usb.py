"""Find adb.exe, list USB devices, and open TCP 17890 over the USB cable."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
PORT = 17890


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


def usb_forward(adb: str, serial: str | None = None) -> None:
    args = ["-s", serial] if serial else []
    _run(adb, [*args, "forward", "--remove", f"tcp:{PORT}"])
    result = _run(adb, [*args, "forward", f"tcp:{PORT}", f"tcp:{PORT}"])
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "adb forward failed").strip())


def install_apk(adb: str, apk: Path, serial: str | None = None) -> str:
    args = ["-s", serial] if serial else []
    result = _run(adb, [*args, "install", "-r", "-t", str(apk)], timeout=120)
    text = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(text.strip() or "adb install failed")
    _run(adb, [*args, "shell", "pm", "grant", "com.lx04.pcbridge", "android.permission.RECORD_AUDIO"])
    _run(adb, [*args, "shell", "am", "start", "-n", "com.lx04.pcbridge/.MainActivity"])
    return text.strip()
