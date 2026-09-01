"""Fail if idle-yield debounce or host wiring regresses."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pc_host
import win_endpoint
from qt_ui import HostBridge


def main() -> None:
    g = win_endpoint.CaptureYield(idle_needed=3)
    assert g.held
    assert g.on_busy(True) is None
    assert g.on_busy(False) is None
    assert g.on_busy(False) is None
    assert g.on_busy(False) == "yield"
    assert not g.held
    assert g.on_busy(False) is None
    assert g.on_busy(True) == "grab"
    assert g.held
    assert g.on_busy(True) is None
    g.reset(False)
    assert not g.held
    assert g.on_busy(True) == "grab"
    g.reset(True)
    assert g.on_busy(False) is None
    assert g.on_busy(True) is None
    apply = inspect.getsource(pc_host.HostApp._apply_mic_route)
    assert "_yield_xiaoai_mic" in apply
    assert "_grab_xiaoai_mic" in apply
    assert "xiaoai_yield" in apply
    connect = inspect.getsource(pc_host.HostApp.connect)
    assert "take_speaker_mic" not in connect
    revive = inspect.getsource(pc_host.HostApp._revive_worker)
    assert "_xiaoai_held" in revive
    revived = inspect.getsource(pc_host.HostApp._on_revived)
    assert "start_mic" not in revived
    assert "_apply_mic_route" in revived
    hello = inspect.getsource(pc_host.HostApp._handle_event)
    assert "xiaoai_idle" in hello
    save = inspect.getsource(pc_host.HostApp._save_routes)
    assert "xiaoai_yield" in save
    qml = (HERE / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert "空闲时交还小爱麦" in qml
    assert "xiaoaiYieldSwitch" in qml
    bridge = HostBridge()
    assert bridge.xiaoaiYield is False
    assert bridge.xiaoaiIdle is False
    print("ok")


if __name__ == "__main__":
    main()
