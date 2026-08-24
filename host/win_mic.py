"""Detect Windows recording devices, especially the LX04 USB microphone."""
from __future__ import annotations

import time

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover
    sd = None

USB_MIC_HINTS = (
    "cable output",
    "vb-audio virtual cable",
    "lx04 麦克风",
    "lx04 microphone",
)


def list_inputs() -> list[tuple[int, str]]:
    if sd is None:
        return []
    items: list[tuple[int, str]] = []
    try:
        hostapis = list(sd.query_hostapis())
    except Exception:
        hostapis = []
    for index, info in enumerate(sd.query_devices()):
        if int(info.get("max_input_channels") or 0) <= 0:
            continue
        api = int(info.get("hostapi") or 0)
        api_name = ""
        if 0 <= api < len(hostapis):
            api_name = str(hostapis[api].get("name") or "")
        if api_name and "WASAPI" not in api_name and "MME" not in api_name:
            continue
        items.append((index, str(info.get("name") or f"mic-{index}")))
    return items


def find_usb_microphone(names: list[tuple[int, str]] | None = None) -> tuple[int, str] | None:
    items = names if names is not None else list_inputs()
    for index, name in items:
        lowered = name.lower()
        if any(hint in lowered for hint in USB_MIC_HINTS):
            if "inject" in lowered or "注入" in name or "speakers" in lowered or "cable input" in lowered:
                continue
            if "16ch" in lowered or "16 ch" in lowered:
                continue
            if "hi-fi" in lowered or "hifi" in lowered:
                continue
            return index, name
        if "microphone" in lowered and "usb" in lowered:
            return index, name
        if "麦克风" in name and "usb" in lowered:
            return index, name
    return None


def matching_recording_device(output_name: str) -> tuple[int, str] | None:
    lowered = output_name.lower()
    keys: list[str] = []
    if "lx04" in lowered:
        keys.extend(("lx04 麦克风", "lx04 microphone", "lx04"))
    if "steam streaming microphone" in lowered:
        keys.append("steam streaming microphone")
    if (
        "cable input" in lowered
        or "cable output" in lowered
        or "vb-audio" in lowered
        or "vb-audio point" in lowered
    ):
        keys.extend(("cable output", "cable out", "vb-audio virtual cable"))
    if "voicemeeter" in lowered:
        keys.append("voicemeeter")
    if not keys:
        keys = list(USB_MIC_HINTS)
    items = list_inputs()
    for index, name in items:
        candidate = name.lower()
        if "speakers" in candidate or "inject" in candidate or "注入" in name:
            continue
        if "16ch" in candidate or "16 ch" in candidate:
            continue
        if "hi-fi" in candidate or "hifi" in candidate:
            continue
        if any(key in candidate or key in name for key in keys):
            return index, name
    return find_usb_microphone(items)


def wait_for_usb_microphone(seconds: float = 12.0) -> tuple[int, str] | None:
    deadline = time.time() + seconds
    found: tuple[int, str] | None = None
    while time.time() < deadline:
        found = find_usb_microphone()
        if found:
            return found
        time.sleep(0.8)
    return found
