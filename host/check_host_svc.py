"""Assert host_svc answers ping + snapshot with device lists after boot."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HOST = Path(__file__).resolve().parent


def _read(proc, pred, timeout: float = 8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        msg = json.loads(line)
        if pred(msg):
            return msg
    raise AssertionError("timeout waiting for host_svc")


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(HOST / "host_svc.py")],
        cwd=str(HOST),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert proc.stdin and proc.stdout
    ready = _read(proc, lambda m: m.get("event") == "ready")
    assert "connected" in (ready.get("data") or {}), ready
    proc.stdin.write(json.dumps({"id": 1, "method": "ping"}) + "\n")
    proc.stdin.flush()
    pong = _read(proc, lambda m: m.get("id") == 1)
    assert pong.get("result", {}).get("ok"), pong
    labels = []
    deadline = time.time() + 6
    while time.time() < deadline and not labels:
        proc.stdin.write(json.dumps({"id": 2, "method": "snapshot"}) + "\n")
        proc.stdin.flush()
        snap = _read(proc, lambda m: m.get("id") == 2 or m.get("event") == "snapshot")
        data = snap.get("result") or snap.get("data") or {}
        labels = (
            data.get("injectLabels")
            or data.get("speakerLabels")
            or data.get("diskLabels")
            or data.get("monitorLabels")
            or []
        )
        if labels:
            break
        time.sleep(0.4)
    assert labels, "boot never filled dropdown labels"
    try:
        proc.stdin.write(json.dumps({"id": 3, "method": "shutdown"}) + "\n")
        proc.stdin.flush()
        proc.kill()
    except Exception:
        proc.kill()
    print("host_svc ok", labels[:2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
