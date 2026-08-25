#!/usr/bin/env python3
"""Build the LX04 APK and create a local git snapshot."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
VERSION_FILE = ROOT / "VERSION.txt"

from release_git import commit_usable_version, read_version


def current_version() -> int:
    return read_version()


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
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Pack only; skip the local git snapshot.",
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
    if not apks:
        raise SystemExit("Gradle finished but no APK was produced.")
    built = apks[-1]
    DIST.mkdir(parents=True, exist_ok=True)
    latest = DIST / "LX04-PC-Bridge.apk"
    shutil.copy2(built, latest)
    print("Wrote", latest)
    if not args.no_commit:
        commit_usable_version(version, args.message or "APK build snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
