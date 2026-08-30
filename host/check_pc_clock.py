"""Fail if the host stops sending PC wall-clock fields to the speaker HUD."""
from __future__ import annotations

import time
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pc_stats


def main() -> None:
    fields = pc_stats.clock_fields()
    assert isinstance(fields["now"], int)
    assert isinstance(fields["tz"], int)
    assert abs(fields["now"] - int(time.time() * 1000)) < 2000
    snap = pc_stats.snapshot()
    assert snap.get("now")
    assert "tz" in snap
    print("ok")


if __name__ == "__main__":
    main()
