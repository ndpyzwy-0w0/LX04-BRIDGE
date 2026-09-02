#!/usr/bin/env python3
"""Fail if host system-rotation wiring drifts off the Android user_rotation API."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import adb_usb
import pc_host
from qt_ui import HostBridge


def main() -> None:
    assert adb_usb.ROTATION_LABELS == ("0°", "90°", "180°", "270°")
    assert adb_usb.clamp_rotation(0) == 0
    assert adb_usb.clamp_rotation(2) == 2
    assert adb_usb.clamp_rotation(4) == 0
    assert adb_usb.clamp_rotation(-1) == 3
    assert adb_usb.clamp_rotation("3") == 3
    assert adb_usb.clamp_rotation("nope") == 0
    assert adb_usb.clamp_rotation(None) == 0
    src = inspect.getsource(adb_usb.set_user_rotation)
    assert "accelerometer_rotation 0" in src
    assert "user_rotation" in src
    host_src = inspect.getsource(pc_host.HostApp._on_sys_rotation_change)
    assert "_after_paint" in host_src
    save = inspect.getsource(pc_host.HostApp._save_routes)
    assert "sys_rotation" in save
    load = inspect.getsource(pc_host.HostApp._load_route_vars)
    assert "sys_rotation" in load
    push = inspect.getsource(pc_host.HostApp._push_sys_rotation)
    assert 'send_control("sys_rotation"' in push or "send_control('sys_rotation'" in push
    assert "set_user_rotation" in push
    connect = inspect.getsource(pc_host.HostApp)
    assert "_push_sys_rotation" in connect
    qt_src = inspect.getsource(HostBridge.setRotationIndex)
    assert "sys_rotation" in qt_src
    ui = (HERE / "qt_ui.py").read_text(encoding="utf-8")
    assert "0°" in ui and "270°" in ui
    qml = (HERE / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "sysRotationRow" in qml
    assert "setRotationIndex" in qml
    java = (HERE.parent / "app" / "src" / "main" / "java" / "com" / "lx04" / "pcbridge" / "BridgeService.java").read_text(encoding="utf-8")
    assert "USER_ROTATION" in java
    assert "sys_rotation" in java
    print("ok")


if __name__ == "__main__":
    main()
