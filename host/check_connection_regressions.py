"""Check partial reads and cancelled connects without loading Windows audio/UI."""
from __future__ import annotations

import ast
import socket
import threading
from pathlib import Path
from types import SimpleNamespace


def main() -> None:
    tree = ast.parse(Path(__file__).with_name("pc_host.py").read_text(encoding="utf-8-sig"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HostApp")
    clock = SimpleNamespace(now=0.0)
    env = {"socket": socket, "time": SimpleNamespace(monotonic=lambda: clock.now),
           "threading": threading}
    names = {"connect", "disconnect", "_connect_done", "_connect_failed", "_cancel_connect"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_read_exact_idle"]
    nodes += [n for n in host.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pc_host.py", "exec"), env)

    class Stream:
        def __init__(self, pieces):
            self.pieces = iter(pieces)

        def recv(self, size):
            clock.now += 2
            piece = next(self.pieces)
            if piece is None:
                raise socket.timeout()
            return piece

    read = env["_read_exact_idle"]
    assert read(Stream([None]), 3) is None
    assert read(Stream([b"L", None, b"XB"]), 3) == b"LXB"
    # Continuous progress must reset the inactivity deadline.
    assert read(Stream([b"L", None, b"X", None, b"B"]), 3, max_idle=5) == b"LXB"
    try:
        read(Stream([b"L"] + [None] * 16), 3)
    except ConnectionError:
        pass
    else:
        raise AssertionError("A stalled partial frame must disconnect")
    try:
        read(Stream([b"L", b""]), 3)
    except ConnectionError:
        pass
    else:
        raise AssertionError("EOF during a frame must disconnect")

    events = []
    queued = []
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def shutdown():
        started.set()
        assert release.wait(3)
        events.append("closed")

    def ui(fn):
        queued.append(fn)
        finished.set()

    label = SimpleNamespace(configure=lambda **kw: None)
    app = SimpleNamespace(
        _connecting=True, _connect_cancelled=False, _closing=False,
        _session=False, connected=False, _xiaoai_idle=False,
        headline=label, detail=label, _start_session=lambda: events.append("started"),
        _link_label=lambda: "WiFi", _log=lambda text: None,
        _shutdown_work=shutdown, _ui=ui,
        bridge=SimpleNamespace(connectedChanged=SimpleNamespace(emit=lambda: None)),
    )
    app._cancel_connect = lambda: env["_cancel_connect"](app)
    # Keep the thread controllable so disconnect queues its first cleanup.
    workers = []
    class QueuedThread:
        def __init__(self, target, **kwargs):
            workers.append(target)
        def start(self):
            pass

    app._stop_xiaoai_watch = lambda: None
    app._draw_meter = lambda *args: None
    env["threading"] = SimpleNamespace(Thread=QueuedThread)
    env["disconnect"](app)
    assert app._connect_cancelled and not app._session and not app.connected
    assert len(workers) == 1
    env["threading"] = threading

    env["_connect_done"](app, "speaker", "late completion")
    assert started.wait(3)
    assert app._connecting and not app.connected and not app._session
    assert "started" not in events
    env["connect"](app)  # Must not start a new connection during cleanup.
    assert app._connect_cancelled
    release.set()
    assert finished.wait(3)
    queued.pop()()
    assert not app._connecting and events == ["closed"]

    # A cancelled failure must not display an error or overwrite the UI.
    app._connecting = True
    app._cancel_connect = lambda: events.append("cancelled failure")
    env["_connect_failed"](app, RuntimeError("late failure"))
    assert events[-1] == "cancelled failure"
    app._connect_cancelled = False
    app._closing = True
    env["_connect_done"](app, "speaker", "completion after exit")
    assert not app.connected and "started" not in events

    app._closing = False
    env["_connect_done"](app, "speaker", "normal completion")
    assert app.connected and app._session and events[-1] == "started"
    print("Partial reads and connection cancellation: all checks passed")


if __name__ == "__main__":
    main()
