#!/usr/bin/env python3
"""Bump, pack APK + host EXE, then one local git snapshot."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION.txt"

from release_git import commit_usable_version, read_version


def bump_version() -> int:
    version = read_version() + 1
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    print("VERSION.txt ->", version)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack APK + host EXE and commit once.")
    parser.add_argument(
        "-m",
        "--message",
        default="",
        help="Release note for the git commit (Release vN: ...).",
    )
    parser.add_argument(
        "--bump",
        action="store_true",
        help="Increment VERSION.txt before packing.",
    )
    args = parser.parse_args()

    version = bump_version() if args.bump else read_version()
    py = sys.executable
    subprocess.check_call([py, str(ROOT / "build_apk.py"), "--no-commit"], cwd=ROOT)
    host = subprocess.call([py, str(ROOT / "build_host_exe.py"), "--no-commit"], cwd=ROOT)
    if host != 0:
        print("Host EXE pack failed (close the running host if the file is locked). APK is already in dist/.")
        return host
    commit_usable_version(version, args.message or "APK and host snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
