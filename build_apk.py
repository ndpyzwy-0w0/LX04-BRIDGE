#!/usr/bin/env python3
"""Build the LX04 APK and create a local git snapshot."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION.txt"

from release_git import commit_usable_version


def current_version() -> int:
    if not VERSION_FILE.exists():
        return 1
    text = VERSION_FILE.read_text(encoding="utf-8").strip()
    return int(text) if text else 1


def bump_version() -> int:
    version = current_version() + 1
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")
    print("VERSION.txt ->", version)
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Build APK and commit a local release snapshot.")
    parser.add_argument(
        "-m",
        "--message",
        default="",
        help="Release note for the git commit (Release vN: ...).",
    )
    parser.add_argument(
        "--bump",
        action="store_true",
        help="Increment VERSION.txt before building.",
    )
    args = parser.parse_args()

    version = bump_version() if args.bump else current_version()
    env = os.environ.copy()
    for key in ("JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if key in os.environ:
            env[key] = os.environ[key]

    gradlew = ROOT / "gradlew.bat" if os.name == "nt" else ROOT / "gradlew"
    cmd = [str(gradlew), ":app:assembleDebug", "--no-daemon"]
    print("Running", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT, env=env)

    apk_dir = ROOT / "app" / "build" / "outputs" / "apk" / "debug"
    apks = sorted(apk_dir.glob("*.apk")) if apk_dir.is_dir() else []
    if apks:
        print("Wrote", apks[-1])
    commit_usable_version(version, args.message or "APK build snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
