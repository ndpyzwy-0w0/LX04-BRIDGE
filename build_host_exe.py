#!/usr/bin/env python3
"""Package WinUI host + Python worker into one EXE. Rollback is git, not extra copies."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION.txt"
DIST = ROOT / "dist"
HOST = ROOT / "host"
HOST_UI = ROOT / "host-ui"

from release_git import commit_usable_version, read_version


def bump_version() -> int:
    version = read_version() + 1
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    print("VERSION.txt ->", version)
    return version


def _dotnet() -> str:
    found = shutil.which("dotnet")
    if found:
        return found
    for candidate in (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet" / "dotnet.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "dotnet" / "dotnet.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError("dotnet not found")


def _pyinstaller_worker(staging: Path) -> Path:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", "pyinstaller", "sounddevice", "pycaw", "comtypes", "psutil"]
    )
    subprocess.check_call(
        [sys.executable, "-c", "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"]
    )
    name = "LX04-PC-Bridge-Worker"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--console",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(staging),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build" / "pyinstaller"),
        "--paths",
        str(HOST),
    ]
    for hidden in (
        "host_controller",
        "host_svc",
        "pc_host",
        "adb_usb",
        "protocol",
        "audio_out",
        "vb_cable",
        "win_mic",
        "win_endpoint",
        "hw_capture",
        "hifi_cable",
        "afterburner",
        "hud_preview",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "_tkinter",
        "speaker_loopback",
        "win_volume",
        "virtual_mic",
        "driver_setup",
        "pycaw",
        "comtypes",
        "sounddevice",
        "_sounddevice",
        "cffi",
        "_cffi_backend",
        "psutil",
        "pc_stats",
        "screen_mirror",
        "dxgi_grab",
        "toast_mirror",
        "comtypes.gen.UIAutomationClient",
    ):
        cmd.extend(["--hidden-import", hidden])
    for pkg in ("psutil", "sounddevice", "cffi", "pycaw", "comtypes"):
        cmd.extend(["--collect-all", pkg])
    vbcable_pack = HOST / "vbcable" / "pack"
    if vbcable_pack.is_dir():
        for item in sorted(vbcable_pack.iterdir()):
            if item.is_file():
                cmd.extend(["--add-data", f"{item};vbcable"])
    hifi_pack = HOST / "hificable" / "pack"
    hifi_zip = HOST / "hificable" / "HiFiCableAsioBridgeSetup_v1007.zip"
    if hifi_pack.is_dir():
        for item in sorted(hifi_pack.iterdir()):
            if item.is_file():
                cmd.extend(["--add-data", f"{item};hificable"])
    if hifi_zip.is_file():
        cmd.extend(["--add-data", f"{hifi_zip};hificable"])
    hifi_notice = HOST / "hificable" / "NOTICE.txt"
    if hifi_notice.is_file():
        cmd.extend(["--add-data", f"{hifi_notice};hificable"])
    driver_pkg = ROOT / "driver" / "lx04-mic" / "x64" / "Release" / "package"
    if driver_pkg.is_dir():
        for item in sorted(driver_pkg.iterdir()):
            if item.is_file():
                cmd.extend(["--add-data", f"{item};lx04mic"])
    adb_dir = HOST / "adb"
    if adb_dir.is_dir():
        for item in sorted(adb_dir.iterdir()):
            if item.suffix.lower() in {".exe", ".dll"}:
                cmd.extend(["--add-binary", f"{item};adb"])
            elif item.suffix.lower() in {".txt", ".md"}:
                cmd.extend(["--add-data", f"{item};adb"])
    cmd.append(str(HOST / "host_svc.py"))
    subprocess.check_call(cmd)
    built = staging / f"{name}.exe"
    dest = HOST_UI / f"{name}.exe"
    dest.write_bytes(built.read_bytes())
    print("Worker", dest)
    return dest


def _publish_winui() -> Path:
    out = HOST_UI / "bin" / "Release" / "net8.0-windows10.0.19041.0" / "win-x64" / "publish" / "LX04-PC-Bridge-Host.exe"
    subprocess.check_call([_dotnet(), "clean", str(HOST_UI / "LX04.HostUi.csproj"), "-c", "Release"], cwd=ROOT)
    subprocess.check_call(
        [
            _dotnet(),
            "publish",
            str(HOST_UI / "LX04.HostUi.csproj"),
            "-c",
            "Release",
            "-r",
            "win-x64",
            "--self-contained",
            "true",
            "--force",
        ],
        cwd=ROOT,
    )
    if not out.is_file():
        raise FileNotFoundError(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack host EXE and commit a local release snapshot.")
    parser.add_argument("-m", "--message", default="", help="Release note for the git commit (Release vN: ...).")
    parser.add_argument("--bump", action="store_true", help="Increment VERSION.txt before packing.")
    parser.add_argument("--no-commit", action="store_true", help="Pack only; skip the local git snapshot.")
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    version = bump_version() if args.bump else read_version()
    staging = ROOT / "build" / "pyinstaller" / "dist"
    staging.mkdir(parents=True, exist_ok=True)
    latest = DIST / "LX04-PC-Bridge-Host.exe"

    print("Building worker")
    _pyinstaller_worker(staging)
    print("Building WinUI shell")
    built = _publish_winui()
    payload = built.read_bytes()
    try:
        latest.write_bytes(payload)
        print("Wrote", latest, "bytes", len(payload))
    except OSError as exc:
        print("Current EXE is in use, left", built, ":", exc)
        print("请先退出上位机，再把该文件复制到", latest)
        return 1
    if not args.no_commit:
        commit_usable_version(version, args.message or "host EXE snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
