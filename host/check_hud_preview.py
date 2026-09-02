#!/usr/bin/env python3
"""Assert HUD preview scales and Fluent editor QML can draw the mock."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hud_preview


def main() -> None:
    scale, w, h, ox, oy = hud_preview._hud_fit(800, 480)
    assert abs(scale - 1.0) < 1e-9 and ox == 0 and oy == 0 and w == 800 and h == 480
    scale, w, h, ox, oy = hud_preview._hud_fit(1600, 960)
    assert abs(scale - 2.0) < 1e-9 and ox == 0 and oy == 0
    scale, w, h, ox, oy = hud_preview._hud_fit(1600, 480)
    assert abs(scale - 1.0) < 1e-9 and abs(ox - 400) < 1e-9 and oy == 0
    scale, w, h, ox, oy = hud_preview._hud_fit(800, 960)
    assert abs(scale - 1.0) < 1e-9 and ox == 0 and abs(oy - 240) < 1e-9
    src = Path(hud_preview.__file__).read_text(encoding="utf-8")
    assert "PreviewWindow" not in src
    hud_preview.set_live_samples({"cpu": "17%"})
    assert hud_preview.metric_sample("cpu") == "17%"
    assert hud_preview.metric_sample("gpu") == "—"
    hud_preview.set_live_samples({})
    assert hud_preview.metric_sample("cpu") == "88%"
    session = hud_preview.HudSession(False)
    session.set_title(0, "CPU")
    assert session.state["cards"][0]["title"] == "CPU"
    assert hud_preview.lerp_color("#3DDC97", "#FF5C7A", 0) == "#3DDC97"
    assert hud_preview.lerp_color("#3DDC97", "#FF5C7A", 1) == "#FF5C7A"
    assert hud_preview.lerp_color("#000000", "#FFFFFF", 0.5) == "#808080"
    assert hud_preview.card_value_paint({"value_color": "#3DDC97"}, 0.9) == "#3DDC97"
    shifted = {"value_color": "#3DDC97", "value_shift": True, "value_color_to": "#FF5C7A"}
    assert hud_preview.card_value_paint(shifted, 0) == "#3DDC97"
    assert hud_preview.card_value_paint(shifted, 1) == "#FF5C7A"
    session.set_value_shift(0, True)
    session.set_color(0, "valueTo", "#FF5C7A")
    payload = hud_preview.control_payload(session.state)
    cpu = payload["cards"][0]
    assert cpu.get("valueShift") is True
    assert cpu.get("valueColorTo") == "#FF5C7A"
    back = hud_preview.state_from_payload(payload, False)
    assert back["cards"][0]["value_shift"] is True
    assert back["cards"][0]["value_color_to"] == "#FF5C7A"
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from qt_ui import PainterCanvas, apply_fluent_style

    app = QApplication.instance() or QApplication([])
    apply_fluent_style()
    img = QImage(800, 480, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    hud_preview.draw_hud(PainterCanvas(painter, 800, 480), session.state)
    painter.end()
    dot = img.pixelColor(33, 33)
    assert dot.green() > 150 and dot.red() < 120, (dot.red(), dot.green(), dot.blue())
    hud_preview.close_session()
    hud_preview.shutdown_tk()
    print("ok")


if __name__ == "__main__":
    main()
