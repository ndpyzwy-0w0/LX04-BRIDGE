#!/usr/bin/env python3
"""Package the Windows host into an onedir folder. Rollback is git, not extra copies."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION.txt"
DIST = ROOT / "dist"
HOST = ROOT / "host"

from release_git import commit_usable_version, read_version

# PyInstaller's QtQml hook copies every QML plugin; WebEngine alone is ~194MB.
_QT_DROP_PREFIXES = (
    "Qt6WebEngine",
    "Qt6WebView",
    "Qt6Pdf",
    "Qt6Quick3D",
    "Qt63D",
    "Qt6Charts",
    "Qt6Graphs",
    "Qt6Location",
    "Qt6Multimedia",
    "Qt6DataVisualization",
    "Qt6VirtualKeyboard",
    "Qt6Sensors",
    "Qt6Scxml",
    "Qt6StateMachine",
    "Qt6RemoteObjects",
    "Qt6TextToSpeech",
    "Qt6Test",
    "Qt6Sql",
    "Qt6Positioning",
    "Qt6WebChannel",
    "Qt6WebSockets",
    "Qt6SpatialAudio",
    "Qt6ShaderTools",
    "Qt6Labs",
    "Qt6QuickControls2Imagine",
    "Qt6QuickControls2Material",
    "Qt6QuickControls2Universal",
    "Qt6QuickControls2Fusion",
    "Qt6QuickControls2Basic",
    "Qt6QuickControls2Windows",
    "Qt6QuickParticles",
    "Qt6QuickTest",
    "Qt6QuickVectorImage",
    "Qt6QuickTimeline",
    "Qt6QuickDialogs2",
    "Qt6OpenGLWidgets",
    "opengl32sw",
)
_QML_DROP = (
    "Qt",
    "Qt3D",
    "Qt5Compat",
    "QtCharts",
    "QtDataVisualization",
    "QtGraphs",
    "QtLocation",
    "QtMultimedia",
    "QtPositioning",
    "QtQuick3D",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtTest",
    "QtTextToSpeech",
    "QtWebChannel",
    "QtWebEngine",
    "QtWebSockets",
    "QtWebView",
)
_QTQUICK_DROP = (
    "Dialogs",
    "LocalStorage",
    "NativeStyle",
    "Particles",
    "Pdf",
    "Scene2D",
    "Scene3D",
    "Timeline",
    "tooling",
    "VectorImage",
    "VirtualKeyboard",
)
_CONTROLS_DROP = ("designer", "Imagine", "Material", "Universal", "Fusion", "Windows")


def slim_host_dir(root: Path) -> None:
    """Delete unused Qt/QML payloads from an onedir build."""
    internal = root / "_internal"
    pyside = internal / "PySide6"
    if pyside.is_dir():
        for item in pyside.iterdir():
            if item.is_file() and any(item.name.startswith(prefix) for prefix in _QT_DROP_PREFIXES):
                item.unlink()
        qml = pyside / "qml"
        if qml.is_dir():
            for name in _QML_DROP:
                target = qml / name
                if target.is_dir():
                    shutil.rmtree(target)
            quick = qml / "QtQuick"
            for name in _QTQUICK_DROP:
                target = quick / name
                if target.is_dir():
                    shutil.rmtree(target)
            controls = quick / "Controls"
            for name in _CONTROLS_DROP:
                target = controls / name
                if target.is_dir():
                    shutil.rmtree(target)
        tooling = pyside / "plugins" / "qmltooling"
        if tooling.is_dir():
            shutil.rmtree(tooling)
    tests = internal / "comtypes" / "test"
    if tests.is_dir():
        shutil.rmtree(tests)
    if internal.is_dir():
        for qm in internal.rglob("*.qm"):
            if "zh_CN" not in qm.name and "zh_Hans" not in qm.name:
                qm.unlink()


def bump_version() -> int:
    version = read_version() + 1
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    print("VERSION.txt ->", version)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack host EXE and commit a local release snapshot.")
    parser.add_argument(
        "-m",
        "--message",
        default="",
        help="Release note for the git commit (Release vN: ...).",
    )
    parser.add_argument(
        "--bump",
        action="store_true",
        help="Increment VERSION.txt before packing.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Pack only; skip the local git snapshot.",
    )
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    version = bump_version() if args.bump else read_version()
    name = "LX04-PC-Bridge-Host"
    staging = ROOT / "build" / "pyinstaller" / "dist"
    staging.mkdir(parents=True, exist_ok=True)
    built = staging / name
    latest = DIST / name
    old_onefile = DIST / f"{name}.exe"

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyinstaller", "sounddevice", "pycaw", "comtypes", "psutil", "PySide6"])
    subprocess.check_call(
        [sys.executable, "-c", "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"]
    )
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
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
        "hifi_cable",
        "--hidden-import",
        "afterburner",
        "--hidden-import",
        "hud_preview",
        "--hidden-import",
        "speaker_loopback",
        "--hidden-import",
        "win_volume",
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
        "--hidden-import",
        "pc_stats",
        "--hidden-import",
        "screen_mirror",
        "--hidden-import",
        "dxgi_grab",
        "--hidden-import",
        "toast_mirror",
        "--hidden-import",
        "qt_ui",
        "--hidden-import",
        "PySide6.QtQuick",
        "--hidden-import",
        "PySide6.QtOpenGL",
        "--hidden-import",
        "PySide6.QtQuickControls2",
        "--hidden-import",
        "comtypes.gen.UIAutomationClient",
        "--exclude-module",
        "PySide6.QtWebEngineCore",
        "--exclude-module",
        "PySide6.QtWebEngineQuick",
        "--exclude-module",
        "PySide6.QtQuick3D",
        "--exclude-module",
        "PySide6.QtPdf",
        "--exclude-module",
        "comtypes.test",
        "--collect-all",
        "psutil",
        "--collect-all",
        "sounddevice",
        "--collect-all",
        "cffi",
        "--collect-all",
        "pycaw",
        "--add-data",
        f"{HOST / 'qml'};qml",
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
    hifi_pack = HOST / "hificable" / "pack"
    hifi_zip = HOST / "hificable" / "HiFiCableAsioBridgeSetup_v1007.zip"
    if hifi_pack.is_dir() or hifi_zip.is_file():
        dest_hifi = DIST / "hificable"
        dest_hifi_pack = dest_hifi / "pack"
        dest_hifi_pack.mkdir(parents=True, exist_ok=True)
        if hifi_pack.is_dir():
            for item in sorted(hifi_pack.iterdir()):
                if item.is_file():
                    cmd.extend(["--add-data", f"{item};hificable"])
                    (dest_hifi_pack / item.name).write_bytes(item.read_bytes())
        if hifi_zip.is_file():
            cmd.extend(["--add-data", f"{hifi_zip};hificable"])
            (dest_hifi / hifi_zip.name).write_bytes(hifi_zip.read_bytes())
        hifi_notice = HOST / "hificable" / "NOTICE.txt"
        if hifi_notice.is_file():
            cmd.extend(["--add-data", f"{hifi_notice};hificable"])
            (dest_hifi / "NOTICE.txt").write_bytes(hifi_notice.read_bytes())
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
    print("Building", latest)
    subprocess.check_call(cmd)
    if not built.is_dir():
        print("PyInstaller did not write", built)
        return 1
    slim_host_dir(built)
    try:
        if old_onefile.is_file():
            old_onefile.unlink()
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(built, latest)
        print("Wrote", latest / f"{name}.exe")
    except OSError as exc:
        print("Current host folder is in use, left", built, ":", exc)
        print("请先退出上位机，再把该目录复制到", latest)
        return 1
    if not args.no_commit:
        commit_usable_version(version, args.message or "host EXE snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
