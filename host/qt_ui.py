"""PySide6 QML shell: FluentWinUI3 style + HostApp bindings."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QObject,
    QPointF,
    QRectF,
    QStringListModel,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtQml import QQmlComponent, qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QColorDialog, QFileDialog, QMessageBox

import hud_preview


def _fmt_rate(n: float) -> str:
    n = float(n)
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB/s"
    if n >= 1024:
        return f"{n / 1024:.0f} KB/s"
    return f"{n:.0f} B/s"


class Var:
    """tk.Variable stand-in: get/set plus optional notify."""

    def __init__(self, value=None, on_change=None) -> None:
        self._value = value
        self._on_change = on_change

    def get(self):
        return self._value

    def set(self, value) -> None:
        if value == self._value:
            return
        self._value = value
        if self._on_change:
            self._on_change()


class QtLoop(QObject):
    """tk.Misc.after/withdraw subset. Timers always arm on the GUI thread."""

    _arm_sig = Signal(int, int, object)

    def __init__(self) -> None:
        super().__init__()
        self.window = None
        self._timers: dict[int, QTimer] = {}
        self._n = 1
        self._lock = threading.Lock()
        self._arm_sig.connect(self._arm)

    def after(self, ms, fn):
        with self._lock:
            tid = self._n
            self._n += 1
        self._arm_sig.emit(tid, max(0, int(ms)), fn)
        return tid

    def after_idle(self, fn):
        return self.after(0, fn)

    def after_cancel(self, tid) -> None:
        timer = self._timers.pop(tid, None)
        if timer is not None:
            timer.stop()

    def _arm(self, tid: int, ms: int, fn) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._fire(tid, fn))
        self._timers[tid] = timer
        timer.start(ms)

    def _fire(self, tid: int, fn) -> None:
        self._timers.pop(tid, None)
        fn()

    def withdraw(self) -> None:
        if self.window is not None:
            self.window.hide()

    def destroy(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def update_idletasks(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def update(self) -> None:
        self.update_idletasks()

    def winfo_id(self) -> int:
        if self.window is None:
            return 0
        return int(self.window.winId())


class _TextSink:
    def __init__(self, setter) -> None:
        self._setter = setter

    def configure(self, text=None, **_kwargs) -> None:
        if text is not None:
            self._setter(text)

    def pack(self, **_kwargs) -> None:
        pass

    def bind(self, *_args, **_kwargs) -> None:
        pass


class _LogBox:
    def __init__(self, emit_line) -> None:
        self._emit = emit_line

    def insert(self, _pos, text: str) -> None:
        self._emit(str(text).rstrip("\n"))

    def see(self, _pos) -> None:
        pass


_HUD_TYPE = False


class PainterCanvas:
    """Duck-type tk.Canvas so draw_hud layout stays the speaker mock."""

    def __init__(self, painter: QPainter, width: int, height: int) -> None:
        self._p = painter
        self._w = max(4, int(width))
        self._h = max(4, int(height))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    def delete(self, _what) -> None:
        return

    def winfo_width(self) -> int:
        return self._w

    def winfo_height(self) -> int:
        return self._h

    def cget(self, key: str):
        if key == "width":
            return self._w
        if key == "height":
            return self._h
        return ""

    def configure(self, **kw) -> None:
        bg = kw.get("bg")
        if bg:
            self._p.fillRect(0, 0, self._w, self._h, QColor(str(bg)))

    def create_rectangle(self, x1, y1, x2, y2, **kw) -> None:
        fill = str(kw.get("fill") or "")
        if not fill:
            return
        self._p.setPen(Qt.PenStyle.NoPen)
        self._p.setBrush(QColor(fill))
        x, y = min(x1, x2), min(y1, y2)
        self._p.drawRect(QRectF(x, y, abs(x2 - x1), abs(y2 - y1)))

    def create_oval(self, x1, y1, x2, y2, **kw) -> None:
        fill = str(kw.get("fill") or "")
        if not fill:
            return
        self._p.setPen(Qt.PenStyle.NoPen)
        self._p.setBrush(QColor(fill))
        x, y = min(x1, x2), min(y1, y2)
        self._p.drawEllipse(QRectF(x, y, abs(x2 - x1), abs(y2 - y1)))

    def create_polygon(self, *pts, **kw) -> None:
        fill = str(kw.get("fill") or "")
        if not fill or len(pts) < 6:
            return
        path = QPainterPath()
        path.moveTo(float(pts[0]), float(pts[1]))
        for i in range(2, len(pts), 2):
            path.lineTo(float(pts[i]), float(pts[i + 1]))
        path.closeSubpath()
        self._p.setPen(Qt.PenStyle.NoPen)
        self._p.setBrush(QColor(fill))
        self._p.drawPath(path)

    def create_line(self, *pts, **kw) -> None:
        if len(pts) < 4:
            return
        color = QColor(str(kw.get("fill") or "#ffffff"))
        pen = QPen(color, float(kw.get("width") or 1))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._p.setPen(pen)
        self._p.setBrush(Qt.BrushStyle.NoBrush)
        points = [QPointF(float(pts[i]), float(pts[i + 1])) for i in range(0, len(pts) - 1, 2)]
        if kw.get("smooth"):
            path = QPainterPath(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            self._p.drawPath(path)
            return
        self._p.drawPolyline(QPolygonF(points))

    def create_text(self, x, y, **kw) -> None:
        text = str(kw.get("text") or "")
        if not text:
            return
        spec = kw.get("font") or ("Microsoft YaHei UI", -12, "normal")
        qf = QFont(str(spec[0]))
        qf.setPixelSize(max(8, abs(int(spec[1]))))
        qf.setBold(len(spec) > 2 and str(spec[2]) == "bold")
        self._p.setFont(qf)
        self._p.setPen(QColor(str(kw.get("fill") or "#ffffff")))
        fm = QFontMetrics(qf)
        tx, ty = float(x), float(y)
        anchor = str(kw.get("anchor") or "c")
        if "s" in anchor:
            ty -= fm.descent()
        elif "n" in anchor:
            ty += fm.ascent()
        else:
            ty += (fm.ascent() - fm.descent()) / 2.0
        if "e" in anchor:
            tx -= fm.horizontalAdvance(text)
        elif "w" not in anchor:
            tx -= fm.horizontalAdvance(text) / 2.0
        self._p.drawText(QPointF(tx, ty), text)


class HudView(QQuickPaintedItem):
    editorChanged = Signal()
    samplesChanged = Signal()
    lightChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._editor = None
        self._samples = {}
        self._light = False
        self.setAntialiasing(True)
        self.setOpaquePainting(True)
        self.setFillColor(QColor("#0B1220"))
        self.setImplicitWidth(800)
        self.setImplicitHeight(480)

    def getEditor(self):
        return self._editor

    def setEditor(self, value) -> None:
        if self._editor is value:
            return
        if self._editor is not None:
            try:
                self._editor.viewTick.disconnect(self._redraw)
            except Exception:
                pass
        self._editor = value
        if value is not None:
            value.viewTick.connect(self._redraw)
        self.editorChanged.emit()
        self._redraw()

    editor = Property(QObject, getEditor, setEditor, notify=editorChanged)

    def getSamples(self):
        return self._samples

    def setSamples(self, value) -> None:
        self._samples = dict(value or {})
        self.samplesChanged.emit()
        self._redraw()

    samples = Property("QVariantMap", getSamples, setSamples, notify=samplesChanged)

    def getLight(self) -> bool:
        return self._light

    def setLight(self, value: bool) -> None:
        value = bool(value)
        if self._light == value:
            return
        self._light = value
        self.lightChanged.emit()
        self._redraw()

    light = Property(bool, getLight, setLight, notify=lightChanged)

    @Slot()
    def tick(self) -> None:
        self._redraw()

    @Slot()
    def _redraw(self) -> None:
        self.update()

    def paint(self, painter: QPainter) -> None:
        w, h = int(self.width()), int(self.height())
        if w < 4 or h < 4:
            return
        hud_preview.set_live_samples(self._samples)
        editor = self._editor
        if editor is not None and editor.session is not None:
            state = editor.session.state
        else:
            state = hud_preview.live_state(self._light)
        hud_preview.draw_hud(PainterCanvas(painter, w, h), state)


def register_hud_types() -> None:
    global _HUD_TYPE
    if _HUD_TYPE:
        return
    qmlRegisterType(HudView, "Lx04", 1, 0, "HudView")
    _HUD_TYPE = True


class HudEditor(QObject):
    viewTick = Signal()
    changed = Signal()
    lightChanged = Signal()
    closed = Signal()

    def __init__(self, on_change=None, light: bool = False) -> None:
        super().__init__()
        self._gen = 0
        self.session = hud_preview.open_session(
            light=light,
            on_change=on_change,
            on_view=self._on_view,
        )
        self.session.on_editor = self._on_editor
        self.session.bind_flush(self._arm_flush)
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.timeout.connect(self.session.flush_save)

    def _arm_flush(self) -> None:
        self._save.start(250)

    def _on_view(self) -> None:
        self.viewTick.emit()

    def _on_editor(self) -> None:
        self._gen += 1
        self.changed.emit()
        self.lightChanged.emit()

    def attach(self, on_change, light: bool) -> None:
        self.session.on_change = on_change
        if bool(self.session.state.get("light")) != bool(light) and hud_preview.style_is_default(self.session.state):
            self.session.set_light(light, remote=True)
        self._on_editor()
        self.viewTick.emit()

    @Property(int, notify=changed)
    def gen(self) -> int:
        return self._gen

    @Property(bool, notify=lightChanged)
    def light(self) -> bool:
        return bool(self.session.state.get("light"))

    @Property(list, constant=True)
    def metricLabels(self) -> list:
        return hud_preview.metric_labels()

    @Property(list, constant=True)
    def chartLabels(self) -> list:
        return hud_preview.chart_metric_labels()

    @Property(list, constant=True)
    def subLabels(self) -> list:
        return hud_preview.sub_metric_labels()

    @Slot(int, result=str)
    def slotName(self, index: int) -> str:
        return hud_preview.DEFAULT_SLOTS[index][1]

    @Slot(int, result=str)
    def cardTitle(self, index: int) -> str:
        return str(self.session.state["cards"][index].get("title") or "")

    @Slot(int, result=int)
    def metricIndex(self, index: int) -> int:
        key = str(self.session.state["cards"][index].get("metric") or hud_preview.DEFAULT_SLOTS[index][2])
        try:
            return self.metricLabels.index(hud_preview.metric_label(key))
        except ValueError:
            return 0

    @Slot(int, result=str)
    def titleColor(self, index: int) -> str:
        return str(self.session.state["cards"][index].get("title_color") or hud_preview.palette(False)["dim"])

    @Slot(int, result=str)
    def valueColor(self, index: int) -> str:
        return str(self.session.state["cards"][index].get("value_color") or hud_preview.OK)

    @Slot(int, result=int)
    def valueSize(self, index: int) -> int:
        return hud_preview.card_value_size(self.session.state["cards"][index])

    @Slot(int, result=int)
    def subSize(self, index: int) -> int:
        return hud_preview.card_sub_size(self.session.state["cards"][index])

    @Slot(int, result=bool)
    def chartOn(self, index: int) -> bool:
        return bool(self.session.state["cards"][index].get("chart", True))

    @Slot(int, result=int)
    def chartIndex(self, index: int) -> int:
        key = str(self.session.state["cards"][index].get("chart_metric") or "")
        labels = self.chartLabels
        if not key:
            return 0
        try:
            return labels.index(hud_preview.metric_label(key))
        except ValueError:
            return 0

    @Slot(int, result="QVariantList")
    def subMetricIndexes(self, index: int) -> list:
        keys = hud_preview.card_sub_metrics(self.session.state["cards"][index]) or [hud_preview.DEFAULT_SLOTS[index][3]]
        labels = self.subLabels
        out = []
        for key in keys:
            lab = hud_preview.sub_metric_label(key)
            try:
                out.append(labels.index(lab))
            except ValueError:
                out.append(0)
        return out

    @Slot(int, str)
    def setTitle(self, index: int, text: str) -> None:
        self.session.set_title(index, text)

    @Slot(int, int)
    def setMetric(self, index: int, combo: int) -> None:
        labels = self.metricLabels
        if 0 <= combo < len(labels):
            self.session.set_metric_label(index, labels[combo])
            self._on_editor()

    @Slot(int, str)
    def pickColor(self, index: int, which: str) -> None:
        current = self.titleColor(index) if which == "title" else self.valueColor(index)
        picked = QColorDialog.getColor(QColor(current), None, "选择颜色")
        if not picked.isValid():
            return
        self.session.set_color(index, which, picked.name().upper())
        self._on_editor()

    @Slot(int, int)
    def setValueSize(self, index: int, size: int) -> None:
        self.session.set_value_size(index, size)

    @Slot(int, int)
    def setSubSize(self, index: int, size: int) -> None:
        self.session.set_sub_size(index, size)

    @Slot(int, bool)
    def setChart(self, index: int, on: bool) -> None:
        self.session.set_chart(index, on)

    @Slot(int, int)
    def setChartMetric(self, index: int, combo: int) -> None:
        labels = self.chartLabels
        if 0 <= combo < len(labels):
            self.session.set_chart_metric_label(index, labels[combo])

    @Slot(int)
    def addSub(self, index: int) -> None:
        self.session.add_sub(index)
        self._on_editor()

    @Slot(int, int)
    def removeSub(self, index: int, line: int) -> None:
        self.session.remove_sub(index, line)
        self._on_editor()

    @Slot(int, int, int)
    def setSubMetric(self, index: int, line: int, combo: int) -> None:
        labels = self.subLabels
        if 0 <= combo < len(labels):
            self.session.set_sub_metric_label(index, line, labels[combo])
            self._on_editor()

    @Slot(bool)
    def setLight(self, on: bool) -> None:
        self.session.set_light(bool(on))
        self._on_editor()

    @Slot()
    def reset(self) -> None:
        self.session.reset()
        self._on_editor()

    @Slot()
    def tick(self) -> None:
        self.viewTick.emit()

    @Slot()
    def closePreview(self) -> None:
        self._save.stop()
        if self.session is not None:
            hud_preview.close_session()
            self.session = None
        self.closed.emit()


class HostBridge(QObject):
    headlineChanged = Signal()
    detailChanged = Signal()
    pcLineChanged = Signal()
    wechatMicChanged = Signal()
    gainLabelChanged = Signal()
    gainPercentChanged = Signal()
    micLevelChanged = Signal()
    spkLevelChanged = Signal()
    logLine = Signal(str)
    deviceIndexChanged = Signal()
    injectIndexChanged = Signal()
    spkIndexChanged = Signal()
    diskIndexChanged = Signal()
    monitorIndexChanged = Signal()
    qualityIndexChanged = Signal()
    micEnabledChanged = Signal()
    spkEnabledChanged = Signal()
    setDefaultSpkChanged = Signal()
    volumeSyncChanged = Signal()
    lightThemeChanged = Signal()
    upsideDownChanged = Signal()
    pcStatsEnabledChanged = Signal()
    toastMirrorChanged = Signal()
    autostartChanged = Signal()
    minimizeToTrayChanged = Signal()
    connectedChanged = Signal()
    diagChanged = Signal()
    screenChanged = Signal()
    muteChanged = Signal()
    statsChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.host = None
        self.engine = None
        self._hud_win = None
        self._hud_editor = None
        self._headline = "未连接"
        self._detail = "插入数据线后点刷新，再点连接。"
        self._pc_line = "电脑状态：连接音箱后显示在音箱屏幕上。"
        self._wechat_mic = "尚未识别"
        self._gain_label = "100%  ·  0.0 dB"
        self._gain_percent = 100.0
        self._mic_level = 0.0
        self._spk_level = 0.0
        self._models = {
            "device": QStringListModel(self),
            "inject": QStringListModel(self),
            "spk": QStringListModel(self),
            "disk": QStringListModel(self),
            "monitor": QStringListModel(self),
            "quality": QStringListModel(self),
        }
        self._device_index = 0
        self._inject_index = 0
        self._spk_index = 0
        self._disk_index = 0
        self._monitor_index = 0
        self._quality_index = 0
        self._vb = False
        self._hifi = False
        self._diag_scanned = False
        self._screen_state = None
        self._stat_cpu = ""
        self._stat_cpu_temp = ""
        self._stat_gpu = ""
        self._stat_gpu_temp = ""
        self._stat_ram = ""
        self._stat_ram_sub = ""
        self._stat_disk = ""
        self._stat_disk_sub = ""
        self._stat_net_up = ""
        self._stat_net_down = ""

    def bind(self, host) -> None:
        self.host = host
        host.headline = _TextSink(self.set_headline)
        host.detail = _TextSink(self.set_detail)
        host.pc_line = _TextSink(self.set_pc_line)
        host.log = _LogBox(self.logLine.emit)
        host.mic_var._on_change = lambda: self.set_wechat_mic(str(host.mic_var.get()))
        host.gain_label_var._on_change = lambda: self.set_gain_label(str(host.gain_label_var.get()))
        host.gain_var._on_change = self.sync_toggles
        host.mic_enabled._on_change = self.sync_toggles
        host.spk_enabled._on_change = self.sync_toggles
        host.set_default_spk._on_change = self.sync_toggles
        host.volume_sync._on_change = self.sync_toggles
        host.light_theme._on_change = self.sync_toggles
        host.upside_down._on_change = self.sync_toggles
        host.pc_stats_enabled._on_change = self.sync_toggles
        host.toast_mirror._on_change = self.sync_toggles
        host.autostart._on_change = self.sync_toggles
        host.minimize_to_tray._on_change = self.sync_toggles
        host.device_var._on_change = lambda: self._sync_combo("device")
        host.inject_var._on_change = lambda: self._sync_combo("inject")
        host.spk_dev_var._on_change = lambda: self._sync_combo("spk")
        host.disk_var._on_change = lambda: self._sync_combo("disk")
        host.monitor_var._on_change = lambda: self._sync_combo("monitor")
        host.quality_var._on_change = lambda: self._sync_combo("quality")
        self.set_wechat_mic(str(host.mic_var.get()))
        self.set_gain_label(str(host.gain_label_var.get()))
        for kind in ("device", "inject", "spk", "disk", "monitor", "quality"):
            self._sync_combo(kind)
        self.sync_toggles()
        self.connectedChanged.emit()
        self.refresh_diag()

    def set_headline(self, text: str) -> None:
        text = str(text)
        if self._headline == text:
            return
        self._headline = text
        self.headlineChanged.emit()
        self.connectedChanged.emit()
        self.diagChanged.emit()

    def set_detail(self, text: str) -> None:
        text = str(text)
        if self._detail == text:
            return
        self._detail = text
        self.detailChanged.emit()

    def set_pc_line(self, text: str) -> None:
        text = str(text)
        if self._pc_line == text:
            return
        self._pc_line = text
        self.pcLineChanged.emit()

    def set_wechat_mic(self, text: str) -> None:
        text = str(text)
        if self._wechat_mic == text:
            return
        self._wechat_mic = text
        self.wechatMicChanged.emit()

    def set_gain_label(self, text: str) -> None:
        text = str(text)
        if self._gain_label == text:
            return
        self._gain_label = text
        self.gainLabelChanged.emit()

    def set_levels(self, mic: float, spk: float) -> None:
        mic = float(max(0.0, min(1.0, mic)))
        spk = float(max(0.0, min(1.0, spk)))
        if abs(mic - self._mic_level) > 0.01:
            self._mic_level = mic
            self.micLevelChanged.emit()
        if abs(spk - self._spk_level) > 0.01:
            self._spk_level = spk
            self.spkLevelChanged.emit()

    def set_labels(self, kind: str, labels: list[str]) -> None:
        labels = [str(x) for x in labels]
        model = self._models[kind]
        if model.stringList() == labels:
            if self.host is not None:
                self._sync_combo(kind)
            return
        model.setStringList(labels)
        if self.host is not None:
            self._sync_combo(kind)
        if kind == "device":
            self.diagChanged.emit()

    def _combo(self, kind: str) -> tuple[list[str], str, Signal]:
        host = self.host
        table = {
            "device": ("device_var", self.deviceIndexChanged),
            "inject": ("inject_var", self.injectIndexChanged),
            "spk": ("spk_dev_var", self.spkIndexChanged),
            "disk": ("disk_var", self.diskIndexChanged),
            "monitor": ("monitor_var", self.monitorIndexChanged),
            "quality": ("quality_var", self.qualityIndexChanged),
        }
        var_name, sig = table[kind]
        labels = list(self._models[kind].stringList())
        return labels, getattr(host, var_name).get() if host else "", sig

    def _sync_combo(self, kind: str) -> None:
        labels, current, sig = self._combo(kind)
        try:
            index = labels.index(current) if current in labels else 0
        except ValueError:
            index = 0
        attr = f"_{kind}_index"
        if getattr(self, attr) != index:
            setattr(self, attr, index)
            sig.emit()
        else:
            sig.emit()

    def _set_combo_index(self, kind: str, index: int, command) -> None:
        labels, _current, sig = self._combo(kind)
        if not labels:
            return
        index = max(0, min(int(index), len(labels) - 1))
        attr = f"_{kind}_index"
        setattr(self, attr, index)
        var_name = {
            "device": "device_var",
            "inject": "inject_var",
            "spk": "spk_dev_var",
            "disk": "disk_var",
            "monitor": "monitor_var",
            "quality": "quality_var",
        }[kind]
        getattr(self.host, var_name).set(labels[index])
        sig.emit()
        if command:
            command()

    def sync_toggles(self) -> None:
        host = self.host
        if host is None:
            return
        self.micEnabledChanged.emit()
        self.spkEnabledChanged.emit()
        self.setDefaultSpkChanged.emit()
        self.volumeSyncChanged.emit()
        self.lightThemeChanged.emit()
        self.upsideDownChanged.emit()
        self.pcStatsEnabledChanged.emit()
        self.toastMirrorChanged.emit()
        self.autostartChanged.emit()
        self.minimizeToTrayChanged.emit()
        self.gainPercentChanged.emit()
        self.connectedChanged.emit()
        self.diagChanged.emit()
        self.screenChanged.emit()

    def _combo_label(self, kind: str, index: int) -> str:
        labels = list(self._models[kind].stringList())
        if 0 <= index < len(labels):
            return labels[index]
        return ""

    def _device_ready(self) -> bool:
        labels = list(self._models["device"].stringList())
        if not labels:
            return False
        text = labels[0]
        return text != "正在扫描…" and not text.startswith("没有") and not text.startswith("未找到")

    def refresh_diag(self) -> None:
        try:
            import vb_cable

            self._vb = bool(vb_cable.present())
        except Exception:
            self._vb = False
        try:
            import hifi_cable

            self._hifi = bool(hifi_cable.present())
        except Exception:
            self._hifi = False
        self._diag_scanned = True
        self.diagChanged.emit()

    def sync_screen(self) -> None:
        host = self.host
        if host is None:
            return
        state = (
            bool(host.connected),
            bool(host.mirror.running()),
            bool(host.toast.showing()),
            getattr(host, "_usb_link", None),
            bool(host.hw.muted),
            bool(host.loopback.muted),
            host.client.video_sock is not None,
            host.client.toast_sock is not None,
        )
        if state == self._screen_state:
            return
        self._screen_state = state
        self.screenChanged.emit()
        self.muteChanged.emit()
        self.diagChanged.emit()

    def set_stats(self, snap: dict) -> None:
        def num(key):
            value = snap.get(key)
            return value if isinstance(value, (int, float)) else None

        cpu = num("cpu")
        self._stat_cpu = f"{int(round(cpu))}%" if cpu is not None else ""
        cpu_t = num("cpuT")
        self._stat_cpu_temp = f"{int(round(cpu_t))}°C" if cpu_t is not None else ""
        gpu = num("gpu")
        self._stat_gpu = f"{int(round(gpu))}%" if gpu is not None else ""
        gpu_t = num("gpuT")
        self._stat_gpu_temp = f"{int(round(gpu_t))}°C" if gpu_t is not None else ""
        ram = num("ram")
        self._stat_ram = f"{int(round(ram))}%" if ram is not None else ""
        ram_u, ram_t = num("ramU"), num("ramT")
        self._stat_ram_sub = f"{ram_u:.1f} / {ram_t:.1f} GB" if ram_u is not None and ram_t is not None else ""
        disk = num("disk")
        self._stat_disk = f"{int(round(disk))}%" if disk is not None else ""
        disk_u, disk_t = num("diskU"), num("diskT")
        letter = str(snap.get("diskN") or "").strip()
        if disk_u is not None and disk_t is not None:
            prefix = (letter + "  ") if letter else ""
            self._stat_disk_sub = f"{prefix}{disk_u:.0f} / {disk_t:.0f} GB"
        else:
            self._stat_disk_sub = letter
        net_u, net_d = num("netU"), num("netD")
        self._stat_net_up = _fmt_rate(net_u) if net_u is not None else ""
        self._stat_net_down = _fmt_rate(net_d) if net_d is not None else ""
        self.statsChanged.emit()

    def _tone(self, kind: str) -> str:
        host = self.host
        connected = bool(host and host.connected)
        if kind == "adb":
            if host is None:
                return "off"
            if not host.adb:
                return "error"
            if connected or self._device_ready():
                return "ok"
            return "warn"
        if kind == "usb":
            if not connected:
                return "off"
            link = getattr(host, "_usb_link", None)
            if link is False:
                return "error"
            return "ok"
        if kind == "audio":
            if not connected:
                return "off"
            if host.mic_enabled.get() or host.spk_enabled.get():
                return "ok"
            return "warn"
        if kind == "vb":
            if not self._diag_scanned:
                return "off"
            return "ok" if self._vb else "warn"
        if kind == "hifi":
            if not self._diag_scanned:
                return "off"
            return "ok" if self._hifi else "warn"
        if kind == "mirror":
            if not connected:
                return "off"
            return "ok" if host.client.video_sock is not None else "warn"
        if kind == "toast":
            if not connected:
                return "off"
            return "ok" if host.client.toast_sock is not None else "warn"
        return "off"

    def parent_widget(self):
        return None

    def askokcancel(self, text: str) -> bool:
        box = QMessageBox(self.parent_widget())
        box.setWindowTitle("LX04")
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Ok

    def showinfo(self, text: str) -> None:
        QMessageBox.information(self.parent_widget(), "LX04", text)

    def showerror(self, text: str) -> None:
        QMessageBox.critical(self.parent_widget(), "LX04", text)

    def pick_image(self) -> str:
        path, _ok = QFileDialog.getOpenFileName(
            self.parent_widget(),
            "选择监视页背景",
            "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.gif *.webp);;所有文件 (*.*)",
        )
        return path

    def pick_bg_slot(self) -> int | None:
        box = QMessageBox(self.parent_widget())
        box.setWindowTitle("背景库已满")
        box.setText("音箱已存 3 张背景，请选择要替换的一张：")
        b1 = box.addButton("替换 1", QMessageBox.ButtonRole.AcceptRole)
        b2 = box.addButton("替换 2", QMessageBox.ButtonRole.AcceptRole)
        b3 = box.addButton("替换 3", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        return {b1: 0, b2: 1, b3: 2}.get(clicked)

    @Property(str, notify=headlineChanged)
    def headline(self) -> str:
        return self._headline

    @Property(str, notify=detailChanged)
    def detail(self) -> str:
        return self._detail

    @Property(str, notify=pcLineChanged)
    def pcLine(self) -> str:
        return self._pc_line

    @Property(str, notify=wechatMicChanged)
    def wechatMic(self) -> str:
        return self._wechat_mic

    @Property(str, notify=gainLabelChanged)
    def gainLabel(self) -> str:
        return self._gain_label

    @Property(float, notify=gainPercentChanged)
    def gainPercent(self) -> float:
        return float(self.host.gain_var.get()) if self.host else self._gain_percent

    @Property(float, notify=micLevelChanged)
    def micLevel(self) -> float:
        return self._mic_level

    @Property(float, notify=spkLevelChanged)
    def spkLevel(self) -> float:
        return self._spk_level

    @Property(QObject, constant=True)
    def deviceModel(self):
        return self._models["device"]

    @Property(int, notify=deviceIndexChanged)
    def deviceIndex(self) -> int:
        return self._device_index

    @Property(QObject, constant=True)
    def injectModel(self):
        return self._models["inject"]

    @Property(int, notify=injectIndexChanged)
    def injectIndex(self) -> int:
        return self._inject_index

    @Property(QObject, constant=True)
    def spkModel(self):
        return self._models["spk"]

    @Property(int, notify=spkIndexChanged)
    def spkIndex(self) -> int:
        return self._spk_index

    @Property(QObject, constant=True)
    def diskModel(self):
        return self._models["disk"]

    @Property(int, notify=diskIndexChanged)
    def diskIndex(self) -> int:
        return self._disk_index

    @Property(QObject, constant=True)
    def monitorModel(self):
        return self._models["monitor"]

    @Property(int, notify=monitorIndexChanged)
    def monitorIndex(self) -> int:
        return self._monitor_index

    @Property(QObject, constant=True)
    def qualityModel(self):
        return self._models["quality"]

    @Property(int, notify=qualityIndexChanged)
    def qualityIndex(self) -> int:
        return self._quality_index

    @Property(bool, notify=micEnabledChanged)
    def micEnabled(self) -> bool:
        return bool(self.host.mic_enabled.get()) if self.host else True

    @Property(bool, notify=spkEnabledChanged)
    def spkEnabled(self) -> bool:
        return bool(self.host.spk_enabled.get()) if self.host else False

    @Property(bool, notify=setDefaultSpkChanged)
    def setDefaultSpk(self) -> bool:
        return bool(self.host.set_default_spk.get()) if self.host else True

    @Property(bool, notify=volumeSyncChanged)
    def volumeSync(self) -> bool:
        return bool(self.host.volume_sync.get()) if self.host else False

    @Property(bool, notify=lightThemeChanged)
    def lightTheme(self) -> bool:
        return bool(self.host.light_theme.get()) if self.host else False

    @Property(bool, notify=upsideDownChanged)
    def upsideDown(self) -> bool:
        return bool(self.host.upside_down.get()) if self.host else False

    @Property(bool, notify=pcStatsEnabledChanged)
    def pcStatsEnabled(self) -> bool:
        return bool(self.host.pc_stats_enabled.get()) if self.host else True

    @Property(bool, notify=toastMirrorChanged)
    def toastMirror(self) -> bool:
        return bool(self.host.toast_mirror.get()) if self.host else False

    @Property(bool, notify=autostartChanged)
    def autostart(self) -> bool:
        return bool(self.host.autostart.get()) if self.host else False

    @Property(bool, notify=minimizeToTrayChanged)
    def minimizeToTray(self) -> bool:
        return bool(self.host.minimize_to_tray.get()) if self.host else False

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return bool(getattr(self.host, "connected", False))

    @Property(bool, notify=diagChanged)
    def hasDevice(self) -> bool:
        return self._device_ready()

    @Property(str, notify=diagChanged)
    def diagAdb(self) -> str:
        return self._tone("adb")

    @Property(str, notify=diagChanged)
    def diagUsb(self) -> str:
        return self._tone("usb")

    @Property(str, notify=diagChanged)
    def diagAudio(self) -> str:
        return self._tone("audio")

    @Property(str, notify=diagChanged)
    def diagVb(self) -> str:
        return self._tone("vb")

    @Property(str, notify=diagChanged)
    def diagHifi(self) -> str:
        return self._tone("hifi")

    @Property(str, notify=diagChanged)
    def diagMirror(self) -> str:
        return self._tone("mirror")

    @Property(str, notify=diagChanged)
    def diagToast(self) -> str:
        return self._tone("toast")

    @Property(str, notify=diagChanged)
    def diagHint(self) -> str:
        if self._headline == "连接失败":
            return "无法连接到 LX04。"
        if self._tone("usb") == "error":
            return "USB 数据通道已断开。"
        if self._tone("hifi") == "warn":
            return "电脑声音无法发送到 LX04。"
        if self._tone("vb") == "warn":
            return "微信麦克风需要 VB-CABLE。"
        if self._tone("adb") == "error":
            return "没有找到内置 adb。"
        if self._tone("adb") == "warn":
            return "未检测到 LX04。"
        return ""

    @Property(str, notify=injectIndexChanged)
    def injectLabel(self) -> str:
        return self._combo_label("inject", self._inject_index)

    @Property(str, notify=spkIndexChanged)
    def spkLabel(self) -> str:
        return self._combo_label("spk", self._spk_index)

    @Property(bool, notify=muteChanged)
    def micMuted(self) -> bool:
        return bool(self.host.hw.muted) if self.host else False

    @Property(bool, notify=muteChanged)
    def spkMuted(self) -> bool:
        return bool(self.host.loopback.muted) if self.host else False

    @Property(bool, notify=screenChanged)
    def mirrorRunning(self) -> bool:
        return bool(self.host and self.host.mirror.running())

    @Property(bool, notify=screenChanged)
    def toastShowing(self) -> bool:
        return bool(self.host and self.host.toast.showing())

    @Property(str, notify=screenChanged)
    def screenMode(self) -> str:
        host = self.host
        if host is None:
            return "—"
        if host.toast.showing():
            return "系统弹窗"
        if host.mirror.running():
            return "屏幕镜像"
        if host.pc_stats_enabled.get():
            return "状态监视"
        return "—"

    @Property(str, notify=statsChanged)
    def statCpu(self) -> str:
        return self._stat_cpu

    @Property(str, notify=statsChanged)
    def statCpuTemp(self) -> str:
        return self._stat_cpu_temp

    @Property(str, notify=statsChanged)
    def statGpu(self) -> str:
        return self._stat_gpu

    @Property(str, notify=statsChanged)
    def statGpuTemp(self) -> str:
        return self._stat_gpu_temp

    @Property(str, notify=statsChanged)
    def statRam(self) -> str:
        return self._stat_ram

    @Property(str, notify=statsChanged)
    def statRamSub(self) -> str:
        return self._stat_ram_sub

    @Property(str, notify=statsChanged)
    def statDisk(self) -> str:
        return self._stat_disk

    @Property(str, notify=statsChanged)
    def statDiskSub(self) -> str:
        return self._stat_disk_sub

    @Property(str, notify=statsChanged)
    def statNetUp(self) -> str:
        return self._stat_net_up

    @Property(str, notify=statsChanged)
    def statNetDown(self) -> str:
        return self._stat_net_down

    @Property("QVariantMap", notify=statsChanged)
    def hudSamples(self) -> dict:
        return {
            "cpu": self._stat_cpu,
            "cpuT": self._stat_cpu_temp,
            "gpu": self._stat_gpu,
            "gpuT": self._stat_gpu_temp,
            "ram": self._stat_ram,
            "ramGB": self._stat_ram_sub,
            "disk": self._stat_disk,
            "diskGB": self._stat_disk_sub,
            "netD": self._stat_net_down,
            "netU": self._stat_net_up,
        }

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return app_version()

    @Slot(str)
    def copyText(self, text: str) -> None:
        QApplication.clipboard().setText(text)

    @Slot()
    def refreshDevices(self) -> None:
        self.host.refresh_devices()
        self.refresh_diag()

    @Slot()
    def redetect(self) -> None:
        if self.host is not None:
            self.host.refresh_devices()
        self.refresh_diag()

    @Slot()
    def syncScreen(self) -> None:
        self.sync_screen()

    @Slot()
    def refreshStats(self) -> None:
        if self.host is None:
            return
        try:
            import pc_stats

            snap = pc_stats.snapshot(str(self.host.disk_var.get() or "C:"))
        except Exception:
            return
        self.set_stats(snap)

    @Slot()
    def connectDevice(self) -> None:
        self.host.connect()

    @Slot()
    def disconnectDevice(self) -> None:
        self.host.disconnect()

    @Slot()
    def testTone(self) -> None:
        self.host._on_test_tone()

    @Slot()
    def speakerTest(self) -> None:
        self.host._on_speaker_test_tone()

    @Slot()
    def toggleMute(self) -> None:
        self.host.client.send_control("toggle_mute")

    @Slot()
    def toggleMicMute(self) -> None:
        if self.host and self.host.connected:
            self.host.client.send_control("toggle_mute")

    @Slot()
    def toggleSpkMute(self) -> None:
        if self.host and self.host.connected:
            self.host.client.send_control("toggle_spk_mute")

    @Slot(bool)
    def setMirrorEnabled(self, on: bool) -> None:
        self.host._apply_mirror_request(bool(on))
        self.sync_screen()

    @Slot()
    def installVb(self) -> None:
        self.host._install_vb()

    @Slot()
    def installHifi(self) -> None:
        self.host._install_hifi()

    @Slot()
    def openHudPreview(self) -> None:
        self.host._open_hud_preview()

    def show_hud_window(self, on_change) -> None:
        register_hud_types()
        light = bool(self.host.light_theme.get()) if self.host else False
        win = self._hud_win
        if win is not None:
            try:
                if self._hud_editor is not None:
                    self._hud_editor.attach(on_change, light)
                win.show()
                win.raise_()
                win.requestActivate()
                return
            except RuntimeError:
                self._hud_win = None
                self._hud_editor = None
        if self.engine is None:
            return
        self._hud_editor = HudEditor(on_change=on_change, light=light)
        self.engine.rootContext().setContextProperty("hud", self._hud_editor)
        qml = qml_dir() / "HudPreview.qml"
        comp = QQmlComponent(self.engine, QUrl.fromLocalFile(str(qml)))
        if comp.status() != QQmlComponent.Status.Ready:
            print(comp.errorString())
            return
        win = comp.create(self.engine.rootContext())
        if win is None:
            print(comp.errorString())
            return
        from PySide6.QtGui import QIcon
        ico = assets_dir() / "app-icon.ico"
        if ico.is_file():
            win.setIcon(QIcon(str(ico)))
        self._hud_win = win
        self._hud_editor.closed.connect(self._hud_closed)
        win.show()

    def _hud_closed(self, *_args) -> None:
        self._hud_win = None
        self._hud_editor = None

    @Slot()
    def uploadHudBg(self) -> None:
        self.host._upload_hud_bg()

    @Slot()
    def afterburner(self) -> None:
        self.host._on_afterburner()

    @Slot(int)
    def setDeviceIndex(self, index: int) -> None:
        self._set_combo_index("device", index, None)

    @Slot(int)
    def setInjectIndex(self, index: int) -> None:
        self._set_combo_index("inject", index, self.host._on_mic_route_change)

    @Slot(int)
    def setSpkIndex(self, index: int) -> None:
        self._set_combo_index("spk", index, self.host._on_spk_route_change)

    @Slot(int)
    def setDiskIndex(self, index: int) -> None:
        self._set_combo_index("disk", index, self.host._on_disk_change)

    @Slot(int)
    def setMonitorIndex(self, index: int) -> None:
        self._set_combo_index("monitor", index, self.host._on_monitor_change)

    @Slot(int)
    def setQualityIndex(self, index: int) -> None:
        self._set_combo_index("quality", index, self.host._on_quality_change)

    @Slot(bool)
    def setMicEnabled(self, on: bool) -> None:
        self.host.mic_enabled.set(bool(on))
        self.host._on_mic_route_change()

    @Slot(bool)
    def setSpkEnabled(self, on: bool) -> None:
        self.host.spk_enabled.set(bool(on))
        self.host._on_spk_route_change()

    @Slot(bool)
    def setSetDefaultSpk(self, on: bool) -> None:
        self.host.set_default_spk.set(bool(on))
        self.host._on_spk_route_change()

    @Slot(bool)
    def setVolumeSync(self, on: bool) -> None:
        self.host.volume_sync.set(bool(on))
        self.host._on_volume_sync_change()

    @Slot(bool)
    def setLightTheme(self, on: bool) -> None:
        self.host.light_theme.set(bool(on))
        self.host._on_light_theme_change()

    @Slot(bool)
    def setUpsideDown(self, on: bool) -> None:
        self.host.upside_down.set(bool(on))
        self.host._on_upside_down_change()

    @Slot(bool)
    def setPcStatsEnabled(self, on: bool) -> None:
        self.host.pc_stats_enabled.set(bool(on))
        self.host._on_pc_stats_change()

    @Slot(bool)
    def setToastMirror(self, on: bool) -> None:
        self.host.toast_mirror.set(bool(on))
        self.host._on_toast_mirror_change()

    @Slot(bool)
    def setAutostart(self, on: bool) -> None:
        self.host.autostart.set(bool(on))
        self.host._on_autostart_change()

    @Slot(bool)
    def setMinimizeToTray(self, on: bool) -> None:
        self.host.minimize_to_tray.set(bool(on))
        self.host._on_tray_pref_change()

    @Slot(float)
    def setGain(self, value: float) -> None:
        self.host.gain_var.set(float(value))
        self.host._on_gain()
        self.gainPercentChanged.emit()

    @Slot(result=bool)
    def onWindowClosing(self) -> bool:
        """True = quit; False = hide to tray."""
        host = self.host
        if host is None:
            return True
        if (not host._closing) and bool(host.minimize_to_tray.get()):
            host._hide_to_tray()
            return False
        host._on_close(force=True)
        return True


def qml_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "qml"
    return Path(__file__).resolve().parent / "qml"


def assets_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parent / "assets"


def app_version() -> str:
    import sys

    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "VERSION.txt")
    candidates.append(Path(__file__).resolve().parents[1] / "VERSION.txt")
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return "0"


def bind_qml_assets(engine) -> None:
    assets = assets_dir()
    ctx = engine.rootContext()
    ctx.setContextProperty("faFontUrl", QUrl.fromLocalFile(str(assets / "fa-solid-900.ttf")))
    ctx.setContextProperty("appIconUrl", QUrl.fromLocalFile(str(assets / "app-icon.png")))


def apply_fluent_style() -> None:
    import os

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "FluentWinUI3")
    QQuickStyle.setStyle("FluentWinUI3")
    app = QApplication.instance()
    if app is not None:
        app.setFont(QFont("Microsoft YaHei"))


def askokcancel(host, text: str) -> bool:
    return host.bridge.askokcancel(text)


def showinfo(host, text: str) -> None:
    host.bridge.showinfo(text)


def showerror(host, text: str) -> None:
    host.bridge.showerror(text)
