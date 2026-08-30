#!/usr/bin/env python3
"""Assert host window metrics stay inside the current screen."""
from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from pc_host import _ui_metrics


def main() -> None:
    fhd = _ui_metrics(1920, 1080, 96)
    assert 700 <= int(fhd["w"]) <= 1100, fhd
    assert 500 <= int(fhd["h"]) <= 800, fhd
    laptop = _ui_metrics(1280, 720, 96)
    assert int(laptop["w"]) <= 1280 - 32 and int(laptop["h"]) <= 720 - 48, laptop
    fourk = _ui_metrics(3840, 2160, 192)
    assert int(fourk["font"]) >= int(fhd["font"]), (fourk, fhd)
    assert int(fourk["w"]) >= int(fhd["w"]), (fourk, fhd)
    tiny = _ui_metrics(1024, 600, 96)
    assert int(tiny["w"]) <= 1024 and int(tiny["h"]) <= 600, tiny
    assert int(tiny["font"]) >= 9
    print("ok", fhd, laptop, fourk, tiny)


if __name__ == "__main__":
    main()
