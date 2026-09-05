"""Detect VB-Audio Hi-Fi Cable; open the official download page if it is missing."""
from __future__ import annotations

import webbrowser

OFFICIAL_URL = "https://vb-audio.com/Cable/"

DONATE_TEXT = (
    "要把电脑里正在播放的声音接到小爱音箱，需要再装一根虚拟线："
    "VB-Audio Hi-Fi Cable（捐赠软件，和已经装的 VB-CABLE 不是同一根）。\n"
    "来源：vb-audio.com/Cable/\n"
    "本程序不附带安装包。\n\n"
    "微信麦克风仍然选「CABLE Output」，不要选 Hi-Fi Cable。\n"
    "将打开官网下载页。装完后通常需要重启电脑，再打开本程序。"
)


def is_hifi_name(name: str) -> bool:
    lowered = (name or "").lower()
    return "hi-fi cable" in lowered or "hifi cable" in lowered or "hi fi cable" in lowered


def is_hifi_render(name: str) -> bool:
    if not is_hifi_name(name):
        return False
    lowered = name.lower()
    if "output" in lowered:
        return False
    return "input" in lowered or "playback" in lowered or "播放" in name


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
    return any(is_hifi_render(name) for name in names)


def open_download() -> str:
    try:
        opened = webbrowser.open(OFFICIAL_URL, new=2)
    except Exception as exc:
        return "无法打开浏览器: " + str(exc)
    if not opened:
        return "请手动打开 " + OFFICIAL_URL
    return "已打开 Hi-Fi Cable 官网。装好并重启后再连接。"
