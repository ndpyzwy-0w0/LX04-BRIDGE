"""Host-side 800x480 mock of the LX04 HUD. Style only; no live PC stats."""
from __future__ import annotations

import json
import math
import sys
import time
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

DEFAULT_SLOTS = (
    ("cpu", "CPU", "cpu", "cpuT"),
    ("gpu", "GPU", "gpu", "gpuT"),
    ("ram", "内存", "ram", "ramGB"),
    ("disk", "磁盘", "disk", "diskGB"),
)
METRICS = (
    ("cpu", "CPU 占用", "88%"),
    ("cpuT", "CPU 温度", "64°C"),
    ("gpu", "GPU 占用", "88%"),
    ("gpuT", "GPU 温度", "64°C"),
    ("gpuW", "GPU 功耗", "120W"),
    ("gpuFan", "GPU 风扇", "40%"),
    ("vram", "显存占用", "28%"),
    ("ram", "内存占用", "35%"),
    ("ramGB", "内存容量", "22 / 64 GB"),
    ("disk", "磁盘占用", "42%"),
    ("diskGB", "磁盘容量", "400 / 931 GB"),
    ("diskIo", "磁盘 IO", "12%"),
    ("netD", "下载速度", "—"),
    ("netU", "上传速度", "—"),
    ("cores", "CPU 核数", "24 核"),
    ("gpuN", "显卡型号", "RTX 4070 SUPER"),
)
METRIC_LABEL = {key: label for key, label, _sample in METRICS}
METRIC_SAMPLE = {key: sample for key, _label, sample in METRICS}
METRIC_KEY = {label: key for key, label, _sample in METRICS}
NONE_METRIC = "none"
NONE_LABEL = "不显示"
CHART_FOLLOW = "main"
CHART_FOLLOW_LABEL = "跟随大字"
CHART_METRICS = tuple(key for key, _label, _sample in METRICS if key not in {"cores", "gpuN"})
VALUE_SIZE_DEFAULT = 28
SUB_SIZE_DEFAULT = 11
VALUE_SIZE_MIN, VALUE_SIZE_MAX = 12, 56
SUB_SIZE_MIN, SUB_SIZE_MAX = 8, 28
MAX_SUBS = 4


def metric_label(key: str) -> str:
    return METRIC_LABEL.get(key) or METRIC_LABEL["cpu"]


def metric_sample(key: str) -> str:
    return METRIC_SAMPLE.get(key) or "—"


def metric_key(label: str) -> str:
    return METRIC_KEY.get(label) or "cpu"


def sub_metric_label(key: str) -> str:
    if key == NONE_METRIC:
        return NONE_LABEL
    return metric_label(key)


def sub_metric_key(label: str) -> str:
    if label == NONE_LABEL:
        return NONE_METRIC
    return metric_key(label)


def sub_metric_sample(key: str) -> str:
    if key == NONE_METRIC:
        return ""
    return metric_sample(key)


def default_sub_for(card: dict) -> str:
    key = str(card.get("key") or "")
    for item in DEFAULT_SLOTS:
        if item[0] == key:
            return item[3]
    return DEFAULT_SLOTS[0][3]


def card_sub_metrics(card: dict) -> list[str]:
    extra = card.get("sub_metrics")
    if extra is None:
        extra = card.get("subMetrics")
    keys: list[str] = []
    if isinstance(extra, list):
        for item in extra:
            key = str(item or "")
            if is_metric(key):
                keys.append(key)
            if len(keys) >= MAX_SUBS:
                break
        if keys:
            return keys
    one = str(card.get("sub_metric") or card.get("subMetric") or "")
    if is_metric(one):
        return [one]
    return []


def display_sub_metrics(card: dict) -> list[str]:
    keys = card_sub_metrics(card)
    if not keys:
        return [default_sub_for(card)]
    return [key for key in keys if key != NONE_METRIC]


def store_sub_metrics(card: dict, keys: list[str]) -> None:
    cleaned: list[str] = []
    for key in keys:
        if is_metric(key):
            cleaned.append(key)
        if len(cleaned) >= MAX_SUBS:
            break
    if not cleaned:
        cleaned = [NONE_METRIC]
    card["sub_metrics"] = cleaned
    card["sub_metric"] = cleaned[0]


def is_metric(key: str) -> bool:
    return key == NONE_METRIC or key in METRIC_LABEL


def is_chartable(key: str) -> bool:
    return key in CHART_METRICS


def chart_metric_label(key: str) -> str:
    if not key or key == CHART_FOLLOW:
        return CHART_FOLLOW_LABEL
    return metric_label(key)


def chart_metric_key(label: str) -> str:
    if label == CHART_FOLLOW_LABEL or not label:
        return ""
    key = metric_key(label)
    return key if is_chartable(key) else ""


def clamp_int(value: object, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return default
    return max(lo, min(hi, number))


def card_value_size(card: dict) -> int:
    return clamp_int(card.get("value_size") or card.get("valueSize"), VALUE_SIZE_DEFAULT, VALUE_SIZE_MIN, VALUE_SIZE_MAX)


def card_sub_size(card: dict) -> int:
    return clamp_int(card.get("sub_size") or card.get("subSize"), SUB_SIZE_DEFAULT, SUB_SIZE_MIN, SUB_SIZE_MAX)


def default_title_for(metric: str, slot_title: str) -> str:
    if metric == "cpu" or metric == "cpuT":
        return "CPU"
    if metric == "gpu" or metric == "gpuT":
        return "GPU"
    if metric == "gpuW":
        return "功耗"
    if metric == "gpuFan":
        return "风扇"
    if metric == "vram":
        return "显存"
    if metric == "ram" or metric == "ramGB":
        return "内存"
    if metric == "disk" or metric == "diskGB":
        return "磁盘"
    if metric == "diskIo":
        return "IO"
    if metric == "netD":
        return "下载"
    if metric == "netU":
        return "上传"
    if metric == "cores":
        return "核数"
    if metric == "gpuN":
        return "显卡"
    return slot_title


def _host_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PREVIEW_FILE = _host_dir() / "hud_preview.json"

_open_root: tk.Toplevel | None = None
_open_win: PreviewWindow | None = None


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
    for key, title, metric, sub_metric in DEFAULT_SLOTS:
        cards.append(
            {
                "key": key,
                "title": title,
                "metric": metric,
                "sub_metric": sub_metric,
                "sub_metrics": [sub_metric],
                "value_size": VALUE_SIZE_DEFAULT,
                "sub_size": SUB_SIZE_DEFAULT,
                "title_color": colors["dim"],
                "value_color": OK,
                "title_color_set": False,
                "value_color_set": False,
                "chart": True,
                "chart_metric": "",
            }
        )
    return {"light": light, "cards": cards, "rev": 0}


def bump_rev(state: dict) -> None:
    now = int(time.time() * 1000)
    state["rev"] = max(int(state.get("rev") or 0) + 1, now)


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
        metric = str(extra.get("metric") or "")
        if metric in METRIC_LABEL:
            card["metric"] = metric
        subs = card_sub_metrics(extra)
        if subs:
            store_sub_metrics(card, subs)
        if extra.get("value_size") or extra.get("valueSize"):
            card["value_size"] = card_value_size(extra)
        if extra.get("sub_size") or extra.get("subSize"):
            card["sub_size"] = card_sub_size(extra)
        if "chart" in extra:
            card["chart"] = bool(extra.get("chart"))
        chart_metric = str(extra.get("chart_metric") or extra.get("chartMetric") or "")
        if chart_metric == CHART_FOLLOW:
            card["chart_metric"] = ""
        elif is_chartable(chart_metric):
            card["chart_metric"] = chart_metric
        if _hex(extra.get("title_color")):
            card["title_color"] = _hex(extra.get("title_color"))
        if _hex(extra.get("value_color")):
            card["value_color"] = _hex(extra.get("value_color"))
        card["title_color_set"] = bool(extra.get("title_color_set")) or (
            bool(_hex(extra.get("title_color"))) and card["title_color"] != palette(light)["dim"]
        )
        card["value_color_set"] = bool(extra.get("value_color_set")) or (
            bool(_hex(extra.get("value_color"))) and card["value_color"] != OK
        )
    base["rev"] = int(data.get("rev") or 0)
    if base["rev"] <= 0 and not style_is_default(base):
        base["rev"] = 1
    return base


def save_state(state: dict) -> None:
    try:
        PREVIEW_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def style_is_default(state: dict) -> bool:
    defaults = default_state(bool(state.get("light")))
    for card, default in zip(state.get("cards") or [], defaults["cards"]):
        if str(card.get("title") or "") != default["title"]:
            return False
        if str(card.get("metric") or default["metric"]) != default["metric"]:
            return False
        if display_sub_metrics(card) != [default["sub_metric"]]:
            return False
        if card_value_size(card) != VALUE_SIZE_DEFAULT or card_sub_size(card) != SUB_SIZE_DEFAULT:
            return False
        if bool(card.get("chart", True)) is False:
            return False
        if str(card.get("chart_metric") or ""):
            return False
        title_color = _hex(card.get("title_color")) or default["title_color"]
        value_color = _hex(card.get("value_color")) or default["value_color"]
        if title_color != default["title_color"] or value_color != default["value_color"]:
            return False
    return True


def control_payload(state: dict) -> dict:
    rev = int(state.get("rev") or 0)
    if style_is_default(state):
        return {"reset": True, "rev": rev}
    defaults = default_state(bool(state.get("light")))
    cards = []
    for card, default in zip(state.get("cards") or [], defaults["cards"]):
        item: dict = {"key": card.get("key")}
        title = str(card.get("title") or "")
        if title and title != default["title"]:
            item["title"] = title[:8]
        metric = str(card.get("metric") or default["metric"])
        if metric != default["metric"] and metric in METRIC_LABEL:
            item["metric"] = metric
        subs = card_sub_metrics(card) or [default["sub_metric"]]
        if subs != [default["sub_metric"]]:
            item["subMetric"] = subs[0]
            if len(subs) > 1 or subs[0] == NONE_METRIC:
                item["subMetrics"] = subs
        title_color = _hex(card.get("title_color"))
        if card.get("title_color_set") and title_color:
            item["titleColor"] = title_color
        elif title_color and title_color != default["title_color"]:
            item["titleColor"] = title_color
        value_color = _hex(card.get("value_color"))
        if card.get("value_color_set") and value_color:
            item["valueColor"] = value_color
        elif value_color and value_color != default["value_color"]:
            item["valueColor"] = value_color
        value_size = card_value_size(card)
        if value_size != VALUE_SIZE_DEFAULT:
            item["valueSize"] = value_size
        sub_size = card_sub_size(card)
        if sub_size != SUB_SIZE_DEFAULT:
            item["subSize"] = sub_size
        if not bool(card.get("chart", True)):
            item["chart"] = False
        chart_metric = str(card.get("chart_metric") or "")
        if is_chartable(chart_metric):
            item["chartMetric"] = chart_metric
        cards.append(item)
    return {"cards": cards, "reset": False, "rev": rev}


def state_from_payload(payload: dict, light: bool) -> dict:
    if not isinstance(payload, dict) or payload.get("reset"):
        state = default_state(light)
        state["rev"] = int((payload or {}).get("rev") or 0)
        return state
    state = default_state(light)
    state["rev"] = int(payload.get("rev") or 0)
    saved = {item.get("key"): item for item in payload.get("cards") or [] if isinstance(item, dict)}
    colors = palette(light)
    for card in state["cards"]:
        extra = saved.get(card["key"]) or {}
        if extra.get("title"):
            card["title"] = str(extra["title"])[:8]
        metric = str(extra.get("metric") or "")
        if metric in METRIC_LABEL:
            card["metric"] = metric
        subs = card_sub_metrics(extra)
        if subs:
            store_sub_metrics(card, subs)
        card["value_size"] = card_value_size(extra)
        card["sub_size"] = card_sub_size(extra)
        if "chart" in extra:
            card["chart"] = bool(extra.get("chart"))
        chart_metric = str(extra.get("chart_metric") or extra.get("chartMetric") or "")
        if chart_metric == CHART_FOLLOW:
            card["chart_metric"] = ""
        elif is_chartable(chart_metric):
            card["chart_metric"] = chart_metric
        elif "chartMetric" in extra or "chart_metric" in extra:
            card["chart_metric"] = ""
        if _hex(extra.get("titleColor") or extra.get("title_color")):
            card["title_color"] = _hex(extra.get("titleColor") or extra.get("title_color"))
            card["title_color_set"] = card["title_color"] != colors["dim"]
        if _hex(extra.get("valueColor") or extra.get("value_color")):
            card["value_color"] = _hex(extra.get("valueColor") or extra.get("value_color"))
            card["value_color_set"] = card["value_color"] != OK
    return state


def replace_state(state: dict) -> None:
    save_state(state)
    win = _open_win
    if win is None:
        return
    try:
        if win.root.winfo_exists():
            win.apply_state(state)
    except tk.TclError:
        pass


def set_light(light: bool) -> None:
    light = bool(light)
    win = _open_win
    if win is None:
        return
    try:
        if not win.root.winfo_exists():
            return
    except tk.TclError:
        return
    if bool(win.state.get("light")) == light and bool(win.light_var.get()) == light:
        return
    win._remote = True
    try:
        win.state["light"] = light
        win.light_var.set(light)
        win._redraw()
    finally:
        win._remote = False


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
    canvas.create_text(dp(36), dp(27), text="USB ADB", fill=colors["dim"], font=top_font, anchor="sw")
    mid_font = _font(11)
    mid = _fit(mid_font, "电脑  ·  预览", w - dp(22) - dp(110))
    canvas.create_text(dp(110), dp(27), text=mid, fill=colors["dim"], font=mid_font, anchor="sw")

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


def _fit_size(size_dp: float, medium: bool, text: str, max_width: float, min_dp: float) -> float:
    size = float(size_dp)
    while size > min_dp:
        spec = tkfont.Font(font=_font(size, medium))
        if spec.measure(text or "") <= max_width:
            return size
        size -= 1
    return min_dp


def _draw_card(canvas: tk.Canvas, x: float, y: float, cw: float, ch: float, card: dict, colors: dict[str, str]) -> None:
    _round_rect(canvas, x, y, x + cw, y + ch, dp(12), colors["card"])
    title = str(card.get("title") or "")
    value = metric_sample(str(card.get("metric") or "cpu"))
    subs = [sub_metric_sample(key) for key in display_sub_metrics(card)]
    title_color = _hex(card.get("title_color")) or colors["dim"]
    value_color = _hex(card.get("value_color")) or OK
    inner_w = max(dp(24), cw - dp(20))
    title_dp = _fit_size(13, False, title, inner_w, 9)
    value_dp = _fit_size(card_value_size(card), True, value, inner_w, VALUE_SIZE_MIN)
    sub_dp = float(card_sub_size(card))
    for line in subs:
        sub_dp = _fit_size(sub_dp, False, line, inner_w, SUB_SIZE_MIN)
    bar_space = dp(16)
    show_chart = bool(card.get("chart", True))
    usable = y + ch - bar_space - (dp(40) if show_chart else 0)

    def _layout() -> tuple[float, float, float]:
        title_y = y + dp(8) + dp(title_dp)
        value_y = title_y + dp(4) + dp(value_dp)
        sub_y = value_y
        for _line in subs:
            sub_y = sub_y + dp(3) + dp(sub_dp)
        return title_y, value_y, sub_y

    title_y, value_y, sub_y = _layout()
    while sub_y > usable + 1:
        shrunk = False
        if value_dp > VALUE_SIZE_MIN:
            value_dp = max(VALUE_SIZE_MIN, value_dp - 1)
            shrunk = True
        if subs and sub_dp > SUB_SIZE_MIN:
            sub_dp = max(SUB_SIZE_MIN, sub_dp - 1)
            shrunk = True
        if title_dp > 9:
            title_dp = max(9, title_dp - 1)
            shrunk = True
        if not shrunk:
            break
        title_y, value_y, sub_y = _layout()
    title_font = _font(title_dp)
    value_font = _font(value_dp, medium=True)
    sub_font = _font(sub_dp)
    canvas.create_text(x + dp(10), title_y, text=_fit(title_font, title, inner_w), fill=title_color, font=title_font, anchor="sw")
    canvas.create_text(x + dp(10), value_y, text=_fit(value_font, value, inner_w), fill=value_color, font=value_font, anchor="sw")
    line_y = value_y
    for line in subs:
        line_y = line_y + dp(3) + dp(sub_dp)
        canvas.create_text(x + dp(10), line_y, text=_fit(sub_font, line, inner_w), fill=colors["dim"], font=sub_font, anchor="sw")

    if show_chart:
        chart_top = (sub_y if subs else value_y) + dp(8)
        chart_bottom = y + ch - bar_space - dp(2)
        if chart_bottom - chart_top >= dp(18):
            chart_metric = str(card.get("chart_metric") or "") or str(card.get("metric") or "cpu")
            _draw_spark(canvas, x + dp(10), chart_top, x + cw - dp(10), chart_bottom,
                        value_color, hash(chart_metric) % 12)

    bar_top = y + ch - dp(14)
    bar_l, bar_r = x + dp(10), x + cw - dp(10)
    _round_rect(canvas, bar_l, bar_top, bar_r, bar_top + dp(7), dp(4), colors["meter_bg"])
    fill = max(dp(6), (cw - dp(20)) * _bar_fill(value))
    _round_rect(canvas, bar_l, bar_top, bar_l + fill, bar_top + dp(7), dp(4), value_color)


def _draw_spark(
    canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, color: str, seed: int
) -> None:
    n = 24
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    pts: list[float] = []
    fill: list[float] = [x1, y2]
    for i in range(n):
        t = i / (n - 1)
        wave = 0.38 + 0.28 * math.sin(t * 4.4 + seed) + 0.1 * math.sin(t * 11.0 + seed * 1.7)
        wave = max(0.06, min(0.94, wave))
        x = x1 + width * t
        y = y2 - height * wave
        pts.extend((x, y))
        fill.extend((x, y))
    fill.extend((x2, y2))
    fill_color = color if len(color) != 7 else color + "33"
    try:
        canvas.create_polygon(*fill, fill=fill_color, outline="")
    except tk.TclError:
        pass
    canvas.create_line(*pts, fill=color, width=2, smooth=True, capstyle="round", joinstyle="round")


def _draw_mute(canvas: tk.Canvas, rect: tuple[float, float, float, float], label: str, colors: dict[str, str]) -> None:
    x1, y1, x2, y2 = rect
    _round_rect(canvas, x1, y1, x2, y2, dp(12), colors["button"])
    font = _font(16, medium=True)
    canvas.create_text((x1 + x2) / 2.0, y1 + (y2 - y1) * 0.66, text=label, fill=colors["text"], font=font, anchor="s")


def open_window(parent: tk.Misc, light: bool = False, on_change=None) -> tk.Toplevel:
    global _open_root, _open_win
    if _open_win is not None:
        try:
            if _open_win.root.winfo_exists():
                _open_win.on_change = on_change
                _open_win.root.lift()
                _open_win.root.focus_force()
                return _open_win.root
        except tk.TclError:
            _open_win = None
            _open_root = None
    win = PreviewWindow(parent, light, on_change)
    _open_win = win
    _open_root = win.root
    return win.root


def live_state(light: bool = False) -> dict:
    win = _open_win
    if win is not None:
        try:
            if win.root.winfo_exists():
                win._cards_from_vars()
                return win.state
        except tk.TclError:
            pass
    return load_state(light)


class PreviewWindow:
    def __init__(self, parent: tk.Misc, light: bool, on_change=None) -> None:
        self.on_change = on_change
        self.root = tk.Toplevel(parent)
        self.root.title("音箱屏幕预览")
        self.root.configure(bg="#0B1220")
        self.root.resizable(False, False)
        self.state = load_state(light)
        self._saving = False
        self._remote = False
        self.light_var = tk.BooleanVar(value=bool(self.state["light"]))
        self.title_vars: list[tk.StringVar] = []
        self.metric_vars: list[tk.StringVar] = []
        self.sub_metric_vars: list[list[tk.StringVar]] = []
        self.sub_frames: list[tk.Frame] = []
        self._combo_bg = "#F3F6FB"
        self._combo_fg = "#1A2333"
        self.value_size_vars: list[tk.IntVar] = []
        self.sub_size_vars: list[tk.IntVar] = []
        self.chart_vars: list[tk.BooleanVar] = []
        self.chart_metric_vars: list[tk.StringVar] = []
        self._swatches: list[tuple[tk.Button, tk.Button]] = []

        hint = ttk.Label(
            self.root,
            text="每个格子可加大字和多条小字。音箱上长按栏目也能改，两边会同步。",
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
        ttk.Label(tools, text="浅色和板块样式会同步到已连接的音箱。", style="CardDim.TLabel").pack(side="left")
        ttk.Button(tools, text="恢复默认", command=self._reset).pack(side="right", padx=8, pady=6)

        editors = tk.Frame(self.root, bg="#141C2E")
        editors.pack(fill="x", padx=16, pady=(0, 16))
        header = tk.Frame(editors, bg="#141C2E")
        header.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(header, text="板块", style="CardDim.TLabel", width=6).pack(side="left")
        ttk.Label(header, text="标题字母", style="CardDim.TLabel", width=10).pack(side="left")
        ttk.Label(header, text="字母色", style="CardDim.TLabel", width=8).pack(side="left")
        ttk.Label(header, text="大字内容", style="CardDim.TLabel", width=14).pack(side="left")
        ttk.Label(header, text="大字色", style="CardDim.TLabel", width=8).pack(side="left")
        ttk.Label(header, text="小字内容", style="CardDim.TLabel", width=18).pack(side="left")
        ttk.Label(header, text="大字号", style="CardDim.TLabel", width=7).pack(side="left")
        ttk.Label(header, text="小字号", style="CardDim.TLabel", width=7).pack(side="left")
        ttk.Label(header, text="折线", style="CardDim.TLabel", width=6).pack(side="left")
        ttk.Label(header, text="折线内容", style="CardDim.TLabel").pack(side="left")

        combo_bg = self._combo_bg
        combo_fg = self._combo_fg
        for index, (_key, label, _metric, _sub) in enumerate(DEFAULT_SLOTS):
            card = self.state["cards"][index]
            row = tk.Frame(editors, bg="#141C2E")
            row.pack(fill="x", padx=8, pady=4)
            ttk.Label(row, text=label, style="Card.TLabel", width=6).pack(side="left", anchor="n", pady=4)
            title_var = tk.StringVar(value=str(card["title"]))
            metric_var = tk.StringVar(value=metric_label(str(card.get("metric") or _metric)))
            value_size_var = tk.IntVar(value=card_value_size(card))
            sub_size_var = tk.IntVar(value=card_sub_size(card))
            chart_var = tk.BooleanVar(value=bool(card.get("chart", True)))
            chart_metric_var = tk.StringVar(value=chart_metric_label(str(card.get("chart_metric") or "")))
            self.title_vars.append(title_var)
            self.metric_vars.append(metric_var)
            self.sub_metric_vars.append([])
            self.value_size_vars.append(value_size_var)
            self.sub_size_vars.append(sub_size_var)
            self.chart_vars.append(chart_var)
            self.chart_metric_vars.append(chart_metric_var)
            ttk.Entry(row, textvariable=title_var, width=10).pack(side="left", padx=(0, 6), anchor="n", pady=4)
            title_swatch = tk.Button(row, width=3, relief="groove", bd=1, command=lambda i=index: self._pick(i, "title"))
            title_swatch.pack(side="left", padx=(0, 12), anchor="n", pady=4)
            drop = ttk.Menubutton(row, textvariable=metric_var, style="Drop.TMenubutton", width=12, direction="below")
            menu = self._metric_menu(drop, metric_var, combo_bg, combo_fg, lambda i=index: self._on_metric(i))
            drop["menu"] = menu
            drop.pack(side="left", padx=(0, 12), anchor="n", pady=4)
            value_swatch = tk.Button(row, width=3, relief="groove", bd=1, command=lambda i=index: self._pick(i, "value"))
            value_swatch.pack(side="left", padx=(0, 12), anchor="n", pady=4)
            sub_col = tk.Frame(row, bg="#141C2E")
            sub_col.pack(side="left", padx=(0, 8))
            self.sub_frames.append(sub_col)
            self._rebuild_sub_col(index)
            ttk.Spinbox(
                row,
                from_=VALUE_SIZE_MIN,
                to=VALUE_SIZE_MAX,
                increment=1,
                textvariable=value_size_var,
                width=4,
                command=lambda i=index: self._on_text(i),
            ).pack(side="left", padx=(0, 8), anchor="n", pady=4)
            ttk.Spinbox(
                row,
                from_=SUB_SIZE_MIN,
                to=SUB_SIZE_MAX,
                increment=1,
                textvariable=sub_size_var,
                width=4,
                command=lambda i=index: self._on_text(i),
            ).pack(side="left", padx=(0, 8), anchor="n", pady=4)
            tk.Checkbutton(
                row,
                text="开",
                variable=chart_var,
                command=lambda i=index: self._on_text(i),
                bg="#141C2E",
                fg="#E8EEF8",
                selectcolor="#1E2A44",
                activebackground="#141C2E",
                activeforeground="#E8EEF8",
                highlightthickness=0,
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(0, 8), anchor="n", pady=4)
            chart_drop = ttk.Menubutton(
                row, textvariable=chart_metric_var, style="Drop.TMenubutton", width=12, direction="below"
            )
            chart_menu = self._metric_menu(
                chart_drop,
                chart_metric_var,
                combo_bg,
                combo_fg,
                lambda i=index: self._on_chart_metric(i),
                include_follow=True,
            )
            chart_drop["menu"] = chart_menu
            chart_drop.pack(side="left", anchor="n", pady=4)
            self._swatches.append((title_swatch, value_swatch))
            title_var.trace_add("write", lambda *_a, i=index: self._on_text(i))
            value_size_var.trace_add("write", lambda *_a, i=index: self._on_text(i))
            sub_size_var.trace_add("write", lambda *_a, i=index: self._on_text(i))

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._paint_swatches()
        self._redraw()

    def apply_state(self, state: dict) -> None:
        self._remote = True
        try:
            self.state = state
            self.light_var.set(bool(state.get("light")))
            for index, card in enumerate(self.state["cards"]):
                self.title_vars[index].set(str(card.get("title") or DEFAULT_SLOTS[index][1]))
                self.metric_vars[index].set(metric_label(str(card.get("metric") or DEFAULT_SLOTS[index][2])))
                self._rebuild_sub_col(index)
                self.value_size_vars[index].set(card_value_size(card))
                self.sub_size_vars[index].set(card_sub_size(card))
                self.chart_vars[index].set(bool(card.get("chart", True)))
                self.chart_metric_vars[index].set(chart_metric_label(str(card.get("chart_metric") or "")))
            self._paint_swatches()
            self._redraw()
        finally:
            self._remote = False

    def _metric_menu(
        self, drop, variable, combo_bg, combo_fg, command, include_none: bool = False, include_follow: bool = False
    ) -> tk.Menu:
        menu = tk.Menu(
            drop,
            tearoff=False,
            font=("Segoe UI", 10),
            bg=combo_bg,
            fg=combo_fg,
            activebackground="#C5E9D6",
            activeforeground=combo_fg,
            relief="solid",
            borderwidth=1,
        )
        if include_none:
            menu.add_radiobutton(label=NONE_LABEL, variable=variable, value=NONE_LABEL, command=command)
        if include_follow:
            menu.add_radiobutton(
                label=CHART_FOLLOW_LABEL, variable=variable, value=CHART_FOLLOW_LABEL, command=command
            )
        keys = CHART_METRICS if include_follow else None
        for mkey, mlabel, _sample in METRICS:
            if keys is not None and mkey not in keys:
                continue
            menu.add_radiobutton(label=mlabel, variable=variable, value=mlabel, command=command)
        return menu

    def _cards_from_vars(self) -> None:
        for index, card in enumerate(self.state["cards"]):
            card["title"] = self.title_vars[index].get()[:8]
            card["metric"] = metric_key(self.metric_vars[index].get())
            keys = [sub_metric_key(var.get()) for var in self.sub_metric_vars[index]]
            store_sub_metrics(card, keys)
            card["value_size"] = self._spin_int(self.value_size_vars[index], VALUE_SIZE_DEFAULT, VALUE_SIZE_MIN, VALUE_SIZE_MAX)
            card["sub_size"] = self._spin_int(self.sub_size_vars[index], SUB_SIZE_DEFAULT, SUB_SIZE_MIN, SUB_SIZE_MAX)
            card["chart"] = bool(self.chart_vars[index].get())
            card["chart_metric"] = chart_metric_key(self.chart_metric_vars[index].get())

    @staticmethod
    def _spin_int(var: tk.IntVar, default: int, lo: int, hi: int) -> int:
        try:
            return clamp_int(var.get(), default, lo, hi)
        except (tk.TclError, ValueError, TypeError):
            return default

    def _on_metric(self, index: int) -> None:
        card = self.state["cards"][index]
        old_metric = str(card.get("metric") or DEFAULT_SLOTS[index][2])
        new_metric = metric_key(self.metric_vars[index].get())
        old_title = default_title_for(old_metric, DEFAULT_SLOTS[index][1])
        if self.title_vars[index].get() in {"", old_title, DEFAULT_SLOTS[index][1], "D:"}:
            self.title_vars[index].set(default_title_for(new_metric, DEFAULT_SLOTS[index][1]))
        card["metric"] = new_metric
        self._on_text(index)

    def _rebuild_sub_col(self, index: int) -> None:
        frame = self.sub_frames[index]
        for child in frame.winfo_children():
            child.destroy()
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        vars: list[tk.StringVar] = []
        for line, key in enumerate(keys):
            row = tk.Frame(frame, bg="#141C2E")
            row.pack(fill="x", pady=1)
            var = tk.StringVar(value=sub_metric_label(key))
            drop = ttk.Menubutton(row, textvariable=var, style="Drop.TMenubutton", width=12, direction="below")
            drop["menu"] = self._metric_menu(
                drop,
                var,
                self._combo_bg,
                self._combo_fg,
                lambda i=index, n=line: self._on_sub_metric(i, n),
                include_none=True,
            )
            drop.pack(side="left")
            ttk.Button(row, text="×", width=2, command=lambda i=index, n=line: self._remove_sub(i, n)).pack(
                side="left", padx=(4, 0)
            )
            vars.append(var)
        if len(keys) < MAX_SUBS:
            ttk.Button(frame, text="+ 小字", command=lambda i=index: self._add_sub(i)).pack(
                anchor="w", pady=(2, 0)
            )
        self.sub_metric_vars[index] = vars

    def _add_sub(self, index: int) -> None:
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        if len(keys) >= MAX_SUBS:
            return
        used = set(keys)
        nxt = next((key for key, _label, _sample in METRICS if key not in used), METRICS[0][0])
        keys.append(nxt)
        store_sub_metrics(self.state["cards"][index], keys)
        self._rebuild_sub_col(index)
        self._on_text(index)

    def _remove_sub(self, index: int, line: int) -> None:
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        if line < 0 or line >= len(keys):
            return
        if len(keys) == 1:
            keys = [NONE_METRIC]
        else:
            keys.pop(line)
        store_sub_metrics(self.state["cards"][index], keys)
        self._rebuild_sub_col(index)
        self._on_text(index)

    def _on_sub_metric(self, index: int, line: int = 0) -> None:
        keys = [sub_metric_key(var.get()) for var in self.sub_metric_vars[index]]
        if 0 <= line < len(keys):
            keys[line] = sub_metric_key(self.sub_metric_vars[index][line].get())
        store_sub_metrics(self.state["cards"][index], keys)
        self._on_text(index)

    def _on_chart_metric(self, index: int) -> None:
        self.state["cards"][index]["chart_metric"] = chart_metric_key(self.chart_metric_vars[index].get())
        self._on_text(index)

    def _on_text(self, _index: int) -> None:
        if self._remote:
            return
        self._cards_from_vars()
        self._redraw()
        self._schedule_save()

    def _on_light(self) -> None:
        if self._remote:
            return
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
        self.state["cards"][index]["title_color_set" if which == "title" else "value_color_set"] = True
        self._paint_swatches()
        self._redraw()
        self._schedule_save()

    def _reset(self) -> None:
        self.state = default_state(bool(self.light_var.get()))
        bump_rev(self.state)
        self.light_var.set(bool(self.state["light"]))
        for index, card in enumerate(self.state["cards"]):
            self.metric_vars[index].set(metric_label(str(card.get("metric") or DEFAULT_SLOTS[index][2])))
            self._rebuild_sub_col(index)
            self.value_size_vars[index].set(card_value_size(card))
            self.sub_size_vars[index].set(card_sub_size(card))
            self.chart_vars[index].set(bool(card.get("chart", True)))
            self.chart_metric_vars[index].set(chart_metric_label(str(card.get("chart_metric") or "")))
            self.title_vars[index].set(card["title"])
        self._paint_swatches()
        self._redraw()
        save_state(self.state)
        self._emit(reset=True)

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
        if self._remote:
            return
        self._cards_from_vars()
        bump_rev(self.state)
        save_state(self.state)
        self._emit(reset=False)

    def _emit(self, reset: bool = False) -> None:
        callback = self.on_change
        if callback is None:
            return
        try:
            callback(self.state, reset)
        except Exception:
            pass

    def _close(self) -> None:
        global _open_root, _open_win
        self._cards_from_vars()
        save_state(self.state)
        self._emit(reset=False)
        _open_win = None
        _open_root = None
        self.root.destroy()
