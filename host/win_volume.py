"""Read and set the Windows default playback volume (system volume keys)."""
from __future__ import annotations

_cached_endpoint = None


def get_state() -> tuple[float | None, bool]:
    """Return (scalar 0..1, muted). One COM round-trip."""
    volume = _endpoint_volume()
    if volume is None:
        return None, False
    muted = False
    scalar = None
    try:
        muted = bool(int(volume.GetMute()))
    except Exception:
        pass
    try:
        scalar = max(0.0, min(1.0, float(volume.GetMasterVolumeLevelScalar())))
    except Exception:
        pass
    if scalar is not None and scalar <= 0.001:
        muted = True
    return scalar, muted


def get_scalar() -> float | None:
    scalar, _muted = get_state()
    return scalar


def is_silent() -> bool:
    _scalar, muted = get_state()
    return muted


def set_scalar(level: float) -> bool:
    volume = _endpoint_volume()
    if volume is None:
        return False
    value = max(0.0, min(1.0, float(level)))
    try:
        volume.SetMasterVolumeLevelScalar(value, None)
        return True
    except Exception:
        _clear_cached_endpoint()
        return False


def _clear_cached_endpoint() -> None:
    global _cached_endpoint
    _cached_endpoint = None


def _endpoint_volume():
    global _cached_endpoint
    if _cached_endpoint is not None:
        return _cached_endpoint
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return None
    try:
        speakers = AudioUtilities.GetSpeakers()
    except Exception:
        return None
    if speakers is None:
        return None
    try:
        endpoint = speakers.EndpointVolume
    except Exception:
        endpoint = None
    if endpoint is None:
        try:
            from pycaw.api.endpointvolume import IAudioEndpointVolume

            iface = speakers._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = iface.QueryInterface(IAudioEndpointVolume)
        except Exception:
            return None
    _cached_endpoint = endpoint
    return endpoint
