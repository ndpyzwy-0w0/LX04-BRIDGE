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
    assert "_close_goes_to_tray" in close
    assert "minimize_to_tray" in inspect.getsource(pc_host.HostApp._save_routes)
    assert pc_host._close_goes_to_tray(False, False, True)
    assert not pc_host._close_goes_to_tray(False, True, True)
    assert not pc_host._close_goes_to_tray(True, False, True)
    menu_src = inspect.getsource(pc_host.HostApp._show_tray_menu)
    assert '"打开"' in menu_src
    menu = pc_host._user32.CreatePopupMenu()
    assert menu, "CreatePopupMenu must return a 64-bit HMENU"
    ok = pc_host._user32.AppendMenuW(menu, pc_host._MF_STRING, pc_host._TRAY_OPEN, "打开")
    pc_host._user32.DestroyMenu(menu)
    assert ok
    print("ok")


if __name__ == "__main__":
    main()
