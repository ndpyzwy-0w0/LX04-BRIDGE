"""Fail if checkbox commands go back to blocking the Tk thread."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hw_capture
import pc_host


def main() -> None:
    start = inspect.getsource(hw_capture.HardwareMic.start)
    assert "killall" not in start, "tinycap start must not killall again; stop() already does"
    mic = inspect.getsource(pc_host.HostApp._on_mic_route_change)
    spk = inspect.getsource(pc_host.HostApp._on_spk_route_change)
    light = inspect.getsource(pc_host.HostApp._on_light_theme_change)
    send = inspect.getsource(pc_host.BridgeClient.send_control)
    assert "_after_paint" in mic and "_after_paint" in spk and "_after_paint" in light
    assert "_apply_mic_route" not in mic
    init = inspect.getsource(pc_host.HostApp.__init__)
    assert "_boot" in init
    assert "refresh_devices" not in init
    assert "tidy_cable" not in init
    main_src = inspect.getsource(pc_host.main)
    assert "_on_close" in main_src
    close = inspect.getsource(pc_host.HostApp._on_close)
    assert "withdraw" in close
    print("ok")


if __name__ == "__main__":
    main()
