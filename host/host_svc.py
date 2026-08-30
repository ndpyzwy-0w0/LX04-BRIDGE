#!/usr/bin/env python3
"""JSON-line worker for the WinUI host shell."""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import Future
from pathlib import Path

HOST_DIR = Path(__file__).resolve().parent
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

from host_controller import HostController

_out_lock = threading.Lock()
_pending: dict[str, Future] = {}
_pending_lock = threading.Lock()
_ids = 0


def _write(payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False, default=str)
    with _out_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def _wait(kind: str, text: str = "", timeout: float = 300.0):
    global _ids
    with _pending_lock:
        _ids += 1
        token = f"{kind}-{_ids}"
        fut: Future = Future()
        _pending[token] = fut
    _write({"event": kind, "id": token, "text": text})
    try:
        return fut.result(timeout=timeout)
    except Exception:
        return None
    finally:
        with _pending_lock:
            _pending.pop(token, None)


def _finish(token: str, value) -> None:
    with _pending_lock:
        fut = _pending.get(token)
    if fut is not None and not fut.done():
        fut.set_result(value)


def _ui_post(app: HostController):
    def post(fn) -> None:
        try:
            fn()
        except Exception as exc:
            _write({"event": "log", "line": "UI 回调失败: " + str(exc), "level": "ERROR"})

    return post


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    def emit(payload: dict) -> None:
        if isinstance(payload, dict):
            _write(payload)

    app = HostController(
        None,
        emit=emit,
        ui_post=lambda fn: _ui_post(app)(fn),
        confirm=lambda text: bool(_wait("confirm", text)),
        ask_file=lambda: _wait("pick_file"),
        ask_slot=lambda: _wait("pick_slot"),
    )
    _write({"event": "ready", "data": app.snapshot()})

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _write({"event": "error", "text": "bad json"})
            continue
        if not isinstance(msg, dict):
            continue
        mid = msg.get("id")
        method = str(msg.get("method") or "")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        try:
            result = _dispatch(app, method, params)
            if mid is not None:
                _write({"id": mid, "result": result})
        except Exception as exc:
            if mid is not None:
                _write({"id": mid, "error": str(exc)})
            else:
                _write({"event": "error", "text": str(exc)})
        if method == "shutdown":
            break
    app.shutdown()
    return 0


def _dispatch(app: HostController, method: str, params: dict):
    if method in {"", "ping"}:
        return {"ok": True}
    if method == "snapshot":
        return app.snapshot()
    if method == "refresh":
        app.refresh_devices()
        return app.snapshot()
    if method == "connect":
        app.connect(str(params.get("serial") or "") or None)
        return app.snapshot()
    if method == "disconnect":
        app.disconnect()
        return app.snapshot()
    if method == "set":
        app.apply_setting(str(params.get("key") or ""), params.get("value"))
        return app.snapshot()
    if method == "gain":
        app.set_gain(float(params.get("value") or 100))
        return app.snapshot()
    if method == "mute_mic":
        app.toggle_mic_mute()
        return {"ok": True}
    if method == "mute_spk":
        app.toggle_spk_mute()
        return {"ok": True}
    if method == "test_tone":
        app._on_test_tone()
        return {"ok": True}
    if method == "speaker_test":
        app._on_speaker_test_tone()
        return {"ok": True}
    if method == "install_vb":
        app._install_vb()
        return app.snapshot()
    if method == "install_hifi":
        app._install_hifi()
        return app.snapshot()
    if method == "afterburner":
        app._on_afterburner()
        return {"ok": True}
    if method == "upload_bg":
        app._upload_hud_bg(str(params.get("path") or "") or None)
        return app.snapshot()
    if method == "mirror":
        app.start_or_stop_mirror(bool(params.get("on")))
        return app.snapshot()
    if method == "hud":
        app.apply_hud(params.get("state") if isinstance(params.get("state"), dict) else None, reset=bool(params.get("reset")))
        return app.snapshot()
    if method == "diagnose":
        app.refresh_devices()
        return app.snapshot()
    if method == "answer":
        _finish(str(params.get("id") or ""), params.get("value"))
        return {"ok": True}
    if method == "shutdown":
        return {"ok": True}
    raise ValueError("unknown method: " + method)


if __name__ == "__main__":
    raise SystemExit(main())
