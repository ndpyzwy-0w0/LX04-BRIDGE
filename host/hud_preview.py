"""Host-side 800x480 mock of the LX04 HUD. Style only; no live PC stats."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tkinter import colorchooser, ttk
import tkinter as tk
import tkinter.font as tkfont

SCREEN_W = 800
SCREEN_H = 480
DENSITY = 240 / 160.0
OK = "#3DDC97"
WARN = "#FFB020"
BAD = "#FF5C7A"
PLAY = "#6EA8FF"

DEFAULT_CARDS = (
    ("cpu", "CPU", "CPU", "88"),
    ("gpu", "GPU", "GPU", "88"),
    ("ram", "内存", "内存", "88"),
    ("disk", "磁盘", "D:", "88"),
)


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PREVIEW_FILE = _host_dir() / "hud_preview.json"

_open_root: tk.Toplevel | None = None


def dp(value: float) -> float:
    return value * DENSITY


def palette(light: bool) -> dict[str, str]:
    if light:
        return {
            "bg": "#F3F5F8",
            "panel": "#FFFFFF",
            "card": "#E8EEF5",
            "meter_bg": "#D5DDE8",
            "button": "#D3DCE8",
            "text": "#1A2438",
            "dim": "#5A6B84",
        }
    return {
        "bg": "#0B1220",
        "panel": "#141C2E",
        "card": "#1A2438",
        "meter_bg": "#1E2A44",
        "button": "#223154",
        "text": "#E8EEF8",
        "dim": "#8FA0BE",
    }


def default_state(light: bool = False) -> dict:
    colors = palette(light)
    cards = []
    for key, _label, title, value in DEFAULT_CARDS:
        cards.append(
            {
                "key": key,
                "title": title,
                "value": value,
                "title_color": colors["dim"],
                "value_color": OK,
            }
        )
    return {"light": light, "cards": cards}


def load_state(light: bool = False) -> dict:
    base = default_state(light)
    try:
        data = json.loads(PREVIEW_FILE.read_text(encoding="utf-8"))
    except Exception:
        return base
    if not isinstance(data, dict):
        return base
    saved = {item.get("key"): item for item in data.get("cards") or [] if isinstance(item, dict)}
    for card in base["cards"]:
        extra = saved.get(card["key"]) or {}
        if extra.get("title"):
            card["title"] = str(extra["title"])[:8]
        if extra.get("value") is not None and str(extra.get("value")) != "":
            card["value"] = str(extra["value"])[:10]
        if _hex(extra.get("title_color")):
            card["title_color"] = _hex(extra.get("title_color"))
        if _hex(extra.get("value_color")):
            card["value_color"] = _hex(extra.get("value_color"))
    return base


def save_state(state: dict) -> None:
    try:
        PREVIEW_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _hex(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
            return text.upper()
        except ValueError:
            return ""
    return ""


def _round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, radius: float, fill: str) -> None:
    r = max(0.0, min(float(radius), (x2 - x1) / 2.0, (y2 - y1) / 2.0))
    if r < 1:
        canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        return
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
    canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline="")
    canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline="")
    canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline="")
    canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline="")


def _font(size_dp: float, medium: bool = False) -> tuple:
    px = max(8, int(round(dp(size_dp))))
    weight = "bold" if medium else "normal"
    return ("Microsoft YaHei UI", -px, weight)


def _fit(font: tuple, text: str, max_width: float) -> str:
    if not text:
        return ""
    spec = tkfont.Font(font=font)
    if spec.measure(text) <= max_width:
        return text
    for i in range(len(text) - 1, 0, -1):
        cut = text[:i] + "…"
        if spec.measure(cut) <= max_width:
            return cut
    return "…"


def _bar_fill(value: str) -> float:
    digits = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    try:
        number = float(digits)
    except ValueError:
        return 0.5
    if number <= 1.0:
        return max(0.04, min(1.0, number))
    return max(0.04, min(1.0, number / 100.0))


def _version_label() -> str:
    for path in (
        _host_dir() / "VERSION.txt",
        _host_dir().parent / "VERSION.txt",
    ):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return "v" + text.split()[0]
        except Exception:
            continue
    return "v"


def draw_hud(canvas: tk.Canvas, state: dict) -> None:
    canvas.delete("all")
    w, h = SCREEN_W, SCREEN_H
    light = bool(state.get("light"))
    colors = palette(light)
    cards = list(state.get("cards") or default_state(light)["cards"])

    canvas.create_rectangle(0, 0, w, h, fill=colors["bg"], outline="")
    _round_rect(canvas, dp(12), dp(12), w - dp(12), h - dp(12), dp(18), colors["panel"])

    canvas.create_oval(dp(15), dp(15), dp(29), dp(29), fill=OK, outline="")
    top_font = _font(12)
    ver_font = _font(11)
    canvas.create_text(dp(36), dp(27), text="USB ADB", fill=colors["dim"], font=top_font, anchor="sw")
    ver = _version_label()
    spec = tkfont.Font(font=ver_font)
    ver_w = spec.measure(ver)
    canvas.create_text(w - dp(22), dp(27), text=ver, fill=colors["dim"], font=ver_font, anchor="se")
    mid = _fit(ver_font, "电脑  ·  预览", w - dp(80) - ver_w - dp(110))
    canvas.create_text(dp(110), dp(27), text=mid, fill=colors["dim"], font=ver_font, anchor="sw")

    mute_top = h - dp(64)
    mute_gap = dp(10)
    meter_h = dp(18)
    top = dp(44)
    left = dp(16)
    right = w - dp(16)
    gap = dp(8)
    bottom = mute_top - dp(8) - meter_h
    card_h = bottom - top
    card_w = (right - left - gap * 3) / 4.0

    for index, card in enumerate(cards[:4]):
        x = left + (card_w + gap) * index
        _draw_card(canvas, x, top, card_w, card_h, card, colors)

    net_font = _font(12)
    meter_top = mute_top - meter_h
    canvas.create_text(
        dp(18),
        meter_top + dp(14),
        text="↓ —    ↑ —",
        fill=colors["dim"],
        font=net_font,
        anchor="sw",
    )
    play_l, play_t, play_r, play_b = dp(210), meter_top, w - dp(18), mute_top - dp(4)
    _round_rect(canvas, play_l, play_t, play_r, play_b, dp(10), colors["meter_bg"])
    fill = max(dp(8), (play_r - play_l - 8) * 0.35)
    _round_rect(canvas, play_l + 4, play_t + 4, play_l + 4 + fill, play_b - 4, dp(8), PLAY)

    mic = (dp(18), mute_top, w / 2.0 - mute_gap / 2.0, h - dp(12))
    spk = (w / 2.0 + mute_gap / 2.0, mute_top, w - dp(18), h - dp(12))
    _draw_mute(canvas, mic, "麦克风", colors)
    _draw_mute(canvas, spk, "扬声器", colors)


def _draw_card(canvas: tk.Canvas, x: float, y: float, cw: float, ch: float, card: dict, colors: dict[str, str]) -> None:
    _round_rect(canvas, x, y, x + cw, y + ch, dp(12), colors["card"])
    title = str(card.get("title") or "")
    value = str(card.get("value") or "")
    title_color = _hex(card.get("title_color")) or colors["dim"]
    value_color = _hex(card.get("value_color")) or OK
    title_font = _font(13)
    value_font = _font(28, medium=True)
    sub_font = _font(11)
    canvas.create_text(x + dp(10), y + dp(18), text=_fit(title_font, title, cw - dp(18)), fill=title_color, font=title_font, anchor="sw")
    canvas.create_text(x + dp(10), y + dp(52), text=_fit(value_font, value, cw - dp(18)), fill=value_color, font=value_font, anchor="sw")
    canvas.create_text(x + dp(10), y + dp(72), text="预览", fill=colors["dim"], font=sub_font, anchor="sw")

    bar_top = y + ch - dp(14)
    bar_l, bar_r = x + dp(10), x + cw - dp(10)
    _round_rect(canvas, bar_l, bar_top, bar_r, bar_top + dp(7), dp(4), colors["meter_bg"])
    fill = max(dp(6), (cw - dp(20)) * _bar_fill(value))
    _round_rect(canvas, bar_l, bar_top, bar_l + fill, bar_top + dp(7), dp(4), value_color)


def _draw_mute(canvas: tk.Canvas, rect: tuple[float, float, float, float], label: str, colors: dict[str, str]) -> None:
    x1, y1, x2, y2 = rect
    _round_rect(canvas, x1, y1, x2, y2, dp(12), colors["button"])
    font = _font(16, medium=True)
    canvas.create_text((x1 + x2) / 2.0, y1 + (y2 - y1) * 0.66, text=label, fill=colors["text"], font=font, anchor="s")


def open_window(parent: tk.Misc, light: bool = False) -> tk.Toplevel:
    global _open_root
    if _open_root is not None:
        try:
            if _open_root.winfo_exists():
                _open_root.lift()
                _open_root.focus_force()
                return _open_root
        except tk.TclError:
            _open_root = None
    win = PreviewWindow(parent, light)
    _open_root = win.root
    return win.root


class PreviewWindow:
    def __init__(self, parent: tk.Misc, light: bool) -> None:
        self.root = tk.Toplevel(parent)
        self.root.title("音箱屏幕预览")
        self.root.configure(bg="#0B1220")
        self.root.resizable(False, False)
        self.state = load_state(light)
        self._saving = False
        self.light_var = tk.BooleanVar(value=bool(self.state["light"]))
        self.title_vars: list[tk.StringVar] = []
        self.value_vars: list[tk.StringVar] = []
        self._swatches: list[tuple[tk.Button, tk.Button]] = []

        hint = ttk.Label(
            self.root,
            text="按音箱 800×480 画样式。大字和标题可改，不读电脑真实占用。",
            style="Dim.TLabel",
        )
        hint.pack(anchor="w", padx=16, pady=(12, 6))

        self.canvas = tk.Canvas(
            self.root,
            width=SCREEN_W,
            height=SCREEN_H,
            highlightthickness=0,
            bg=palette(self.light_var.get())["bg"],
        )
        self.canvas.pack(padx=16, pady=(0, 8))

        tools = tk.Frame(self.root, bg="#141C2E")
        tools.pack(fill="x", padx=16, pady=(0, 8))
        tk.Checkbutton(
            tools,
            text="浅色",
            variable=self.light_var,
            command=self._on_light,
            bg="#141C2E",
            fg="#E8EEF8",
            selectcolor="#1E2A44",
            activebackground="#141C2E",
            activeforeground="#E8EEF8",
            highlightthickness=0,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=8, pady=8)
        ttk.Label(tools, text="只改预览底色，不影响已连上的音箱。", style="CardDim.TLabel").pack(side="left")
        ttk.Button(tools, text="恢复默认", command=self._reset).pack(side="right", padx=8, pady=6)

        editors = tk.Frame(self.root, bg="#141C2E")
        editors.pack(fill="x", padx=16, pady=(0, 16))
        header = tk.Frame(editors, bg="#141C2E")
        header.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(header, text="板块", style="CardDim.TLabel", width=6).pack(side="left")
        ttk.Label(header, text="标题字母", style="CardDim.TLabel", width=10).pack(side="left")
        ttk.Label(header, text="字母色", style="CardDim.TLabel", width=8).pack(side="left")
        ttk.Label(header, text="大字", style="CardDim.TLabel", width=10).pack(side="left")
        ttk.Label(header, text="大字色", style="CardDim.TLabel").pack(side="left")

        for index, (_key, label, _title, _value) in enumerate(DEFAULT_CARDS):
            card = self.state["cards"][index]
            row = tk.Frame(editors, bg="#141C2E")
            row.pack(fill="x", padx=8, pady=4)
            ttk.Label(row, text=label, style="Card.TLabel", width=6).pack(side="left")
            title_var = tk.StringVar(value=str(card["title"]))
            value_var = tk.StringVar(value=str(card["value"]))
            self.title_vars.append(title_var)
            self.value_vars.append(value_var)
            title_entry = ttk.Entry(row, textvariable=title_var, width=10)
            title_entry.pack(side="left", padx=(0, 6))
            title_swatch = tk.Button(row, width=3, relief="groove", bd=1, command=lambda i=index: self._pick(i, "title"))
            title_swatch.pack(side="left", padx=(0, 12))
            value_entry = ttk.Entry(row, textvariable=value_var, width=10)
            value_entry.pack(side="left", padx=(0, 6))
            value_swatch = tk.Button(row, width=3, relief="groove", bd=1, command=lambda i=index: self._pick(i, "value"))
            value_swatch.pack(side="left")
            self._swatches.append((title_swatch, value_swatch))
            title_var.trace_add("write", lambda *_a, i=index: self._on_text(i))
            value_var.trace_add("write", lambda *_a, i=index: self._on_text(i))

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._paint_swatches()
        self._redraw()

    def _cards_from_vars(self) -> None:
        for index, card in enumerate(self.state["cards"]):
            card["title"] = self.title_vars[index].get()[:8]
            card["value"] = self.value_vars[index].get()[:10]

    def _on_text(self, _index: int) -> None:
        self._cards_from_vars()
        self._redraw()
        self._schedule_save()

    def _on_light(self) -> None:
        self.state["light"] = bool(self.light_var.get())
        self._redraw()
        self._schedule_save()

    def _pick(self, index: int, which: str) -> None:
        key = "title_color" if which == "title" else "value_color"
        current = self.state["cards"][index].get(key) or OK
        picked = colorchooser.askcolor(color=current, parent=self.root, title="选择颜色")
        if not picked or not picked[1]:
            return
        self.state["cards"][index][key] = picked[1].upper()
        self._paint_swatches()
        self._redraw()
        self._schedule_save()

    def _reset(self) -> None:
        self.state = default_state(bool(self.light_var.get()))
        self.light_var.set(bool(self.state["light"]))
        for index, card in enumerate(self.state["cards"]):
            self.title_vars[index].set(card["title"])
            self.value_vars[index].set(card["value"])
        self._paint_swatches()
        self._redraw()
        save_state(self.state)

    def _paint_swatches(self) -> None:
        for index, (title_btn, value_btn) in enumerate(self._swatches):
            card = self.state["cards"][index]
            title_btn.configure(bg=card["title_color"], activebackground=card["title_color"])
            value_btn.configure(bg=card["value_color"], activebackground=card["value_color"])

    def _redraw(self) -> None:
        self._cards_from_vars()
        self.canvas.configure(bg=palette(bool(self.state["light"]))["bg"])
        draw_hud(self.canvas, self.state)

    def _schedule_save(self) -> None:
        if self._saving:
            return
        self._saving = True
        self.root.after(250, self._flush_save)

    def _flush_save(self) -> None:
        self._saving = False
        self._cards_from_vars()
        save_state(self.state)

    def _close(self) -> None:
        global _open_root
        self._cards_from_vars()
        save_state(self.state)
        _open_root = None
        self.root.destroy()
