"""Play received PCM into a Windows output device (VB-Cable = virtual microphone)."""
from __future__ import annotations

import queue
import threading

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None


PREFERRED_NAMES = (
    "cable input",
    "voicemeeter input",
    "voicemeeter aux input",
    "vb-audio",
    "virtual cable",
)


class AudioSink:
    def __init__(self) -> None:
        self.sample_rate = 48000
        self.channels = 1
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=10)
        self._pending = bytearray()
        self._stream = None
        self._lock = threading.Lock()
        self.underruns = 0
        self.peak = 0.0

    def available(self) -> bool:
        return sd is not None

    def list_outputs(self) -> list[tuple[int, str]]:
        if sd is None:
            return []
        items: list[tuple[int, str]] = []
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_output_channels") or 0) > 0:
                items.append((index, str(info.get("name") or f"device-{index}")))
        return items

    def preferred_device(self) -> int | None:
        for index, name in self.list_outputs():
            lowered = name.lower()
            if any(key in lowered for key in PREFERRED_NAMES):
                return index
        return None

    def configure(self, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.channels = max(1, channels)

    def start(self, device: int | None) -> None:
        self.stop()
        if sd is None:
            raise RuntimeError("未安装 sounddevice，请先: pip install -r host/requirements.txt")
        self._queue = queue.Queue(maxsize=10)
        self._pending = bytearray()
        self.underruns = 0
        self._stream = sd.RawOutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            device=device,
            blocksize=int(self.sample_rate * 0.02),
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def push(self, pcm: bytes, muted: bool = False) -> None:
        if muted:
            pcm = b"\x00" * len(pcm)
        self.peak = _peak(pcm)
        try:
            self._queue.put_nowait(pcm)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(pcm)
            except queue.Full:
                pass

    def _callback(self, outdata, frames, time_info, status) -> None:  # noqa: ANN001
        need = frames * self.channels * 2
        while len(self._pending) < need:
            try:
                self._pending.extend(self._queue.get_nowait())
            except queue.Empty:
                break
        if len(self._pending) < need:
            self.underruns += 1
            outdata[:] = bytes(self._pending) + b"\x00" * (need - len(self._pending))
            self._pending.clear()
            return
        outdata[:] = bytes(self._pending[:need])
        del self._pending[:need]


def _peak(pcm: bytes) -> float:
    peak = 0
    for i in range(0, len(pcm) - 1, 2):
        sample = pcm[i] | (pcm[i + 1] << 8)
        if sample >= 32768:
            sample -= 65536
        value = -sample if sample < 0 else sample
        if value > peak:
            peak = value
    return peak / 32768.0
