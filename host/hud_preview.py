"""Host-side 800x480 mock of the LX04 HUD. Style only; no live PC stats."""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk

from PySide6.QtGui import QFont, QFontMetricsF

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


_LIVE: dict[str, str] = {}


def set_live_samples(samples: dict | None) -> None:
    global _LIVE
    _LIVE = {str(k): str(v) for k, v in (samples or {}).items()}


def metric_sample(key: str) -> str:
    if _LIVE:
        return str(_LIVE.get(key) or "—")
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

_tk_root: tk.Tk | None = None
_session: HudSession | None = None


def ensure_tk() -> tk.Misc:
    global _tk_root
    if _tk_root is None:
        _tk_root = tk.Tk()
        _tk_root.withdraw()
    return _tk_root


def shutdown_tk() -> None:
    global _tk_root
    if _tk_root is None:
        return
    try:
        _tk_root.destroy()
    except Exception:
        pass
    _tk_root = None


_font_cache: dict[tuple, QFont] = {}
_metrics_cache: dict[tuple, QFontMetricsF] = {}


def _qfont(spec: tuple) -> QFont:
    family = str(spec[0])
    px = max(8, abs(int(spec[1])))
    weight = str(spec[2]) if len(spec) > 2 else "normal"
    key = (family, px, weight)
    qf = _font_cache.get(key)
    if qf is None:
        qf = QFont(family)
        qf.setPixelSize(px)
        qf.setBold(weight == "bold")
        _font_cache[key] = qf
    return qf


def _metrics(spec: tuple) -> QFontMetricsF:
    qf = _qfont(spec)
    key = (qf.family(), qf.pixelSize(), qf.bold())
    fm = _metrics_cache.get(key)
    if fm is None:
        fm = QFontMetricsF(qf)
        _metrics_cache[key] = fm
    return fm


def _measure(spec: tuple, text: str) -> float:
    return float(_metrics(spec).horizontalAdvance(text or ""))


_DP_SCALE = 1.0


def dp(value: float) -> float:
    return value * DENSITY * _DP_SCALE


def _hud_fit(cw: float, ch: float) -> tuple[float, float, float, float, float]:
    """Scale 800x480 into cw x ch, letterboxed. Returns scale, w, h, ox, oy."""
    cw = max(1.0, float(cw))
    ch = max(1.0, float(ch))
    scale = min(cw / SCREEN_W, ch / SCREEN_H)
    w, h = SCREEN_W * scale, SCREEN_H * scale
    return scale, w, h, (cw - w) / 2.0, (ch - h) / 2.0


class _OffsetCanvas:
    """Draw in scaled 800x480 space, then shift into the letterbox."""

    def __init__(self, canvas: tk.Canvas, ox: float, oy: float) -> None:
        self._c = canvas
        self._ox = ox
        self._oy = oy

    def create_rectangle(self, x1, y1, x2, y2, **kw):
        return self._c.create_rectangle(x1 + self._ox, y1 + self._oy, x2 + self._ox, y2 + self._oy, **kw)

    def create_oval(self, x1, y1, x2, y2, **kw):
        return self._c.create_oval(x1 + self._ox, y1 + self._oy, x2 + self._ox, y2 + self._oy, **kw)

    def create_text(self, x, y, **kw):
        return self._c.create_text(x + self._ox, y + self._oy, **kw)

    def _shift_pts(self, pts):
        out: list[float] = []
        for i, p in enumerate(pts):
            out.append(p + (self._ox if i % 2 == 0 else self._oy))
        return out

    def create_line(self, *pts, **kw):
        return self._c.create_line(*self._shift_pts(pts), **kw)

    def create_polygon(self, *pts, **kw):
        return self._c.create_polygon(*self._shift_pts(pts), **kw)


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
                "value_color_to": BAD,
                "title_color_set": False,
                "value_color_set": False,
                "value_color_to_set": False,
                "value_shift": False,
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
        if _hex(extra.get("value_color_to") or extra.get("valueColorTo")):
            card["value_color_to"] = _hex(extra.get("value_color_to") or extra.get("valueColorTo"))
        card["title_color_set"] = bool(extra.get("title_color_set")) or (
            bool(_hex(extra.get("title_color"))) and card["title_color"] != palette(light)["dim"]
        )
        card["value_color_set"] = bool(extra.get("value_color_set")) or (
            bool(_hex(extra.get("value_color"))) and card["value_color"] != OK
        )
        card["value_color_to_set"] = bool(extra.get("value_color_to_set")) or (
            bool(_hex(extra.get("value_color_to") or extra.get("valueColorTo")))
            and card["value_color_to"] != BAD
        )
        if extra.get("value_shift") or extra.get("valueShift"):
            card["value_shift"] = True
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
        if bool(card.get("value_shift")):
            return False
        to_color = _hex(card.get("value_color_to")) or default["value_color_to"]
        if card.get("value_color_to_set") or to_color != default["value_color_to"]:
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
        if card.get("value_shift"):
            item["valueShift"] = True
        to_color = _hex(card.get("value_color_to"))
        if card.get("value_color_to_set") and to_color:
            item["valueColorTo"] = to_color
        elif to_color and to_color != default["value_color_to"]:
            item["valueColorTo"] = to_color
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
        if extra.get("valueShift") or extra.get("value_shift"):
            card["value_shift"] = True
        if _hex(extra.get("valueColorTo") or extra.get("value_color_to")):
            card["value_color_to"] = _hex(extra.get("valueColorTo") or extra.get("value_color_to"))
            card["value_color_to_set"] = card["value_color_to"] != BAD
    return state


def replace_state(state: dict) -> None:
    save_state(state)
    if _session is not None:
        _session.apply_state(state)


def set_light(light: bool) -> None:
    light = bool(light)
    if _session is None:
        return
    if bool(_session.state.get("light")) == light:
        return
    _session.set_light(light, remote=True)


def _hex(value: object) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
            return text.upper()
        except ValueError:
            return ""
    return ""


def lerp_color(from_hex: str, to_hex: str, t: float) -> str:
    t = 0.0 if t <= 0 else 1.0 if t >= 1 else t
    start = int((_hex(from_hex) or OK)[1:], 16)
    end = int((_hex(to_hex) or BAD)[1:], 16)

    def ch(shift: int) -> int:
        a = (start >> shift) & 255
        b = (end >> shift) & 255
        return int(math.floor(a + (b - a) * t + 0.5))

    return f"#{ch(16):02X}{ch(8):02X}{ch(0):02X}"


def card_value_paint(card: dict, t: float) -> str:
    from_c = _hex(card.get("value_color")) or OK
    if not card.get("value_shift"):
        return from_c
    to_c = _hex(card.get("value_color_to")) or BAD
    return lerp_color(from_c, to_c, t)


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
    if _measure(font, text) <= max_width:
        return text
    for i in range(len(text) - 1, 0, -1):
        cut = text[:i] + "…"
        if _measure(font, cut) <= max_width:
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


def _canvas_wh(canvas: tk.Canvas) -> tuple[int, int]:
    w = int(canvas.winfo_width() or 0)
    h = int(canvas.winfo_height() or 0)
    if w < 4:
        w = int(canvas.cget("width") or SCREEN_W)
    if h < 4:
        h = int(canvas.cget("height") or SCREEN_H)
    return max(4, w), max(4, h)


def draw_hud(canvas: tk.Canvas, state: dict) -> None:
    global _DP_SCALE
    canvas.delete("all")
    cw, ch = _canvas_wh(canvas)
    light = bool(state.get("light"))
    colors = palette(light)
    cards = list(state.get("cards") or default_state(light)["cards"])
    canvas.create_rectangle(0, 0, cw, ch, fill=colors["bg"], outline="")
    scale, w, h, ox, oy = _hud_fit(cw, ch)
    if scale <= 0:
        return
    old = _DP_SCALE
    _DP_SCALE = scale
    canvas = _OffsetCanvas(canvas, ox, oy)
    try:
        _draw_hud_body(canvas, colors, cards, w, h)
    finally:
        _DP_SCALE = old


def _draw_hud_body(canvas, colors: dict[str, str], cards: list, w: float, h: float) -> None:
    _round_rect(canvas, dp(12), dp(12), w - dp(12), h - dp(12), dp(18), colors["panel"])

    canvas.create_oval(dp(15), dp(15), dp(29), dp(29), fill=OK, outline="")
    top_font = _font(12)
    canvas.create_text(dp(36), dp(27), text="USB ADB", fill=colors["dim"], font=top_font, anchor="sw")
    now = datetime.now()
    clock = f"{now.month}月{now.day}日  {now.strftime('%H:%M:%S')}"
    clock_font = _font(13, medium=True)
    clock_w = _measure(clock_font, clock)
    clock_x = w - dp(40) - clock_w
    canvas.create_text(clock_x, dp(27), text=clock, fill=colors["text"], font=clock_font, anchor="sw")
    mid_font = _font(11)
    mid = _fit(mid_font, "电脑  ·  预览", max(0, clock_x - dp(12) - dp(110)))
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
    down = metric_sample("netD")
    up = metric_sample("netU")
    canvas.create_text(
        dp(18),
        meter_top + dp(14),
        text=f"↓ {down}    ↑ {up}",
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
        if _measure(_font(size, medium), text or "") <= max_width:
            return size
        size -= 1
    return min_dp


def _draw_card(canvas: tk.Canvas, x: float, y: float, cw: float, ch: float, card: dict, colors: dict[str, str]) -> None:
    _round_rect(canvas, x, y, x + cw, y + ch, dp(12), colors["card"])
    title = str(card.get("title") or "")
    value = metric_sample(str(card.get("metric") or "cpu"))
    subs = [sub_metric_sample(key) for key in display_sub_metrics(card)]
    title_color = _hex(card.get("title_color")) or colors["dim"]
    shift_t = 0.0 if not value or value == "—" else _bar_fill(value)
    value_color = card_value_paint(card, shift_t)
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
    canvas.create_line(
        *pts, fill=color, width=max(1, round(2 * _DP_SCALE)), smooth=True, capstyle="round", joinstyle="round"
    )


def _draw_mute(canvas: tk.Canvas, rect: tuple[float, float, float, float], label: str, colors: dict[str, str]) -> None:
    x1, y1, x2, y2 = rect
    _round_rect(canvas, x1, y1, x2, y2, dp(12), colors["button"])
    font = _font(16, medium=True)
    canvas.create_text((x1 + x2) / 2.0, y1 + (y2 - y1) * 0.66, text=label, fill=colors["text"], font=font, anchor="s")


def metric_labels() -> list[str]:
    return [label for _key, label, _sample in METRICS]


def chart_metric_labels() -> list[str]:
    return [CHART_FOLLOW_LABEL] + [metric_label(key) for key in CHART_METRICS]


def sub_metric_labels() -> list[str]:
    return [NONE_LABEL] + metric_labels()


def live_state(light: bool = False) -> dict:
    if _session is not None:
        return _session.state
    return load_state(light)


def open_session(light: bool = False, on_change=None, on_view=None) -> HudSession:
    global _session
    if _session is not None:
        _session.on_change = on_change
        if on_view is not None:
            _session.on_view = on_view
        return _session
    _session = HudSession(light, on_change=on_change, on_view=on_view)
    return _session


def close_session() -> None:
    global _session
    if _session is None:
        return
    save_state(_session.state)
    _session.emit(reset=False)
    _session = None


class HudSession:
    def __init__(self, light: bool, on_change=None, on_view=None) -> None:
        self.on_change = on_change
        self.on_view = on_view
        self.on_editor = None
        self.state = load_state(light)
        self._remote = False
        self._saving = False
        self._flush = None

    def bind_flush(self, fn) -> None:
        self._flush = fn

    def apply_state(self, state: dict) -> None:
        self._remote = True
        try:
            self.state = state
            self.notify()
            if self.on_editor is not None:
                self.on_editor()
        finally:
            self._remote = False

    def set_light(self, light: bool, remote: bool = False) -> None:
        if remote:
            self._remote = True
        try:
            self.state["light"] = bool(light)
            self.notify()
            if remote and self.on_editor is not None:
                self.on_editor()
            if not remote:
                self.schedule_save()
        finally:
            if remote:
                self._remote = False

    def set_title(self, index: int, text: str) -> None:
        self.state["cards"][index]["title"] = str(text)[:8]
        self.touch()

    def set_metric_label(self, index: int, label: str) -> None:
        card = self.state["cards"][index]
        old_metric = str(card.get("metric") or DEFAULT_SLOTS[index][2])
        new_metric = metric_key(label)
        old_title = default_title_for(old_metric, DEFAULT_SLOTS[index][1])
        if str(card.get("title") or "") in {"", old_title, DEFAULT_SLOTS[index][1], "D:"}:
            card["title"] = default_title_for(new_metric, DEFAULT_SLOTS[index][1])
        card["metric"] = new_metric
        self.touch()

    def set_color(self, index: int, which: str, hex_color: str) -> None:
        color = _hex(hex_color)
        if not color:
            return
        keys = {
            "title": ("title_color", "title_color_set"),
            "value": ("value_color", "value_color_set"),
            "valueTo": ("value_color_to", "value_color_to_set"),
        }
        pair = keys.get(which)
        if pair is None:
            return
        key, flag = pair
        self.state["cards"][index][key] = color
        self.state["cards"][index][flag] = True
        self.touch()

    def set_value_shift(self, index: int, on: bool) -> None:
        self.state["cards"][index]["value_shift"] = bool(on)
        self.touch()

    def set_value_size(self, index: int, size: int) -> None:
        self.state["cards"][index]["value_size"] = clamp_int(size, VALUE_SIZE_DEFAULT, VALUE_SIZE_MIN, VALUE_SIZE_MAX)
        self.touch()

    def set_sub_size(self, index: int, size: int) -> None:
        self.state["cards"][index]["sub_size"] = clamp_int(size, SUB_SIZE_DEFAULT, SUB_SIZE_MIN, SUB_SIZE_MAX)
        self.touch()

    def set_chart(self, index: int, on: bool) -> None:
        self.state["cards"][index]["chart"] = bool(on)
        self.touch()

    def set_chart_metric_label(self, index: int, label: str) -> None:
        self.state["cards"][index]["chart_metric"] = chart_metric_key(label)
        self.touch()

    def add_sub(self, index: int) -> None:
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        if len(keys) >= MAX_SUBS:
            return
        used = set(keys)
        nxt = next((key for key, _label, _sample in METRICS if key not in used), METRICS[0][0])
        keys.append(nxt)
        store_sub_metrics(self.state["cards"][index], keys)
        self.touch()

    def remove_sub(self, index: int, line: int) -> None:
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        if line < 0 or line >= len(keys):
            return
        if len(keys) == 1:
            keys = [NONE_METRIC]
        else:
            keys.pop(line)
        store_sub_metrics(self.state["cards"][index], keys)
        self.touch()

    def set_sub_metric_label(self, index: int, line: int, label: str) -> None:
        keys = card_sub_metrics(self.state["cards"][index]) or [DEFAULT_SLOTS[index][3]]
        if line < 0 or line >= len(keys):
            return
        keys[line] = sub_metric_key(label)
        store_sub_metrics(self.state["cards"][index], keys)
        self.touch()

    def reset(self) -> None:
        self.state = default_state(bool(self.state.get("light")))
        bump_rev(self.state)
        save_state(self.state)
        self.notify()
        self.emit(reset=True)

    def close(self) -> None:
        close_session()

    def touch(self) -> None:
        if self._remote:
            return
        self.notify()
        self.schedule_save()

    def notify(self) -> None:
        if self.on_view is not None:
            self.on_view()

    def schedule_save(self) -> None:
        if self._saving:
            return
        self._saving = True
        if self._flush is not None:
            self._flush()
            return
        self.flush_save()

    def flush_save(self) -> None:
        self._saving = False
        if self._remote:
            return
        bump_rev(self.state)
        save_state(self.state)
        self.emit(reset=False)

    def emit(self, reset: bool = False) -> None:
        callback = self.on_change
        if callback is None:
            return
        try:
            callback(self.state, reset)
        except Exception:
            pass

