"""Read and set the Windows default playback volume (system volume keys)."""
from __future__ import annotations


def get_scalar() -> float | None:
    volume = _endpoint_volume()
    if volume is None:
        return None
    try:
        return max(0.0, min(1.0, float(volume.GetMasterVolumeLevelScalar())))
    except Exception:
        return None


def is_silent() -> bool:
    volume = _endpoint_volume()
    if volume is None:
        return False
    try:
        if int(volume.GetMute()):
            return True
    except Exception:
        pass
    try:
        return float(volume.GetMasterVolumeLevelScalar()) <= 0.001
    except Exception:
        return False


def set_scalar(level: float) -> bool:
    volume = _endpoint_volume()
    if volume is None:
        return False
    value = max(0.0, min(1.0, float(level)))
    try:
        volume.SetMasterVolumeLevelScalar(value, None)
        return True
    except Exception:
        return False


def _endpoint_volume():
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
        return speakers.EndpointVolume
    except Exception:
        pass
    try:
        from pycaw.api.endpointvolume import IAudioEndpointVolume

        iface = speakers._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return iface.QueryInterface(IAudioEndpointVolume)
    except Exception:
        return None
