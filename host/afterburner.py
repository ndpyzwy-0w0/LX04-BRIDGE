"""Open the official MSI Afterburner page, or launch a copy already on this PC.

Afterburner is not bundled: MSI forbids redistributing it with other software.
This host only reads MAHM shared memory when Afterburner is already running.
"""
from __future__ import annotations

import os
import webbrowser
import winreg
from pathlib import Path

OFFICIAL_URL = "https://www.msi.com/Landing/afterburner"

DOWNLOAD_TEXT = (
    "音箱上的 CPU 封装温度是可选的，需要本机开着 MSI Afterburner。\n"
    "本程序不能内置 Afterburner（官方禁止随其它软件分发）。\n\n"
    "将打开 MSI 官网下载页：\n"
    f"{OFFICIAL_URL}\n\n"
    "请只从官网安装。装好后启动 Afterburner，再连音箱。\n"
    "GPU 温度走显卡驱动，不需要它。"
)

LAUNCH_TEXT = (
    "本机已安装 MSI Afterburner。\n"
    "启动后，音箱才会显示 CPU 温度（可选，不影响桥接和 GPU 温度）。\n\n"
    "现在打开它？"
)

RUNNING_TEXT = (
    "Afterburner 已在运行。连接音箱并打开「音箱显示电脑状态」后，"
    "屏幕上会出现 CPU 温度。"
)


def present() -> bool:
    return find_exe() is not None


def sensors_live() -> bool:
    try:
        import pc_stats
    except Exception:
        return False
    return bool(pc_stats.mahm_live())


def find_exe() -> Path | None:
    seen: set[str] = set()
    for candidate in _common_exes() + _registry_exes():
        exe = _as_afterburner_exe(candidate)
        if exe is None:
            continue
        try:
            path = exe.resolve()
        except OSError:
            path = exe
        key = str(path).lower()
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        return path
    return None


def _as_afterburner_exe(path: Path) -> Path | None:
    if path.is_dir():
        exe = path / "MSIAfterburner.exe"
        return exe if exe.is_file() else None
    name = path.name.lower()
    if name == "msiafterburner.exe" and path.is_file():
        return path
    sibling = path.parent / "MSIAfterburner.exe"
    if sibling.is_file():
        return sibling
    return None


def launch(exe: Path | None = None) -> str:
    path = exe or find_exe()
    if path is None:
        return "未找到已安装的 Afterburner。"
    try:
        os.startfile(str(path))
    except OSError as exc:
        return "无法启动 Afterburner: " + str(exc)
    return "已启动 Afterburner。等一两秒后，音箱会显示 CPU 温度。"


def open_download() -> str:
    try:
        opened = webbrowser.open(OFFICIAL_URL, new=2)
    except Exception as exc:
        return "无法打开浏览器: " + str(exc)
    if not opened:
        return "请手动打开 " + OFFICIAL_URL
    return "已打开 MSI Afterburner 官网。装好并启动后再连音箱。"


def _common_exes() -> list[Path]:
    names = ("MSI Afterburner",)
    exe = "MSIAfterburner.exe"
    out: list[Path] = []
    for env in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432"):
        root = os.environ.get(env)
        if root:
            for folder in names:
                out.append(Path(root) / folder / exe)
    out.append(Path(r"C:\Program Files (x86)\MSI Afterburner") / exe)
    out.append(Path(r"C:\Program Files\MSI Afterburner") / exe)
    return out


def _registry_exes() -> list[Path]:
    hives = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    found: list[Path] = []
    for hive, key in hives:
        try:
            root = winreg.OpenKey(hive, key)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(root)[0]
            for i in range(count):
                try:
                    name = winreg.EnumKey(root, i)
                    with winreg.OpenKey(root, name) as sub:
                        found.extend(_exe_from_uninstall(sub))
                except OSError:
                    continue
        finally:
            winreg.CloseKey(root)
    return found


def _exe_from_uninstall(key) -> list[Path]:
    try:
        display = str(winreg.QueryValueEx(key, "DisplayName")[0])
    except OSError:
        return []
    lowered = display.lower()
    if "afterburner" not in lowered:
        return []
    out: list[Path] = []
    for value_name in ("InstallLocation", "DisplayIcon"):
        try:
            raw = str(winreg.QueryValueEx(key, value_name)[0])
        except OSError:
            continue
        path = _path_from_reg(raw)
        if path is None:
            continue
        if path.is_dir():
            exe = path / "MSIAfterburner.exe"
            if exe.is_file():
                out.append(exe)
        elif path.is_file():
            out.append(path)
    return out


def _path_from_reg(raw: str) -> Path | None:
    text = raw.strip().strip('"')
    if "," in text:
        head, tail = text.rsplit(",", 1)
        if tail.strip().lstrip("-").isdigit():
            text = head.strip().strip('"')
    if not text:
        return None
    return Path(text)
