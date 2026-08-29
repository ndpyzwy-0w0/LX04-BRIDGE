"""Fail if speaker-dismissed toasts can be pushed back to the APK."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import toast_mirror as tm


def main() -> None:
    same = tm.ToastContent(app="Cursor", title="申请权限", body="用麦克风", hwnd=11)
    gone_btns = tm.ToastContent(app="Cursor", title="申请权限", body="用麦克风", hwnd=11)
    reincarnated = tm.ToastContent(app="Cursor", title="申请权限", body="用麦克风", hwnd=22)
    nxt = tm.ToastContent(app="Cursor", title="另一条", body="新的", hwnd=11)
    other = tm.ToastContent(app="Other", title="完成", body="好了", hwnd=33)
    key = same.text_key()
    assert tm.stale_toast(same, 11, key)
    assert tm.stale_toast(gone_btns, 11, key)
    assert tm.stale_toast(reincarnated, 11, key)
    assert not tm.stale_toast(nxt, 11, key)
    assert not tm.stale_toast(other, 11, key)
    assert not tm.stale_toast(None, 11, key)
    loop = inspect.getsource(tm.ToastSender._loop)
    hide = inspect.getsource(tm.ToastSender._hide)
    assert "stale_toast" in loop or "_blocked" in loop
    assert "_ignore_hwnd" in hide and "_ignore_key" in hide
    print("ok")


if __name__ == "__main__":
    main()
