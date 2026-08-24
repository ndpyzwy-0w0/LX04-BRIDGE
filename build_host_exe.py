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

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyinstaller", "sounddevice", "pycaw", "comtypes", "psutil"])
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
        "vb_cable",
        "--hidden-import",
        "win_mic",
        "--hidden-import",
        "win_endpoint",
        "--hidden-import",
        "hw_capture",
        "--hidden-import",
        "virtual_mic",
        "--hidden-import",
        "driver_setup",
        "--hidden-import",
        "pycaw",
        "--hidden-import",
        "comtypes",
        "--hidden-import",
        "sounddevice",
        "--hidden-import",
        "_sounddevice",
        "--hidden-import",
        "cffi",
        "--hidden-import",
        "_cffi_backend",
        "--hidden-import",
        "psutil",
        "--collect-all",
        "sounddevice",
        "--collect-all",
        "cffi",
        "--collect-all",
        "pycaw",
        "--collect-all",
        "comtypes",
    ]
    vbcable_pack = HOST / "vbcable" / "pack"
    if vbcable_pack.is_dir():
        for item in sorted(vbcable_pack.iterdir()):
            if item.is_file():
                cmd.extend(["--add-data", f"{item};vbcable"])
        dest_cable = DIST / "vbcable"
        dest_pack = dest_cable / "pack"
        dest_pack.mkdir(parents=True, exist_ok=True)
        for item in sorted(vbcable_pack.iterdir()):
            if item.is_file():
                (dest_pack / item.name).write_bytes(item.read_bytes())
        notice = HOST / "vbcable" / "NOTICE.txt"
        zip_pack = HOST / "vbcable" / "VBCABLE_Driver_Pack45.zip"
        if notice.is_file():
            (dest_cable / "NOTICE.txt").write_bytes(notice.read_bytes())
        if zip_pack.is_file():
            (dest_cable / zip_pack.name).write_bytes(zip_pack.read_bytes())
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
    cmd.append(str(HOST / "pc_host.py"))
    print("Building", exe_path)
    subprocess.check_call(cmd)
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(exe_path.read_bytes())
    print("Wrote", exe_path)
    print("Wrote", latest)
    _commit_usable_version(
        version,
        "capture LX04 digital mics with tinycap after pausing XiaoAi VPM",
    )
    return 0


COMMIT_PATHS = [
    "VERSION.txt",
    "README.md",
    "build_host_exe.py",
    ".gitignore",
    ".cursor/rules",
    "app",
    "host",
    "protocol.md",
    "local.properties.example",
    "dist/LX04-PC-Bridge-Host.exe",
]


def _commit_usable_version(version: int, summary: str = "") -> None:
    """Snapshot source + current EXE after a usable pack. Historical vN.exe stay gitignored."""
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        return
    try:
        subprocess.check_call(["git", "add", "--", *COMMIT_PATHS], cwd=ROOT)
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT,
            text=True,
        ).strip()
        if not staged:
            return
        why = summary or "snapshot source and current host EXE"
        message = (
            f"Release v{version}: {why}\n"
            "\n"
            "Keep versioned dist/LX04-PC-Bridge-Host-vN.exe on disk only."
        )
        subprocess.check_call(["git", "commit", "-m", message], cwd=ROOT)
        print("Committed git snapshot for v" + str(version))
    except subprocess.CalledProcessError as exc:
        print("Git commit skipped:", exc)


if __name__ == "__main__":
    raise SystemExit(main())
