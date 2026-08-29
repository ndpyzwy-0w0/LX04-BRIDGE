"""Capture Windows playback mix (WASAPI loopback) and emit 48 kHz stereo s16le."""
from __future__ import annotations

import array
import ctypes
import threading
import time
from ctypes import POINTER, Structure, byref, c_byte, c_uint32, c_uint64
from ctypes.wintypes import BYTE, DWORD, WORD

from audio_out import resample_int16, to_output_format

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x1
WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE
REFTIMES_PER_MS = 10_000
PLAY_RATE = 48000
PLAY_CHANNELS = 2
PACKET_FRAMES = PLAY_RATE // 100  # 10 ms


class WAVEFORMATEX(Structure):
    _fields_ = [
        ("wFormatTag", WORD),
        ("nChannels", WORD),
        ("nSamplesPerSec", DWORD),
        ("nAvgBytesPerSec", DWORD),
        ("nBlockAlign", WORD),
        ("wBitsPerSample", WORD),
        ("cbSize", WORD),
    ]


class WAVEFORMATEXTENSIBLE(Structure):
    _fields_ = [
        ("Format", WAVEFORMATEX),
        ("wValidBitsPerSample", WORD),
        ("dwChannelMask", DWORD),
        ("SubFormat_Data1", DWORD),
        ("SubFormat_Data2", WORD),
        ("SubFormat_Data3", WORD),
        ("SubFormat_Data4", ctypes.c_ubyte * 8),
    ]


class IAudioCaptureClient:
    """Filled after comtypes is imported — see _capture_client_type()."""


def _capture_client_type():
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class IAudioCaptureClientImpl(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
        _methods_ = (
            COMMETHOD(
                [],
                HRESULT,
                "GetBuffer",
                (["out"], POINTER(POINTER(BYTE)), "ppData"),
                (["out"], POINTER(c_uint32), "pNumFramesToRead"),
                (["out"], POINTER(DWORD), "pdwFlags"),
                (["out"], POINTER(c_uint64), "pu64DevicePosition"),
                (["out"], POINTER(c_uint64), "pu64QPCPosition"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "ReleaseBuffer",
                (["in"], c_uint32, "NumFramesRead"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetNextPacketSize",
                (["out"], POINTER(c_uint32), "pNumFramesInNextPacket"),
            ),
        )

    return IAudioCaptureClientImpl


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


def _is_float(fmt: WAVEFORMATEX, raw: bytes) -> bool:
    if fmt.wFormatTag == WAVE_FORMAT_IEEE_FLOAT:
        return True
    if fmt.wFormatTag == WAVE_FORMAT_EXTENSIBLE and fmt.cbSize >= 22 and len(raw) >= 40:
        # WAVEFORMATEXTENSIBLE.SubFormat.Data1 sits at offset 24.
        data1 = int.from_bytes(raw[24:28], "little")
        return data1 == WAVE_FORMAT_IEEE_FLOAT
    return False


def _mix_to_s16(raw: bytes, frames: int, channels: int, bits: int, is_float: bool) -> bytes:
    if frames <= 0 or channels <= 0:
        return b""
    out = array.array("h")
    if is_float and bits == 32:
        floats = memoryview(raw).cast("f")
        for frame in range(frames):
            for ch in range(channels):
                value = float(floats[frame * channels + ch])
                sample = int(value * 32767.0)
                if sample > 32767:
                    sample = 32767
                elif sample < -32768:
                    sample = -32768
                out.append(sample)
        return out.tobytes()
    if bits == 16 and not is_float:
        return raw[: frames * channels * 2]
    if bits == 32 and not is_float:
        for frame in range(frames):
            for ch in range(channels):
                offset = (frame * channels + ch) * 4
                sample = int.from_bytes(raw[offset : offset + 4], "little", signed=True) >> 16
                out.append(sample)
        return out.tobytes()
    if bits == 24 and not is_float:
        for frame in range(frames):
            for ch in range(channels):
                offset = (frame * channels + ch) * 3
                sample = int.from_bytes(raw[offset : offset + 3] + b"\x00", "little", signed=False)
                if sample & 0x800000:
                    sample -= 0x1000000
                out.append(sample >> 8)
        return out.tobytes()
    return b"\x00" * (frames * channels * 2)


class SpeakerLoopback:
    def __init__(self) -> None:
        self.device_id = ""
        self.device_name = ""
        self.peak = 0.0
        self.error = ""
        self.frames = 0
        self._on_pcm = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._muted = False

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def muted(self) -> bool:
        return self._muted

    @muted.setter
    def muted(self, value: bool) -> None:
        self._muted = bool(value)

    def start(self, device_id: str, device_name: str, on_pcm) -> None:
        self.stop()
        if not device_id:
            raise RuntimeError("没有可环回的播放设备")
        self.device_id = device_id
        self.device_name = device_name
        self._on_pcm = on_pcm
        self.error = ""
        self.peak = 0.0
        self.frames = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="lx04-loopback", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.5)
        self.peak = 0.0

    def _emit(self, pcm: bytes) -> None:
        if not pcm:
            return
        if self._muted:
            pcm = b"\x00" * len(pcm)
        self.peak = _peak(pcm)
        self.frames += 1
        callback = self._on_pcm
        if callback is not None:
            callback(pcm, self._muted)

    def _run(self) -> None:
        try:
            import comtypes
            from comtypes import CLSCTX_ALL
            from pycaw.api.audioclient import IAudioClient
            from pycaw.pycaw import AudioUtilities
        except Exception as exc:
            self.error = "未安装 pycaw/comtypes，无法环回系统播放: " + str(exc)
            return
        comtypes.CoInitialize()
        client = None
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            imm = enumerator.GetDevice(self.device_id)
            if imm is None:
                self.error = "找不到播放设备: " + self.device_name
                return
            iface = imm.Activate(IAudioClient._iid_, CLSCTX_ALL, None)
            client = iface.QueryInterface(IAudioClient)
            mix = client.GetMixFormat()
            fmt = mix.contents
            mix_bytes = ctypes.string_at(ctypes.addressof(fmt), ctypes.sizeof(WAVEFORMATEX) + int(fmt.cbSize or 0))
            rate = int(fmt.nSamplesPerSec)
            channels = int(fmt.nChannels)
            bits = int(fmt.wBitsPerSample)
            block = int(fmt.nBlockAlign)
            is_float = _is_float(fmt, mix_bytes)
            hr = client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK,
                50 * REFTIMES_PER_MS,
                0,
                mix,
                None,
            )
            if hr not in (0, None):
                self.error = f"WASAPI 环回打开失败 ({hr})"
                return
            capture_cls = _capture_client_type()
            service = client.GetService(capture_cls._iid_)
            capture = service.QueryInterface(capture_cls)
            client.Start()
            pending = bytearray()
            packet_bytes = PACKET_FRAMES * PLAY_CHANNELS * 2
            while not self._stop.is_set():
                try:
                    next_frames = capture.GetNextPacketSize()
                except Exception:
                    next_frames = 0
                if not next_frames:
                    time.sleep(0.001)
                    continue
                try:
                    data, nframes, flags, _pos, _qpc = capture.GetBuffer()
                except Exception as exc:
                    self.error = repr(exc)
                    time.sleep(0.01)
                    continue
                nframes = int(nframes or 0)
                if nframes <= 0:
                    try:
                        capture.ReleaseBuffer(0)
                    except Exception:
                        pass
                    continue
                if flags & AUDCLNT_BUFFERFLAGS_SILENT:
                    s16 = b"\x00" * (nframes * channels * 2)
                else:
                    raw = ctypes.string_at(data, nframes * block)
                    s16 = _mix_to_s16(raw, nframes, channels, bits, is_float)
                try:
                    capture.ReleaseBuffer(nframes)
                except Exception:
                    pass
                s16 = to_output_format(s16, channels, PLAY_CHANNELS)
                s16 = resample_int16(s16, rate, PLAY_RATE, PLAY_CHANNELS)
                pending.extend(s16)
                while len(pending) >= packet_bytes:
                    chunk = bytes(pending[:packet_bytes])
                    del pending[:packet_bytes]
                    self._emit(chunk)
        except Exception as exc:
            self.error = repr(exc)
        finally:
            try:
                if client is not None:
                    client.Stop()
            except Exception:
                pass
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    import audio_out

    assert PLAY_RATE // PACKET_FRAMES == 100, PACKET_FRAMES
    assert PACKET_FRAMES * PLAY_CHANNELS * 2 == PLAY_RATE * PLAY_CHANNELS * 2 // 100
    raw = bytes(range(16))
    assert _mix_to_s16(raw, 4, 2, 16, False) == raw
    pcm = b"\x00\x10" * 48
    assert resample_int16(pcm, 48000, 48000, 1) == pcm
    assert audio_out.BLOCK_SEC == 0.01
    assert audio_out.QUEUE_PACKETS <= 8
    print("ok")
