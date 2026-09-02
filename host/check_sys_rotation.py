#!/usr/bin/env python3
"""Fail if host rotation / hide-UI wiring drifts off 0°/180° and hide_ui."""
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
    assert adb_usb.ROTATION_LABELS == ("正向", "倒转")
    assert adb_usb.clamp_rotation(0) == 0
    assert adb_usb.clamp_rotation(1) == 0
    assert adb_usb.clamp_rotation(2) == 2
    assert adb_usb.clamp_rotation(3) == 2
    assert adb_usb.clamp_rotation(4) == 0
    assert adb_usb.clamp_rotation(-1) == 2
    assert adb_usb.clamp_rotation("3") == 2
    assert adb_usb.clamp_rotation("nope") == 0
    assert adb_usb.clamp_rotation(None) == 0
    assert adb_usb.rotation_choice(2) == 1
    assert adb_usb.rotation_label(2) == "倒转"
    src = inspect.getsource(adb_usb.set_user_rotation)
    assert "accelerometer_rotation 0" in src
    assert "user_rotation" in src
    host_src = inspect.getsource(pc_host.HostApp._on_sys_rotation_change)
    assert "_after_paint" in host_src
    save = inspect.getsource(pc_host.HostApp._save_routes)
    assert "sys_rotation" in save
    assert "ui_hidden" in save
    load = inspect.getsource(pc_host.HostApp._load_route_vars)
    assert "sys_rotation" in load
    assert "ui_hidden" in load
    push = inspect.getsource(pc_host.HostApp._push_sys_rotation)
    assert 'send_control("sys_rotation"' in push or "send_control('sys_rotation'" in push
    assert "set_user_rotation" in push
    hide = inspect.getsource(pc_host.HostApp._push_ui_hidden)
    assert 'send_control("hide_ui"' in hide or "send_control('hide_ui'" in hide
    assert "hide_bridge_ui" in hide
    assert "start_bridge_ui" in hide
    connect = inspect.getsource(pc_host.HostApp)
    assert "_push_sys_rotation" in connect
    assert "_push_ui_hidden" in connect
    qt_src = inspect.getsource(HostBridge.setRotationIndex)
    assert "sys_rotation" in qt_src
    assert "2 if int(index) else 0" in qt_src
    hide_slot = inspect.getsource(HostBridge.setUiHidden)
    assert "ui_hidden" in hide_slot
    ui = (HERE / "qt_ui.py").read_text(encoding="utf-8")
    assert "正向" in ui and "倒转" in ui
    qml = (HERE / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "sysRotationRow" in qml
    assert "setRotationIndex" in qml
    assert "uiHiddenSwitch" in qml
    java = (HERE.parent / "app" / "src" / "main" / "java" / "com" / "lx04" / "pcbridge" / "BridgeService.java").read_text(encoding="utf-8")
    assert "USER_ROTATION" in java
    assert "sys_rotation" in java
    assert "hide_ui" in java
    act = (HERE.parent / "app" / "src" / "main" / "java" / "com" / "lx04" / "pcbridge" / "MainActivity.java").read_text(encoding="utf-8")
    assert "leaveToBackground" in act
    assert "allowLeave" in act
    print("ok")


if __name__ == "__main__":
    main()
