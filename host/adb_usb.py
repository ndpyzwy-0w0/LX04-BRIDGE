"""Find adb.exe, list USB devices, and open TCP 17890 over the USB cable."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
PORT = 17890


def find_adb() -> str | None:
    env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    candidates = [
        shutil.which("adb"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
        r"C:\Android\platform-tools\adb.exe",
        r"C:\platform-tools\adb.exe",
    ]
    if env:
        candidates.insert(1, str(Path(env) / "platform-tools" / "adb.exe"))
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def _run(adb: str, args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def list_devices(adb: str) -> list[str]:
    result = _run(adb, ["devices"])
    devices: list[str] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


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
