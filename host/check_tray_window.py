"""Fail if withdraw/show cannot bring a Qt host window back."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from PySide6.QtWidgets import QApplication, QWidget

import pc_host


def main() -> None:
    app = QApplication.instance() or QApplication([])
    w = QWidget()
    w.setWindowTitle("LX04 上位机")
    w.resize(240, 80)
    w.show()
    app.processEvents()
    assert w.isVisible()
    w.hide()
    app.processEvents()
    assert not w.isVisible()
    pc_host._show_host_window(w)
    app.processEvents()
    assert w.isVisible(), w.isVisible()
    w.close()
    print("ok")


if __name__ == "__main__":
    main()
