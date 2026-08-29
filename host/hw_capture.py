"""Capture LX04 dual digital mics via tinycap over adb (AudioRecord cannot reach them)."""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from audio_out import AudioSink

CREATE_NO_WINDOW = 0x08000000
CHUNK = 960  # 10 ms of 48 kHz mono s16le


class HardwareMic:
    def __init__(self) -> None:
        self.muted = False
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._alive = False
        self.sample_rate = 48000

    def running(self) -> bool:
        return self._alive and self._proc is not None and self._proc.poll() is None

    def start(self, adb: str, serial: str, sink: AudioSink) -> None:
        self.stop(adb, serial)
        args = ["-s", serial] if serial else []
        flags = CREATE_NO_WINDOW if os.name == "nt" else 0
        cwd = str(Path(adb).resolve().parent)
        subprocess.run(
            [adb, *args, "shell", "killall tinycap >/dev/null 2>&1"],
            capture_output=True,
            timeout=4,
            creationflags=flags,
            cwd=cwd,
        )
        cmd = [
            adb,
            *args,
            "exec-out",
            "sh",
            "-c",
            "tinycap /proc/self/fd/1 -D 0 -d 1 -c 1 -r 48000 -b 16 -T 36000 2>/dev/null",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            creationflags=flags,
            cwd=cwd,
        )
        banner = _read_line(proc.stdout, timeout_bytes=8000)
        if b"Capturing" not in banner:
            proc.kill()
            raise RuntimeError("音箱硬件麦没有打开：" + banner.decode("utf-8", "replace")[:120])
        self._proc = proc
        self._alive = True
        self._thread = threading.Thread(target=self._pump, args=(proc, sink), daemon=True)
        self._thread.start()

    def stop(self, adb: str | None = None, serial: str | None = None) -> None:
        self._alive = False
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        if adb:
            args = ["-s", serial] if serial else []
            flags = CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                subprocess.run(
                    [adb, *args, "shell", "killall tinycap >/dev/null 2>&1"],
                    capture_output=True,
                    timeout=4,
                    creationflags=flags,
                    cwd=str(Path(adb).resolve().parent),
                )
            except Exception:
                pass

    def _pump(self, proc: subprocess.Popen, sink: AudioSink) -> None:
        stdout = proc.stdout
        if stdout is None:
            return
        pending = bytearray()
        try:
            while self._alive and proc.poll() is None:
                piece = stdout.read(CHUNK)
                if not piece:
                    break
                if piece.startswith(b"RIFF"):
                    continue
                pending.extend(piece)
                while len(pending) >= CHUNK:
                    pcm = bytes(pending[:CHUNK])
                    del pending[:CHUNK]
                    if sink.running():
                        sink.push(pcm, muted=self.muted)
        except Exception:
            pass
        finally:
            self._alive = False


def _read_line(stream, timeout_bytes: int = 4096) -> bytes:
    data = bytearray()
    while len(data) < timeout_bytes:
        ch = stream.read(1)
        if not ch:
            break
        data.extend(ch)
        if ch == b"\n":
            break
    return bytes(data)
