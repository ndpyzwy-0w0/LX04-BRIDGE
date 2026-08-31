"""Local git snapshot after a usable host or APK build."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
VERSION_FILE = ROOT / "VERSION.txt"

COMMIT_PATHS = [
    "VERSION.txt",
    "README.md",
    "build_host_exe.py",
    "build_apk.py",
    "pack_release.py",
    "release_git.py",
    "启动上位机.bat",
    ".gitignore",
    ".cursor/rules",
    "app",
    "host",
    "protocol.md",
    "local.properties.example",
    "dist/LX04-PC-Bridge.apk",
]


def read_version() -> int:
    if not VERSION_FILE.exists():
        return 1
    text = VERSION_FILE.read_text(encoding="utf-8").strip()
    return int(text) if text else 1


def commit_usable_version(version: int, summary: str = "") -> bool:
    """Commit source (+ current host EXE / APK when present). Returns True if a commit was created."""
    if not (ROOT / ".git").is_dir():
        print("Not a git repo; skip commit.")
        return False
    try:
        subprocess.check_call(["git", "add", "--", *COMMIT_PATHS], cwd=ROOT)
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT,
            text=True,
        ).strip()
        if not staged:
            print("Nothing to commit.")
            return False
        why = (summary or "snapshot source and current release artifacts").strip()
        message = (
            f"Release v{version}: {why}\n"
            "\n"
            "Rollback is git history of the current host EXE and APK."
        )
        subprocess.check_call(["git", "commit", "-m", message], cwd=ROOT)
        print("Committed git snapshot for v" + str(version))
        return True
    except subprocess.CalledProcessError as exc:
        print("Git commit skipped:", exc)
        return False
