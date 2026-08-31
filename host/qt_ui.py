"""PySide6 QML shell: FluentWinUI3 style + HostApp bindings."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QStringListModel, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


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

    def __init__(self) -> None:
        super().__init__()
        self.host = None
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

    def set_headline(self, text: str) -> None:
        text = str(text)
        if self._headline == text:
            return
        self._headline = text
        self.headlineChanged.emit()
        self.connectedChanged.emit()

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

    @Property(str, constant=True)
    def appVersion(self) -> str:
        return app_version()

    @Slot(str)
    def copyText(self, text: str) -> None:
        QApplication.clipboard().setText(text)

    @Slot()
    def refreshDevices(self) -> None:
        self.host.refresh_devices()

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
    def installVb(self) -> None:
        self.host._install_vb()

    @Slot()
    def installHifi(self) -> None:
        self.host._install_hifi()

    @Slot()
    def openHudPreview(self) -> None:
        self.host._open_hud_preview()

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
