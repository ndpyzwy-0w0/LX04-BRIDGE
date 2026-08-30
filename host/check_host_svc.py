"""Assert host_svc answers ping + snapshot. No speaker required."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parent


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
    ready = json.loads(proc.stdout.readline())
    assert ready.get("event") == "ready", ready
    assert "connected" in (ready.get("data") or {}), ready
    proc.stdin.write(json.dumps({"id": 1, "method": "ping"}) + "\n")
    proc.stdin.flush()
    pong = json.loads(proc.stdout.readline())
    assert pong.get("id") == 1 and pong.get("result", {}).get("ok"), pong
    proc.stdin.write(json.dumps({"id": 2, "method": "snapshot"}) + "\n")
    proc.stdin.flush()
    snap = json.loads(proc.stdout.readline())
    assert snap.get("id") == 2
    data = snap.get("result") or {}
    assert "diagnostics" in data and "devices" in data, data
    proc.stdin.write(json.dumps({"id": 3, "method": "shutdown"}) + "\n")
    proc.stdin.flush()
    proc.stdin.close()
    proc.wait(timeout=20)
    print("host_svc ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
