#!/usr/bin/env python3
"""Fail if the tracked VB-CABLE zip cannot yield the official setup exe."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import vb_cable


def main() -> None:
    archive = vb_cable.zip_path()
    assert archive is not None and archive.is_file(), archive
    names = {Path(name).name.lower() for name in zipfile.ZipFile(archive).namelist()}
    assert vb_cable.SETUP_X64.lower() in names, names
    exe = vb_cable.ensure_installer()
    assert exe is not None and exe.is_file(), exe
    print("ok")


if __name__ == "__main__":
    main()
