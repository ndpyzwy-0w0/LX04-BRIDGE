#!/usr/bin/env python3
"""Fail if unused Qt payloads are not stripped from the onedir tree."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_host_exe import slim_host_dir


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        pyside = root / "_internal" / "PySide6"
        qml = pyside / "qml" / "QtWebEngine"
        controls = pyside / "qml" / "QtQuick" / "Controls" / "Imagine"
        fluent = pyside / "qml" / "QtQuick" / "Controls" / "FluentWinUI3"
        tests = root / "_internal" / "comtypes" / "test"
        trans = root / "_internal" / "PySide6" / "translations"
        for folder in (qml, controls, fluent, tests, trans):
            folder.mkdir(parents=True)
        (pyside / "Qt6WebEngineCore.dll").write_bytes(b"x")
        (pyside / "Qt6Core.dll").write_bytes(b"x")
        (pyside / "opengl32sw.dll").write_bytes(b"x")
        (fluent / "keep.qml").write_text("x", encoding="utf-8")
        (trans / "qt_de.qm").write_bytes(b"x")
        (trans / "qt_zh_CN.qm").write_bytes(b"x")
        (tests / "test_word.py").write_text("x", encoding="utf-8")
        slim_host_dir(root)
        assert not (pyside / "Qt6WebEngineCore.dll").exists()
        assert not (pyside / "opengl32sw.dll").exists()
        assert not qml.exists()
        assert not controls.exists()
        assert not tests.exists()
        assert not (trans / "qt_de.qm").exists()
        assert (pyside / "Qt6Core.dll").exists()
        assert (fluent / "keep.qml").exists()
        assert (trans / "qt_zh_CN.qm").exists()
    print("ok")


if __name__ == "__main__":
    main()
