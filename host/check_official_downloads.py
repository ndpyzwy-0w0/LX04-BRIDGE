#!/usr/bin/env python3
"""Fail if VB-CABLE / Hi-Fi Cable / Afterburner installers are bundled or fetched."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import afterburner
import hifi_cable
import vb_cable


def main() -> None:
    assert vb_cable.OFFICIAL_URL == "https://www.vb-cable.com/"
    assert hifi_cable.OFFICIAL_URL == "https://vb-audio.com/Cable/"
    assert afterburner.OFFICIAL_URL == "https://www.msi.com/Landing/afterburner"
    for mod in (vb_cable, hifi_cable):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "zipfile" not in src
        assert "urllib" not in src
        assert "ShellExecute" not in src
        assert "Setup.exe" not in src
        assert "def open_download" in src
    forbidden = ("vbcable_driver", "hificableasiobridge", "msiafterburner_setup")
    for path in HERE.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() in {".zip", ".exe", ".msi"} and any(key in name for key in forbidden):
            raise AssertionError(path)
        if path.suffix.lower() in {".zip", ".exe", ".msi"} and path.parent.name.lower() in {
            "vbcable",
            "hificable",
            "pack",
        }:
            raise AssertionError(path)
    pack = (HERE.parent / "build_host_exe.py").read_text(encoding="utf-8")
    assert "VBCABLE_Driver_Pack" not in pack
    assert "HiFiCableAsioBridge" not in pack
    print("ok")


if __name__ == "__main__":
    main()
