"""Fail if withdraw/deiconify cannot bring a Tk window back."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tkinter as tk

import pc_host


def main() -> None:
    root = tk.Tk()
    root.geometry("240x80+80+80")
    root.update()
    assert root.winfo_viewable(), root.state()
    root.withdraw()
    root.update()
    assert root.state() == "withdrawn"
    pc_host._show_tk_window(root)
    root.update()
    assert root.state() != "withdrawn", root.state()
    assert root.winfo_viewable(), root.state()
    root.destroy()
    print("ok")


if __name__ == "__main__":
    main()
