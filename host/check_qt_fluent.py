#!/usr/bin/env python3
"""Fail if Qt's built-in FluentWinUI3 style cannot load the host QML."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from qt_ui import HostBridge, HudEditor, QtLoop, apply_fluent_style, bind_qml_assets, qml_dir, register_hud_types


def main() -> None:
    pack = (HERE.parent / "build_host_exe.py").read_text(encoding="utf-8")
    assert '"--onedir"' in pack and '"--onefile"' not in pack
    apply_fluent_style()
    app = QApplication.instance() or QApplication([])
    apply_fluent_style()
    assert QQuickStyle.name() == "FluentWinUI3", QQuickStyle.name()
    loop = QtLoop()
    hit: list[int] = []
    threading.Thread(target=lambda: loop.after(0, lambda: hit.append(1)), daemon=True).start()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not hit:
        app.processEvents()
        time.sleep(0.01)
    assert hit, "QtLoop.after from a worker thread must run on the GUI loop"
    bridge = HostBridge()
    assert bridge.deviceModel.rowCount() == 0
    assert bridge.diagUsb == "off" and bridge.diagAdb == "off"
    from pc_host import _log_level
    from qt_ui import _fmt_rate
    assert _log_level("连接失败: boom") == "ERROR"
    assert _log_level("警告：串音") == "WARN"
    assert _log_level("USB 设备: 无") == "INFO"
    assert _fmt_rate(2048).endswith("KB/s")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("host", bridge)
    bind_qml_assets(engine)
    register_hud_types()
    qml = qml_dir() / "Main.qml"
    engine.load(str(qml))
    roots = engine.rootObjects()
    assert roots, qml
    win = roots[0]
    font = win.property("font")
    assert font is not None and ("YaHei" in font.family() or "雅黑" in font.family()), font.family() if font else None
    assert bool(win.property("navOpen")) is True
    win.setProperty("navOpen", False)
    app.processEvents()
    assert bool(win.property("navOpen")) is False
    assert win.findChild(QObject, "navToggle") is not None
    assert win.findChild(QObject, "aboutPage") is not None
    assert win.findChild(QObject, "aboutLicense") is not None
    assert win.findChild(QObject, "installPanel") is not None
    assert win.findChild(QObject, "installVbStatus") is not None
    assert win.findChild(QObject, "installHifiStatus") is not None
    assert win.findChild(QObject, "installAfterStatus") is not None
    assert win.findChild(QObject, "diagBox") is not None
    assert win.findChild(QObject, "previewBox") is not None
    assert win.findChild(QObject, "logFilter") is not None
    area = win.findChild(QObject, "logArea")
    assert area is not None
    bridge.logLine.emit("12:00:00  INFO  hello-log")
    app.processEvents()
    assert "hello-log" in str(area.property("text") or "")
    assert win.findChild(QObject, "micMeter") is not None
    assert bridge.diagUsb == "off"
    assert bridge.diagVb == "off"
    assert bridge.diagHifi == "off"
    assert bridge.diagAfter == "off"
    assert bridge.installOkCount == 0
    assert win.findChild(QObject, "installVbStatus").property("text") == "未检测"
    bridge.refresh_diag()
    app.processEvents()
    assert bridge.diagVb in ("ok", "warn")
    assert bridge.diagHifi in ("ok", "warn")
    assert bridge.diagAfter in ("ok", "warn")
    assert 0 <= bridge.installOkCount <= 3
    note = "已安装" if bridge.diagVb == "ok" else "未安装"
    assert win.findChild(QObject, "installVbStatus").property("text") == note
    assert bridge.statCpu == ""
    assert win.findChild(QObject, "usbBox") is not None
    assert win.property("scrollTick") == 0
    from PySide6.QtCore import QMetaObject, Qt
    QMetaObject.invokeMethod(win, "noteScroll", Qt.ConnectionType.DirectConnection)
    app.processEvents()
    assert int(win.property("scrollTick") or 0) >= 1
    box = win.findChild(QObject, "usbBox")
    assert box is not None
    app.processEvents()
    assert int(box.property("count") or 0) == 0
    bridge.set_labels("device", ["SERIAL-1", "SERIAL-2"])
    app.processEvents()
    assert list(bridge.deviceModel.stringList()) == ["SERIAL-1", "SERIAL-2"]
    assert int(box.property("count") or 0) == 2, box.property("count")
    win.close()
    register_hud_types()
    editor = HudEditor()
    engine.rootContext().setContextProperty("hud", editor)
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtCore import QUrl
    hud_qml = qml_dir() / "HudPreview.qml"
    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(hud_qml)))
    assert comp.status() == QQmlComponent.Status.Ready, comp.errorString()
    hudwin = comp.create(engine.rootContext())
    assert hudwin is not None, comp.errorString()
    hudwin.setWidth(1100)
    hudwin.setHeight(720)
    app.processEvents()
    view = hudwin.findChild(QObject, "hudView")
    assert view is not None
    assert view.property("editor") is not None
    assert float(view.property("height") or 0) >= 160
    hudwin.close()
    editor.closePreview()
    print("ok", QQuickStyle.name(), qml)


if __name__ == "__main__":
    main()
