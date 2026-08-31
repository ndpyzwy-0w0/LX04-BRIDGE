#!/usr/bin/env python3
"""Fail if Qt's built-in FluentWinUI3 style cannot load the host QML."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from qt_ui import HostBridge, apply_fluent_style, qml_dir


def main() -> None:
    apply_fluent_style()
    app = QApplication.instance() or QApplication([])
    assert QQuickStyle.name() == "FluentWinUI3", QQuickStyle.name()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("host", HostBridge())
    qml = qml_dir() / "Main.qml"
    engine.load(str(qml))
    roots = engine.rootObjects()
    assert roots, qml
    roots[0].close()
    print("ok", QQuickStyle.name(), qml)


if __name__ == "__main__":
    main()
