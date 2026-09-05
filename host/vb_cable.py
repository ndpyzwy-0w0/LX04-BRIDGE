"""Detect VB-CABLE; open the official download page if it is missing."""
from __future__ import annotations

import webbrowser

OFFICIAL_URL = "https://www.vb-cable.com/"

DONATE_TEXT = (
    "需要安装 VB-CABLE（VB-Audio 的虚拟声卡，捐赠软件）。\n"
    "来源：www.vb-cable.com\n"
    "本程序不附带安装包。觉得好用请向作者捐赠。\n\n"
    "将打开官网下载页。请下载官方包并以管理员安装，完成后通常需要重启，再打开本程序。"
)


def present() -> bool:
    try:
        import win_endpoint
    except Exception:
        return False
    return win_endpoint.find_cable_capture() is not None and win_endpoint.find_cable_render() is not None


def open_download() -> str:
    try:
        opened = webbrowser.open(OFFICIAL_URL, new=2)
    except Exception as exc:
        return "无法打开浏览器: " + str(exc)
    if not opened:
        return "请手动打开 " + OFFICIAL_URL
    return "已打开 VB-CABLE 官网。装好并重启后再连接。"
