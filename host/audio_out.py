"""Play received PCM into a Windows virtual-cable playback device (WeChat microphone)."""
from __future__ import annotations

import array
import math
import queue
import threading

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None


# Play INTO these output devices so the matching recording endpoint becomes a mic.
PREFERRED_OUTPUTS = (
    "cable input",
)


class AudioSink:
    def __init__(self) -> None:
        self.sample_rate = 48000
        self.out_rate = 44100
        self.in_channels = 1
        self.out_channels = 1
        self.device: int | None = None
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self._pending = bytearray()
        self._stream = None
        self._lock = threading.Lock()
        self.underruns = 0
        self.peak = 0.0
        self.gain = 1.0
        self.callback_error = ""
        self.device_name = ""
        self._dtype = "int16"

    def available(self) -> bool:
        return sd is not None

    def list_inject_outputs(self) -> list[tuple[int, str]]:
        ranked = self._ranked_outputs()
        return [(index, name) for index, name, _score in ranked if _score > 0]

    def preferred_device(self) -> int | None:
        ranked = self._ranked_outputs()
        return ranked[0][0] if ranked and ranked[0][2] > 0 else None

    def _ranked_outputs(self) -> list[tuple[int, str, int]]:
        if sd is None:
            return []
        try:
            hostapis = list(sd.query_hostapis())
        except Exception:
            hostapis = []
        ranked: list[tuple[int, str, int]] = []
        for index, info in enumerate(sd.query_devices()):
            max_out = int(info.get("max_output_channels") or 0)
            if max_out <= 0:
                continue
            name = str(info.get("name") or f"device-{index}")
            api = ""
            api_index = int(info.get("hostapi") or 0)
            if 0 <= api_index < len(hostapis):
                api = str(hostapis[api_index].get("name") or "")
            score = _score_inject_output(name, api, max_out)
            if score > 0:
                ranked.append((index, f"{name}  [{api}]", score))
        ranked.sort(key=lambda item: item[2], reverse=True)
        return ranked

    def configure(self, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.in_channels = max(1, channels)

    def start(self, device: int | None) -> None:
        self.stop()
        if sd is None:
            raise RuntimeError("未安装 sounddevice，请先: pip install -r host/requirements.txt")
        if device is None:
            raise RuntimeError("没有可用的虚拟麦克风播放端（LX04 注入 / CABLE Input）")
        info = sd.query_devices(device)
        max_out = int(info.get("max_output_channels") or 0)
        if max_out <= 0:
            raise RuntimeError("选中的设备不能播放")
        self.device = device
        self.device_name = str(info.get("name") or f"device-{device}")
        native_rate = int(info.get("default_samplerate") or self.sample_rate)
        cable = "cable input" in self.device_name.lower()
        api = ""
        try:
            api = str(sd.query_hostapis()[int(info.get("hostapi") or 0)].get("name") or "")
        except Exception:
            pass
        extra = None
        if "WASAPI" in api:
            try:
                extra = sd.WasapiSettings(exclusive=False, auto_convert=True)
            except Exception:
                extra = None
        channels = 2 if max_out >= 2 else 1
        if cable:
            rate = 48000
        else:
            rate = native_rate or 48000
        attempts: list[tuple[str, int, int, object]] = []
        if extra is not None:
            attempts.append(("int16", channels, rate, extra))
            attempts.append(("float32", channels, rate, extra))
        attempts.append(("int16", channels, rate, None))
        if rate != native_rate and native_rate > 0:
            attempts.append(("int16", channels, native_rate, extra if extra is not None else None))
        if channels > 1:
            attempts.append(("int16", 1, rate, None))
        last_error: Exception | None = None
        self._queue = queue.Queue(maxsize=32)
        self._pending = bytearray()
        self.underruns = 0
        self.callback_error = ""
        for dtype, ch, sr, settings in attempts:
            kwargs = dict(
                samplerate=sr,
                channels=ch,
                dtype=dtype,
                device=device,
                blocksize=max(int(sr * 0.02), 1),
                callback=self._callback,
            )
            if settings is not None:
                kwargs["extra_settings"] = settings
            try:
                stream = sd.RawOutputStream(**kwargs)
                stream.start()
                self._stream = stream
                self._dtype = dtype
                self.out_channels = ch
                self.out_rate = sr
                return
            except Exception as exc:
                last_error = exc
        raise RuntimeError("无法打开 CABLE Input") from last_error

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

    def running(self) -> bool:
        stream = self._stream
        return stream is not None and bool(getattr(stream, "active", False))

    def push(self, pcm: bytes, muted: bool = False) -> None:
        if muted:
            pcm = b"\x00" * len(pcm)
        else:
            pcm = apply_gain(pcm, self.gain)
        pcm = to_output_format(pcm, self.in_channels, self.out_channels)
        pcm = resample_int16(pcm, self.sample_rate, self.out_rate, self.out_channels)
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

    def play_test_tone(self, seconds: float = 0.6, freq: float = 880.0) -> None:
        if not self.running():
            raise RuntimeError("还没有打开虚拟麦克风")
        frames = int(self.out_rate * seconds)
        mono = array.array("h")
        for index in range(frames):
            mono.append(int(12000 * math.sin(2.0 * math.pi * freq * index / self.out_rate)))
        pcm = to_output_format(mono.tobytes(), 1, self.out_channels)
        chunk = max(self.out_rate // 50, 1) * self.out_channels * 2
        for offset in range(0, len(pcm), chunk):
            try:
                self._queue.put_nowait(pcm[offset : offset + chunk])
            except queue.Full:
                break

    def _callback(self, outdata, frames, time_info, status) -> None:  # noqa: ANN001
        try:
            if status:
                self.callback_error = str(status)
            need_i16 = frames * self.out_channels * 2
            while len(self._pending) < need_i16:
                try:
                    self._pending.extend(self._queue.get_nowait())
                except queue.Empty:
                    break
            if len(self._pending) < need_i16:
                self.underruns += 1
                data = bytes(self._pending) + b"\x00" * (need_i16 - len(self._pending))
                self._pending.clear()
            else:
                data = bytes(self._pending[:need_i16])
                del self._pending[:need_i16]
            if self._dtype == "float32":
                converted = _i16_to_f32_bytes(data)
                memoryview(outdata)[: len(converted)] = converted
            else:
                memoryview(outdata)[:need_i16] = data
        except Exception as exc:
            self.callback_error = repr(exc)


def _score_inject_output(name: str, api: str, max_out: int) -> int:
    lowered = name.lower()
    if "WDM-KS" in api or ("WDM" in api and "KS" in api):
        return 0
    if "16ch" in lowered or "16 ch" in lowered or "vb-audio point" in lowered:
        return 0
    if "cable output" in lowered:
        return 0
    if "cable input" not in lowered:
        return 0
    score = 50
    if "WASAPI" in api:
        score += 40
    elif "DirectSound" in api:
        score += 15
    if max_out == 2:
        score += 20
    elif max_out > 2:
        score -= 20
    return score


def resample_int16(pcm: bytes, in_rate: int, out_rate: int, channels: int) -> bytes:
    if not pcm or in_rate == out_rate or in_rate <= 0 or out_rate <= 0:
        return pcm
    if len(pcm) % 2:
        pcm = pcm[: len(pcm) - 1]
        if not pcm:
            return pcm
    channels = max(1, channels)
    samples = array.array("h")
    samples.frombytes(pcm)
    frames_in = len(samples) // channels
    if frames_in <= 1:
        return pcm
    frames_out = max(1, int(frames_in * out_rate / in_rate))
    out = array.array("h")
    scale = (frames_in - 1) / max(1, frames_out - 1)
    for index in range(frames_out):
        src = index * scale
        left = int(src)
        frac = src - left
        right = left + 1 if left + 1 < frames_in else left
        for channel in range(channels):
            a = samples[left * channels + channel]
            b = samples[right * channels + channel]
            out.append(int(a + (b - a) * frac))
    return out.tobytes()


def to_output_format(pcm: bytes, in_channels: int, out_channels: int) -> bytes:
    if not pcm:
        return pcm
    if len(pcm) % 2:
        pcm = pcm[: len(pcm) - 1]
        if not pcm:
            return pcm
    in_channels = max(1, in_channels)
    out_channels = max(1, out_channels)
    if in_channels == out_channels:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm)
    out = array.array("h")
    if in_channels == 1 and out_channels > 1:
        for sample in samples:
            for _ in range(out_channels):
                out.append(sample)
        return out.tobytes()
    frames = len(samples) // in_channels
    for frame in range(frames):
        left = samples[frame * in_channels]
        right = samples[frame * in_channels + 1] if in_channels > 1 else left
        mixed = int((left + right) / 2)
        if out_channels == 1:
            out.append(mixed)
        else:
            out.append(left)
            out.append(right)
            for _ in range(out_channels - 2):
                out.append(mixed)
    return out.tobytes()


def _i16_to_f32_bytes(pcm: bytes) -> bytes:
    samples = array.array("h")
    samples.frombytes(pcm)
    out = array.array("f")
    scale = 1.0 / 32768.0
    for sample in samples:
        out.append(sample * scale)
    return out.tobytes()


def apply_gain(pcm: bytes, gain: float) -> bytes:
    if not pcm or abs(gain - 1.0) < 0.001:
        return pcm
    if len(pcm) % 2:
        pcm = pcm[: len(pcm) - 1]
        if not pcm:
            return pcm
    if gain <= 0:
        return b"\x00" * len(pcm)
    samples = array.array("h")
    samples.frombytes(pcm)
    for i, sample in enumerate(samples):
        value = int(sample * gain)
        if value > 32767:
            value = 32767
        elif value < -32768:
            value = -32768
        samples[i] = value
    return samples.tobytes()


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
