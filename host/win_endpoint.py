"""Set Windows default microphone, format, names, and unmute virtual-cable endpoints."""
from __future__ import annotations

import winreg
from ctypes import POINTER, Structure, byref, c_int
from ctypes.wintypes import BOOL, DWORD, LPCWSTR
from typing import Any

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3

# IPolicyConfig DeviceShareMode: 0 = shared (apps use the mixer).
_SHARE_MODE_SHARED = 0

CABLE_PARENT_NAME = "LX04"
CAPTURE_DEVICE_DESC = "LX04 麦克风"
RENDER_DEVICE_DESC = "LX04 注入"

_PKEY_PARENT_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
_PKEY_DEVICE_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
_PKEY_DISABLE_SYSFX = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
_VT_BOOL_TRUE = bytes((0x0B, 0, 0, 0, 1, 0, 0, 0, 0xFF, 0xFF, 0, 0))

CABLE_RATE = 48000
CABLE_CHANNELS = 2


class _DeviceShareMode(Structure):
    _fields_ = (("dwMode", DWORD),)


def is_steam_speakers(name: str) -> bool:
    return "steam streaming speakers" in (name or "").lower()


def _is_16ch_cable(name: str) -> bool:
    lowered = (name or "").lower()
    return "16ch" in lowered or "16 ch" in lowered or "16通道" in (name or "") or "in 16ch" in lowered


def is_cable_capture(name: str) -> bool:
    text = name or ""
    lowered = text.lower()
    if is_steam_speakers(text) or "注入" in text or "inject" in lowered:
        return False
    if _is_16ch_cable(text) or "vb-audio point" in lowered:
        return False
    if _is_hifi_name(text):
        return False
    if "cable input" in lowered:
        return False
    if "cable output" in lowered:
        return True
    return False


def is_cable_render(name: str) -> bool:
    text = name or ""
    lowered = text.lower()
    if is_steam_speakers(text) or _is_16ch_cable(text) or "vb-audio point" in lowered:
        return False
    if _is_hifi_name(text):
        return False
    if "cable output" in lowered:
        return False
    if "cable input" in lowered:
        return True
    return False


def _is_hifi_name(name: str) -> bool:
    import hifi_cable

    return hifi_cable.is_hifi_name(name)


def is_hifi_render(name: str) -> bool:
    import hifi_cable

    return hifi_cable.is_hifi_render(name)


def get_default_render() -> tuple[str, str] | None:
    try:
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return None
    try:
        speakers = AudioUtilities.GetSpeakers()
    except Exception:
        return None
    if speakers is None:
        return None
    return speakers.id, speakers.FriendlyName or ""


def set_default_render(device_id: str) -> bool:
    try:
        from pycaw.constants import ERole
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return False
    try:
        AudioUtilities.SetDefaultDevice(
            device_id,
            roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications],
        )
        return True
    except Exception:
        return False


def list_render_endpoints() -> list[tuple[str, str]]:
    try:
        from pycaw.constants import DEVICE_STATE, EDataFlow
    except Exception:
        return []
    items: list[tuple[str, str]] = []
    for device in _iter_devices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value):
        name = device.FriendlyName or ""
        if is_steam_speakers(name):
            continue
        items.append((device.id, name))
    items.sort(
        key=lambda item: (
            0 if is_hifi_render(item[1]) else 1 if is_cable_render(item[1]) else 2,
            item[1].lower(),
        )
    )
    return items


def prepare_render_device(device_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {"render": None, "device_id": None, "logs": []}
    logs: list[str] = result["logs"]
    try:
        from pycaw.constants import DEVICE_STATE, EDataFlow
    except Exception:
        logs.append("未安装 pycaw，无法打开播放设备。")
        return result
    device = None
    for candidate in _iter_devices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value):
        if candidate.id == device_id:
            device = candidate
            break
    if device is None:
        logs.append("找不到选中的播放设备。")
        return result
    _unmute(device)
    ok = set_capture_app_format(device.id, channels=CABLE_CHANNELS, rate=CABLE_RATE)
    set_shared_mode(device.id)
    result["render"] = device.FriendlyName
    result["device_id"] = device.id
    logs.append(("已准备" if ok else "已打开") + " 播放设备: " + (device.FriendlyName or device_id))
    return result


def find_hifi_render() -> Any | None:
    try:
        from pycaw.constants import EDataFlow
    except Exception:
        return None
    return _find_endpoint(EDataFlow.eRender.value, is_hifi_render)


def prepare_hifi_cable() -> dict[str, Any]:
    """Unmute Hi-Fi Cable Input so system audio can be looped to the LX04 speaker."""
    result: dict[str, Any] = {"render": None, "device_id": None, "logs": []}
    logs: list[str] = result["logs"]
    render = find_hifi_render()
    if render is None:
        logs.append("未找到 Hi-Fi Cable Input。请安装 VB-Audio Hi-Fi Cable 并重启。")
        return result
    _unmute(render)
    ok = set_capture_app_format(render.id, channels=CABLE_CHANNELS, rate=CABLE_RATE)
    set_shared_mode(render.id)
    _disable_endpoint_fx("Render", render.id)
    result["render"] = render.FriendlyName
    result["device_id"] = render.id
    logs.append(
        ("已锁定" if ok else "未能锁定") + " Hi-Fi Cable Input: 48kHz / 立体声"
    )
    return result


def _pcm16(channels: int, rate: int):
    from pycaw.api.audioclient.depend import WAVEFORMATEX

    fmt = WAVEFORMATEX()
    fmt.wFormatTag = WAVE_FORMAT_PCM
    fmt.nChannels = channels
    fmt.nSamplesPerSec = rate
    fmt.wBitsPerSample = 16
    fmt.nBlockAlign = channels * 2
    fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign
    fmt.cbSize = 0
    return fmt


def _float32(channels: int, rate: int):
    from pycaw.api.audioclient.depend import WAVEFORMATEX

    fmt = WAVEFORMATEX()
    fmt.wFormatTag = WAVE_FORMAT_IEEE_FLOAT
    fmt.nChannels = channels
    fmt.nSamplesPerSec = rate
    fmt.wBitsPerSample = 32
    fmt.nBlockAlign = channels * 4
    fmt.nAvgBytesPerSec = rate * fmt.nBlockAlign
    fmt.cbSize = 0
    return fmt


def _policy_config():
    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
    from pycaw.api.audioclient.depend import WAVEFORMATEX
    from pycaw.constants import CLSID_CPolicyConfigClient

    class IPolicyConfigAudio(IUnknown):
        _iid_ = GUID("{f8679f50-850a-41cf-9c72-430f290290c8}")
        _methods_ = (
            COMMETHOD(
                [],
                HRESULT,
                "GetMixFormat",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["out"], POINTER(POINTER(WAVEFORMATEX)), "ppFormat"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetDeviceFormat",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], c_int, "bDefault"),
                (["out"], POINTER(POINTER(WAVEFORMATEX)), "ppFormat"),
            ),
            COMMETHOD([], HRESULT, "ResetDeviceFormat", (["in"], LPCWSTR, "pwstrDeviceId")),
            COMMETHOD(
                [],
                HRESULT,
                "SetDeviceFormat",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], POINTER(WAVEFORMATEX), "pEndpointFormat"),
                (["in"], POINTER(WAVEFORMATEX), "pMixFormat"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetProcessingMode",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["out"], POINTER(DWORD), "pMode"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetProcessingMode",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], DWORD, "mode"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "GetShareMode",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["out"], POINTER(_DeviceShareMode), "pMode"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetShareMode",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], POINTER(_DeviceShareMode), "pMode"),
            ),
            COMMETHOD([], HRESULT, "GetPropertyValue"),
            COMMETHOD([], HRESULT, "SetPropertyValue"),
            COMMETHOD(
                [],
                HRESULT,
                "SetDefaultEndpoint",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], DWORD, "role"),
            ),
            COMMETHOD(
                [],
                HRESULT,
                "SetEndpointVisibility",
                (["in"], LPCWSTR, "pwstrDeviceId"),
                (["in"], BOOL, "bVisible"),
            ),
        )

    return comtypes.CoCreateInstance(
        CLSID_CPolicyConfigClient, IPolicyConfigAudio, comtypes.CLSCTX_ALL
    )


def _mix_is_stereo_48k(device_id: str) -> bool:
    try:
        policy = _policy_config()
        mix = policy.GetMixFormat(device_id)
        fmt = mix.contents
        return int(fmt.nChannels) == 2 and int(fmt.nSamplesPerSec) == 48000
    except Exception:
        return False


def set_capture_app_format(device_id: str, channels: int = 2, rate: int = 48000) -> bool:
    """Keep VB-CABLE Input and Output on the same 48 kHz stereo clock.

    Different mix rates on the two ends produce speech-gated digital hash (电流声).
    VB-CABLE on this PC already exposes a 48 kHz 2ch mix; forcing 16-bit PCM
    WAVEFORMATEX is rejected (device uses WAVEFORMATEXTENSIBLE 24-bit).
    """
    if _mix_is_stereo_48k(device_id) and channels == 2 and rate == 48000:
        return True
    try:
        policy = _policy_config()
        endpoint = _pcm16(channels, rate)
        mix = _float32(channels, rate)
        hr = policy.SetDeviceFormat(device_id, byref(endpoint), byref(mix))
        return hr == 0 or hr is None
    except Exception:
        return _mix_is_stereo_48k(device_id)


def set_shared_mode(device_id: str) -> bool:
    try:
        policy = _policy_config()
        mode = _DeviceShareMode()
        mode.dwMode = _SHARE_MODE_SHARED
        hr = policy.SetShareMode(device_id, byref(mode))
        return hr == 0 or hr is None
    except Exception:
        return False


def _mmdevice_guid(device_id: str) -> str:
    if "}." in device_id:
        return "{" + device_id.split("}.{", 1)[1]
    return device_id


def _disable_endpoint_fx(flow: str, device_id: str) -> bool:
    guid = _mmdevice_guid(device_id)
    path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\{flow}\{guid}\Properties"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
        )
    except OSError:
        return False
    try:
        winreg.SetValueEx(key, _PKEY_DISABLE_SYSFX, 0, winreg.REG_BINARY, _VT_BOOL_TRUE)
        return True
    except OSError:
        return False
    finally:
        winreg.CloseKey(key)


def _iter_devices(data_flow: int, device_state: int | None = None):
    try:
        from pycaw.constants import DEVICE_STATE
        from pycaw.pycaw import AudioUtilities
    except Exception:
        return []
    state = DEVICE_STATE.ACTIVE.value if device_state is None else device_state
    try:
        return list(
            AudioUtilities.GetAllDevices(
                data_flow=data_flow,
                device_state=state,
            )
        )
    except Exception:
        try:
            return list(AudioUtilities.GetAllDevices())
        except Exception:
            return []


def _find_endpoint(data_flow: int, matcher) -> Any | None:
    for device in _iter_devices(data_flow):
        if matcher(device.FriendlyName or ""):
            return device
    return None


def _unmute(device: Any) -> None:
    try:
        volume = device.EndpointVolume
        volume.SetMute(0, None)
        volume.SetMasterVolumeLevelScalar(1.0, None)
    except Exception:
        pass


def _restore_cable_endpoints() -> list[str]:
    """Show 16-channel VB-CABLE endpoints again. Hiding them left WeChat holding a dead mic."""
    try:
        from pycaw.constants import DEVICE_STATE, EDataFlow
    except Exception:
        return []
    restored: list[str] = []
    try:
        policy = _policy_config()
    except Exception:
        return []
    mask = DEVICE_STATE.MASK_ALL.value
    for flow in (EDataFlow.eCapture.value, EDataFlow.eRender.value):
        for device in _iter_devices(flow, mask):
            name = device.FriendlyName or ""
            lowered = name.lower()
            if "cable" not in lowered and "vb-audio" not in lowered:
                continue
            try:
                hr = policy.SetEndpointVisibility(device.id, 1)
                if hr == 0 or hr is None:
                    restored.append(name)
            except Exception:
                pass
    return restored


def _hide_16ch_cable_endpoints() -> list[str]:
    return []


def prepare_vb_cable() -> dict[str, Any]:
    """Unmute both VB-CABLE ends, make CABLE Output the default mic, keep 48 kHz stereo."""
    result: dict[str, Any] = {"capture": None, "render": None, "logs": []}
    logs: list[str] = result["logs"]
    restored = _restore_cable_endpoints()
    if restored:
        logs.append("已重新显示 CABLE 设备，请完全退出微信后再选「CABLE Output」")
    try:
        from pycaw.constants import EDataFlow, ERole
        from pycaw.pycaw import AudioUtilities
    except Exception:
        logs.append("未安装 pycaw，无法锁定 CABLE 采样率。")
        return result
    capture = _find_endpoint(EDataFlow.eCapture.value, is_cable_capture)
    render = _find_endpoint(EDataFlow.eRender.value, is_cable_render)
    if capture is not None:
        _unmute(capture)
        ok = set_capture_app_format(capture.id, channels=CABLE_CHANNELS, rate=CABLE_RATE)
        set_shared_mode(capture.id)
        _disable_endpoint_fx("Capture", capture.id)
        try:
            AudioUtilities.SetDefaultDevice(
                capture.id,
                roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications],
            )
        except Exception:
            pass
        result["capture"] = capture.FriendlyName
        logs.append(
            ("已锁定" if ok else "未能锁定") + " CABLE Output: 48kHz / 16bit / 立体声"
        )
    if render is not None:
        _unmute(render)
        ok = set_capture_app_format(render.id, channels=CABLE_CHANNELS, rate=CABLE_RATE)
        set_shared_mode(render.id)
        _disable_endpoint_fx("Render", render.id)
        result["render"] = render.FriendlyName
        logs.append(
            ("已锁定" if ok else "未能锁定") + " CABLE Input: 48kHz / 16bit / 立体声"
        )
    if capture is None or render is None:
        logs.append("未找全 CABLE Input / CABLE Output。请确认已安装 VB-CABLE 并重启过电脑。")
    return result
