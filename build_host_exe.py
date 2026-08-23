#!/usr/bin/env python3
"""Package the Windows host into a versioned onefile EXE."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION.txt"
DIST = ROOT / "dist"
HOST = ROOT / "host"


def current_version() -> int:
    if not VERSION_FILE.exists():
        return 1
    text = VERSION_FILE.read_text(encoding="utf-8").strip()
    return int(text) if text else 1


def next_exe_version() -> int:
    version = current_version()
    while (DIST / f"LX04-PC-Bridge-Host-v{version}.exe").exists():
        version += 1
    if version != current_version():
        VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    return version


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    version = next_exe_version()
    name = f"LX04-PC-Bridge-Host-v{version}"
    exe_path = DIST / f"{name}.exe"
    latest = DIST / "LX04-PC-Bridge-Host.exe"

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyinstaller", "sounddevice"])
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build" / "pyinstaller"),
        "--paths",
        str(HOST),
        "--hidden-import",
        "adb_usb",
        "--hidden-import",
        "protocol",
        "--hidden-import",
        "audio_out",
        "--hidden-import",
        "sounddevice",
        "--hidden-import",
        "_sounddevice",
        "--hidden-import",
        "cffi",
        "--hidden-import",
        "_cffi_backend",
        "--collect-all",
        "sounddevice",
        "--collect-all",
        "cffi",
        str(HOST / "pc_host.py"),
    ]
    print("Building", exe_path)
    subprocess.check_call(cmd)
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(exe_path.read_bytes())
    print("Wrote", exe_path)
    print("Wrote", latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
