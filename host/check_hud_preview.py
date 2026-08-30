#!/usr/bin/env python3
"""Assert HUD preview scales into a resized canvas."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hud_preview


def main() -> None:
    scale, w, h, ox, oy = hud_preview._hud_fit(800, 480)
    assert abs(scale - 1.0) < 1e-9 and ox == 0 and oy == 0 and w == 800 and h == 480
    scale, w, h, ox, oy = hud_preview._hud_fit(1600, 960)
    assert abs(scale - 2.0) < 1e-9 and ox == 0 and oy == 0
    scale, w, h, ox, oy = hud_preview._hud_fit(1600, 480)
    assert abs(scale - 1.0) < 1e-9 and abs(ox - 400) < 1e-9 and oy == 0
    scale, w, h, ox, oy = hud_preview._hud_fit(800, 960)
    assert abs(scale - 1.0) < 1e-9 and ox == 0 and abs(oy - 240) < 1e-9
    src = Path(hud_preview.__file__).read_text(encoding="utf-8")
    assert "resizable(False, False)" not in src
    print("ok")


if __name__ == "__main__":
    main()
