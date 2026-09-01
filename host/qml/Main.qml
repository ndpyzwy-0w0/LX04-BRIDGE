import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Lx04 1.0

ApplicationWindow {
    id: win
    visible: true
    title: "LX04 PC Bridge"
    width: 800
    height: 600
    minimumWidth: 560
    minimumHeight: 420
    font.family: "Microsoft YaHei"
    color: chrome
    property bool navOpen: true
    property int uptimeSec: 0
    property var logLines: []
    property int logFilterIndex: 0
    property int scrollTick: 0
    function noteScroll() { scrollTick++ }
    readonly property bool dark: palette.window.hslLightness < 0.5
    readonly property color chrome: dark ? "#202020" : "#F3F3F3"
    readonly property color surface: dark ? "#2C2C2C" : "#FFFFFF"
    readonly property color stroke: dark ? "#3F3F3F" : "#E6E6E6"
    readonly property color muted: dark ? "#9A9A9A" : "#6B6B6B"
    readonly property color ink: dark ? "#F0F0F0" : "#1A1A1A"
    readonly property color accent: "#0078D4"
    readonly property color ok: "#107C10"
    readonly property color warn: "#9D5D00"
    readonly property color err: "#C42B1C"
    readonly property color sel: dark ? "#3B3B3B" : "#E6E6E6"
    readonly property color hover: dark ? "#333333" : "#EEEEEE"
    readonly property var navPages: [
        { title: "总览", sub: "连接状态与诊断", glyph: "\uf015" },
        { title: "音频", sub: "麦克风与扬声器", glyph: "\uf001" },
        { title: "屏幕", sub: "800 × 480", glyph: "\uf108" },
        { title: "设置", sub: "监控与系统", glyph: "\uf013" },
        { title: "日志", sub: "调试信息", glyph: "\uf15c" },
        { title: "关于", sub: "LX04 PC Bridge", glyph: "\uf05a" }
    ]

    function installNote(tone) {
        if (tone === "ok") return "已安装"
        if (tone === "off") return "未检测"
        return "未安装"
    }
    function toneColor(tone) {
        if (tone === "ok") return win.ok
        if (tone === "warn") return win.warn
        if (tone === "error") return win.err
        return win.muted
    }
    function toneGlyph(tone) {
        if (tone === "ok") return "\uf00c"
        if (tone === "warn") return "\uf071"
        if (tone === "error") return "\uf00d"
        return "\uf111"
    }
    function fmtUptime(sec) {
        const h = Math.floor(sec / 3600)
        const m = Math.floor((sec % 3600) / 60)
        const s = sec % 60
        const z = (n) => (n < 10 ? "0" : "") + n
        return z(h) + ":" + z(m) + ":" + z(s)
    }
    function applyLog() {
        const keys = ["", "INFO", "WARN", "ERROR"]
        const key = keys[win.logFilterIndex] || ""
        const out = []
        for (let i = 0; i < win.logLines.length; i++) {
            const line = win.logLines[i]
            if (!key || line.indexOf("  " + key + "  ") >= 0)
                out.push(line)
        }
        logArea.text = out.join("\n")
    }

    onClosing: (event) => { event.accepted = host.onWindowClosing() }

    FontLoader { id: faSolid; source: faFontUrl }

    Timer {
        interval: 1000
        running: host.connected
        repeat: true
        onTriggered: win.uptimeSec += 1
    }
    Timer {
        interval: 2000
        running: pages.currentIndex === 2
        repeat: true
        triggeredOnStart: true
        onTriggered: { host.refreshStats(); previewBox.tick() }
    }

    component FaText: Text {
        property string glyph: ""
        font.family: faSolid.name
        font.pixelSize: 15
        text: glyph
        color: win.ink
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    component HostCombo: ComboBox {
        required property var hostModel
        required property int hostIndex
        property string emptyText: ""
        Layout.fillWidth: true
        font.family: "Microsoft YaHei"
        model: hostModel
        textRole: "display"
        currentIndex: hostIndex
        displayText: count ? currentText : emptyText
        enabled: count > 0
        popup.parent: Overlay.overlay
        popup.closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        function pinPopup() {
            const overlay = Overlay.overlay
            if (overlay === null)
                return
            const p = mapToItem(overlay, 0, height)
            popup.x = p.x
            popup.y = p.y
            if (popup.visible && (p.y < 0 || p.y > overlay.height))
                popup.close()
        }
        popup.onAboutToShow: pinPopup()
        popup.onOpened: pinPopup()
        Connections {
            target: win
            function onScrollTickChanged() { pinPopup() }
        }
    }

    component PageScroll: ScrollView {
        clip: true
        visible: StackLayout.isCurrentItem
        enabled: StackLayout.isCurrentItem
        property real _bar: ScrollBar.vertical.position
        on_BarChanged: win.noteScroll()
        Component.onCompleted: {
            const f = contentItem
            if (f && f.contentYChanged)
                f.contentYChanged.connect(win.noteScroll)
        }
    }

    component LevelMeter: Rectangle {
        property real level: 0
        implicitHeight: 22
        Layout.fillWidth: true
        color: "#1E2A44"
        radius: 3
        clip: true
        Rectangle {
            width: Math.max(4, parent.width * Math.min(1.0, parent.level * 2.2))
            height: parent.height
            color: parent.level < 0.35 ? "#3DDC97" : (parent.level < 0.7 ? "#FFB020" : "#FF5C7A")
        }
    }

    component NavBtn: Rectangle {
        required property int pageIndex
        Layout.fillWidth: true
        implicitHeight: 40
        radius: 4
        readonly property var page: win.navPages[pageIndex]
        color: pages.currentIndex === pageIndex ? win.sel : (navHover.containsMouse ? win.hover : "transparent")
        Rectangle {
            width: 3
            height: parent.height - 16
            x: 0
            y: 8
            radius: 1
            color: pages.currentIndex === pageIndex ? win.accent : "transparent"
        }
        FaText {
            x: 11
            width: 22
            height: parent.height
            glyph: page.glyph
        }
        Label {
            x: 37
            width: Math.max(0, parent.width - 45)
            height: parent.height
            verticalAlignment: Text.AlignVCenter
            text: page.title
            color: win.ink
            visible: win.navOpen
            elide: Text.ElideRight
        }
        MouseArea {
            id: navHover
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: pages.currentIndex = pageIndex
        }
    }

    component PageHead: ColumnLayout {
        required property string title
        required property string subtitle
        spacing: 2
        Label {
            text: title
            color: win.ink
            font.pixelSize: 26
            font.bold: true
        }
        Label {
            text: subtitle
            color: win.muted
            font.pixelSize: 13
        }
    }

    component GroupCard: Rectangle {
        id: card
        default property alias extra: body.data
        property string title: ""
        property string status: ""
        property color statusColor: win.ok
        Layout.fillWidth: true
        radius: 6
        border.color: win.stroke
        color: "transparent"
        implicitHeight: inner.implicitHeight + 24
        ColumnLayout {
            id: inner
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 12
            spacing: 8
            RowLayout {
                visible: card.title.length > 0
                Layout.fillWidth: true
                Label {
                    text: card.title
                    font.bold: true
                    font.pixelSize: 16
                    color: win.ink
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: card.status
                    visible: card.status.length > 0
                    color: card.statusColor
                    font.pixelSize: 13
                }
            }
            ColumnLayout {
                id: body
                Layout.fillWidth: true
                spacing: 8
            }
        }
    }

    component DiagRow: RowLayout {
        property string tone: "off"
        property string label: ""
        property string note: ""
        spacing: 8
        Layout.fillWidth: true
        FaText {
            glyph: win.toneGlyph(tone)
            color: win.toneColor(tone)
            Layout.preferredWidth: 18
        }
        Label {
            text: label
            color: win.ink
            Layout.fillWidth: true
        }
        Label {
            text: note
            color: win.toneColor(tone)
            visible: note.length > 0
            font.pixelSize: 12
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: nav
            objectName: "navPane"
            Layout.fillHeight: true
            Layout.preferredWidth: win.navOpen ? 200 : 52
            color: win.chrome
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 8
                anchors.bottomMargin: 12
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 2

                Item {
                    objectName: "navToggle"
                    Layout.fillWidth: true
                    implicitHeight: 40
                    FaText {
                        x: 11
                        width: 22
                        height: parent.height
                        glyph: "\uf0c9"
                        font.pixelSize: 16
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.navOpen = !win.navOpen
                    }
                }

                NavBtn { pageIndex: 0 }
                NavBtn { pageIndex: 1 }
                NavBtn { pageIndex: 2 }
                NavBtn { pageIndex: 3 }
                NavBtn { pageIndex: 4 }
                NavBtn { pageIndex: 5 }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: win.stroke
                    visible: win.navOpen
                }

                Item {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    implicitHeight: 40
                    FaText {
                        x: 11
                        width: 22
                        height: parent.height
                        glyph: host.connected ? "\uf058" : "\uf111"
                        color: host.connected ? win.ok : win.muted
                    }
                    ColumnLayout {
                        x: 37
                        width: Math.max(0, parent.width - 45)
                        spacing: 0
                        visible: win.navOpen
                        Label { text: host.connected ? "已连接" : "未连接"; color: win.ink }
                        Label {
                            text: host.connected ? "LX04 · USB / ADB" : "请连接 LX04"
                            color: win.muted
                            font.pixelSize: 11
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }

        ColumnLayout {
            id: content
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 12
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: win.surface
                border.color: win.stroke
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 14

                    PageHead {
                        title: win.navPages[pages.currentIndex].title
                        subtitle: win.navPages[pages.currentIndex].sub
                    }

                    StackLayout {
                        id: pages
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        PageScroll {
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 16

                                Rectangle {
                                    objectName: "overviewStatus"
                                    Layout.fillWidth: true
                                    radius: 6
                                    color: host.connected ? (win.dark ? "#1C3B2A" : "#E6F4EA") : (host.headline === "连接失败" ? (win.dark ? "#3B1C1F" : "#FDE7E9") : (win.dark ? "#3A3416" : "#FFF4D6"))
                                    implicitHeight: statusCol.implicitHeight + 20
                                    ColumnLayout {
                                        id: statusCol
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.margins: 12
                                        spacing: 4
                                        Label { text: "连接状态"; font.bold: true; font.pixelSize: 16; color: win.ink }
                                        RowLayout {
                                            FaText {
                                                glyph: host.connected ? "\uf058" : "\uf111"
                                                color: host.connected ? win.ok : (host.headline === "连接失败" ? win.err : win.warn)
                                            }
                                            Label {
                                                text: host.connected ? "已连接" : (host.headline === "连接失败" ? "连接失败" : "未连接")
                                                font.bold: true
                                                font.pixelSize: 18
                                                color: win.ink
                                            }
                                        }
                                        Label {
                                            text: host.connected ? "LX04 · USB / ADB" : (host.headline === "连接失败" ? "无法连接到 LX04。" : "请连接 LX04 设备后开始使用")
                                            wrapMode: Text.Wrap
                                            color: win.ink
                                            Layout.fillWidth: true
                                            Layout.leftMargin: 26
                                        }
                                        Label {
                                            visible: host.connected
                                            text: "连接时间：" + win.fmtUptime(win.uptimeSec)
                                            color: win.muted
                                            Layout.leftMargin: 26
                                        }
                                        Label {
                                            visible: host.connected && host.detail.length > 0
                                            text: host.detail
                                            wrapMode: Text.Wrap
                                            color: win.muted
                                            Layout.fillWidth: true
                                            Layout.leftMargin: 26
                                        }
                                    }
                                }

                                GroupCard {
                                    title: "设备"
                                    Label {
                                        text: host.connected ? (host.hasDevice ? usbBox.displayText : "LX04") : (host.hasDevice ? usbBox.displayText : "未检测到 LX04")
                                        font.bold: true
                                        color: win.ink
                                        Layout.fillWidth: true
                                    }
                                    Label {
                                        text: host.connected ? "ADB 已连接 · USB 数据通道正常" : (host.hasDevice ? "ADB · USB" : "")
                                        visible: host.connected || host.hasDevice
                                        color: win.muted
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                    HostCombo {
                                        id: usbBox
                                        objectName: "usbBox"
                                        visible: !host.connected
                                        hostModel: host.deviceModel
                                        hostIndex: host.deviceIndex
                                        emptyText: "未检测到 LX04"
                                        onActivated: (i) => host.setDeviceIndex(i)
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Button { text: "刷新设备"; onClicked: host.refreshDevices() }
                                        Item { Layout.fillWidth: true }
                                        Button {
                                            text: "重试"
                                            highlighted: true
                                            visible: !host.connected && host.headline === "连接失败"
                                            onClicked: host.connectDevice()
                                        }
                                        Button {
                                            text: "连接"
                                            highlighted: true
                                            visible: !host.connected && host.hasDevice && host.headline !== "连接失败"
                                            onClicked: host.connectDevice()
                                        }
                                        Button {
                                            text: "断开连接"
                                            highlighted: true
                                            visible: host.connected
                                            onClicked: host.disconnectDevice()
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12
                                    GroupCard {
                                        objectName: "diagBox"
                                        title: "连接诊断"
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        Layout.preferredWidth: 1
                                        DiagRow { tone: host.diagAdb; label: "LX04 ADB"; note: host.diagAdb === "warn" ? "未检测到" : (host.diagAdb === "error" ? "未找到 adb" : "") }
                                        DiagRow { tone: host.diagUsb; label: "USB 数据通道"; note: host.diagUsb === "error" ? "已断开" : (host.diagUsb === "off" ? "未检测" : "") }
                                        DiagRow { tone: host.diagAudio; label: "音频通道"; note: host.diagAudio === "warn" ? "已关闭" : (host.diagAudio === "off" ? "未检测" : "") }
                                        DiagRow { tone: host.diagVb; label: "VB-CABLE"; note: host.diagVb === "warn" ? "未安装" : (host.diagVb === "off" ? "未检测" : "") }
                                        DiagRow { tone: host.diagHifi; label: "Hi-Fi Cable"; note: host.diagHifi === "warn" ? "未安装" : (host.diagHifi === "off" ? "未检测" : "") }
                                        DiagRow { tone: host.diagMirror; label: "镜像通道"; note: host.diagMirror === "warn" ? "未打开" : (host.diagMirror === "off" ? "未检测" : "") }
                                        DiagRow { tone: host.diagToast; label: "系统弹窗通道"; note: host.diagToast === "warn" ? "走 17890" : (host.diagToast === "off" ? "未检测" : "") }
                                        Label {
                                            text: host.diagHint
                                            visible: host.diagHint.length > 0
                                            wrapMode: Text.Wrap
                                            color: win.warn
                                            Layout.fillWidth: true
                                        }
                                        Button { text: "重新检测"; onClicked: host.redetect() }
                                    }
                                    GroupCard {
                                        title: "音频"
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        Layout.preferredWidth: 1
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Label { text: "麦克风"; color: win.muted; font.pixelSize: 12; Layout.fillWidth: true }
                                            Button {
                                                text: host.micMuted ? "取消静音" : "静音麦克风"
                                                enabled: host.connected
                                                onClicked: host.toggleMicMute()
                                                ToolTip.visible: hovered && !enabled
                                                ToolTip.text: "请先连接 LX04"
                                            }
                                        }
                                        LevelMeter { objectName: "micMeter"; level: host.micLevel }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            Label { text: "扬声器"; color: win.muted; font.pixelSize: 12; Layout.fillWidth: true }
                                            Button {
                                                text: host.spkMuted ? "取消静音" : "静音扬声器"
                                                enabled: host.connected
                                                onClicked: host.toggleSpkMute()
                                                ToolTip.visible: hovered && !enabled
                                                ToolTip.text: "请先连接 LX04"
                                            }
                                        }
                                        LevelMeter { objectName: "spkMeter"; level: host.spkLevel }
                                    }
                                }

                                GroupCard {
                                    objectName: "installPanel"
                                    title: "安装"
                                    status: host.diagVb === "off" ? "未检测" : (host.installOkCount === 3 ? "已全部安装" : host.installOkCount + "/3 已安装")
                                    statusColor: host.diagVb === "off" ? win.muted : (host.installOkCount === 3 ? win.ok : win.warn)
                                    Label {
                                        text: "这些会打开官方安装程序或下载页，不是本软件自带的驱动。"
                                        wrapMode: Text.Wrap
                                        color: win.muted
                                        Layout.fillWidth: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "VB-CABLE"; font.bold: true; color: win.ink; Layout.fillWidth: true }
                                        Label {
                                            objectName: "installVbStatus"
                                            text: win.installNote(host.diagVb)
                                            color: win.toneColor(host.diagVb)
                                            font.pixelSize: 12
                                        }
                                    }
                                    Label {
                                        text: "给微信 / QQ 当麦克风。装完官方虚拟声卡后需要重启电脑。"
                                        wrapMode: Text.Wrap
                                        color: win.muted
                                        Layout.fillWidth: true
                                    }
                                    Button { text: "安装 VB-CABLE"; onClicked: host.installVb() }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "Hi-Fi Cable"; font.bold: true; color: win.ink; Layout.fillWidth: true }
                                        Label {
                                            objectName: "installHifiStatus"
                                            text: win.installNote(host.diagHifi)
                                            color: win.toneColor(host.diagHifi)
                                            font.pixelSize: 12
                                        }
                                    }
                                    Label {
                                        text: "把电脑正在播放的声音送到音箱喇叭。和 VB-CABLE 不是同一根线，装完也要重启。"
                                        wrapMode: Text.Wrap
                                        color: win.muted
                                        Layout.fillWidth: true
                                    }
                                    Button { text: "安装 Hi-Fi Cable"; onClicked: host.installHifi() }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "MSI Afterburner"; font.bold: true; color: win.ink; Layout.fillWidth: true }
                                        Label {
                                            objectName: "installAfterStatus"
                                            text: win.installNote(host.diagAfter)
                                            color: win.toneColor(host.diagAfter)
                                            font.pixelSize: 12
                                        }
                                    }
                                    Label {
                                        text: "可选。音箱上的 CPU 封装温度要靠它。本程序不能内置，将启动已安装的程序或打开 MSI 官网。"
                                        wrapMode: Text.Wrap
                                        color: win.muted
                                        Layout.fillWidth: true
                                    }
                                    Button { text: "CPU 温度 / Afterburner"; onClicked: host.afterburner() }
                                    Button { text: "重新检测"; onClicked: host.redetect() }
                                }
                            }
                        }

                        PageScroll {
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                GroupCard {
                                    title: "麦克风"
                                    status: host.micEnabled ? (host.micMuted ? "静音" : "正常") : "关闭"
                                    statusColor: host.micEnabled && !host.micMuted ? win.ok : win.muted
                                    LevelMeter { level: host.micLevel }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Switch {
                                            checked: host.micEnabled
                                            onClicked: host.setMicEnabled(checked)
                                        }
                                        HostCombo {
                                            hostModel: host.injectModel
                                            hostIndex: host.injectIndex
                                            emptyText: "暂无设备"
                                            onActivated: (i) => host.setInjectIndex(i)
                                        }
                                    }
                                    Label {
                                        text: "输出到  " + (host.injectLabel || "—")
                                        color: win.muted
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "微信请选麦克风"; color: win.ink }
                                        Label { text: host.wechatMic; color: win.muted }
                                        Item { Layout.fillWidth: true }
                                        Button {
                                            text: host.micMuted ? "取消静音" : "静音麦克风"
                                            enabled: host.connected
                                            onClicked: host.toggleMicMute()
                                            ToolTip.visible: hovered && !enabled
                                            ToolTip.text: "请先连接 LX04"
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "麦克风增益"; color: win.ink }
                                        Slider {
                                            Layout.fillWidth: true
                                            from: 0
                                            to: 300
                                            value: host.gainPercent
                                            onMoved: host.setGain(value)
                                        }
                                        Label { text: host.gainLabel; color: win.muted }
                                    }
                                }

                                GroupCard {
                                    title: "扬声器"
                                    status: host.spkEnabled ? (host.spkMuted ? "静音" : "正常") : "关闭"
                                    statusColor: host.spkEnabled && !host.spkMuted ? win.ok : win.muted
                                    LevelMeter { level: host.spkLevel }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Switch {
                                            checked: host.spkEnabled
                                            onClicked: host.setSpkEnabled(checked)
                                        }
                                        HostCombo {
                                            hostModel: host.spkModel
                                            hostIndex: host.spkIndex
                                            emptyText: "暂无设备"
                                            onActivated: (i) => host.setSpkIndex(i)
                                        }
                                    }
                                    Label {
                                        text: "来源  " + (host.spkLabel || "—")
                                        color: win.muted
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Switch {
                                            text: "设为默认播放"
                                            checked: host.setDefaultSpk
                                            onClicked: host.setSetDefaultSpk(checked)
                                        }
                                        Item { Layout.fillWidth: true }
                                        Button {
                                            text: host.spkMuted ? "取消静音" : "静音扬声器"
                                            enabled: host.connected
                                            onClicked: host.toggleSpkMute()
                                            ToolTip.visible: hovered && !enabled
                                            ToolTip.text: "请先连接 LX04"
                                        }
                                    }
                                }

                                GroupCard {
                                    title: "其他"
                                    Switch {
                                        text: "同步系统音量"
                                        checked: host.volumeSync
                                        onClicked: host.setVolumeSync(checked)
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Button { text: "试音"; onClicked: host.testTone() }
                                        Button { text: "音箱试音"; onClicked: host.speakerTest() }
                                    }
                                }
                            }
                        }

                        PageScroll {
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                HudView {
                                    id: previewBox
                                    objectName: "previewBox"
                                    Layout.fillWidth: true
                                    implicitHeight: Math.max(120, width * 480 / 800)
                                    samples: host.hudSamples
                                    light: host.lightTheme
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { text: "监测磁盘"; color: win.ink }
                                    HostCombo {
                                        hostModel: host.diskModel
                                        hostIndex: host.diskIndex
                                        onActivated: (i) => host.setDiskIndex(i)
                                    }
                                    Switch {
                                        text: "同步系统弹窗 实验性"
                                        checked: host.toastMirror
                                        onClicked: host.setToastMirror(checked)
                                    }
                                }

                                GroupCard {
                                    title: "显示"
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Button {
                                            text: "状态监视"
                                            highlighted: host.pcStatsEnabled && !host.mirrorRunning
                                            onClicked: host.setPcStatsEnabled(true)
                                        }
                                        Button {
                                            text: host.mirrorRunning ? "停止镜像" : "屏幕镜像"
                                            highlighted: host.mirrorRunning
                                            enabled: host.connected
                                            onClicked: host.setMirrorEnabled(!host.mirrorRunning)
                                            ToolTip.visible: hovered && !enabled
                                            ToolTip.text: "请先连接 LX04"
                                        }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Button { text: "编辑样式"; onClicked: host.openHudPreview() }
                                        Button { text: "上传背景"; onClicked: host.uploadHudBg() }
                                    }
                                }

                                GroupCard {
                                    title: "屏幕镜像"
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Label { text: "显示器"; color: win.ink }
                                        HostCombo {
                                            hostModel: host.monitorModel
                                            hostIndex: host.monitorIndex
                                            onActivated: (i) => host.setMonitorIndex(i)
                                        }
                                    }
                                    Label { text: "画质"; color: win.ink }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Repeater {
                                            model: host.qualityModel
                                            RadioButton {
                                                text: model.display
                                                checked: host.qualityIndex === index
                                                onClicked: host.setQualityIndex(index)
                                            }
                                        }
                                    }
                                }

                                GroupCard {
                                    title: "外观"
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Switch {
                                            text: "浅色"
                                            checked: host.lightTheme
                                            onClicked: host.setLightTheme(checked)
                                        }
                                        Switch {
                                            text: "吊装"
                                            checked: host.upsideDown
                                            onClicked: host.setUpsideDown(checked)
                                        }
                                    }
                                    Label {
                                        text: host.pcLine
                                        color: win.muted
                                        wrapMode: Text.Wrap
                                        Layout.fillWidth: true
                                        visible: host.pcLine.length > 0
                                    }
                                }
                            }
                        }

                        PageScroll {
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                GroupCard {
                                    title: "系统"
                                    Switch {
                                        text: "开机自启动"
                                        checked: host.autostart
                                        onClicked: host.setAutostart(checked)
                                    }
                                    Switch {
                                        text: "关闭后最小化到托盘"
                                        checked: host.minimizeToTray
                                        onClicked: host.setMinimizeToTray(checked)
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            spacing: 10
                            onVisibleChanged: if (visible) win.applyLog()

                            RowLayout {
                                ComboBox {
                                    id: logFilter
                                    objectName: "logFilter"
                                    model: ["全部", "INFO", "WARN", "ERROR"]
                                    Layout.preferredWidth: 120
                                    popup.closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                                    onActivated: (i) => { win.logFilterIndex = i; win.applyLog() }
                                }
                                Item { Layout.fillWidth: true }
                                Button {
                                    text: "复制"
                                    onClicked: host.copyText(win.logLines.join("\n"))
                                }
                                Button {
                                    text: "清空"
                                    onClicked: { win.logLines = []; win.applyLog() }
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 6
                                border.color: win.stroke
                                color: win.surface
                                TextArea {
                                    id: logArea
                                    objectName: "logArea"
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    readOnly: true
                                    wrapMode: TextEdit.Wrap
                                    font.family: "Microsoft YaHei"
                                    color: win.ink
                                    background: null
                                }
                            }
                        }

                        PageScroll {
                            objectName: "aboutPage"
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                Image {
                                    source: appIconUrl
                                    Layout.preferredWidth: 96
                                    Layout.preferredHeight: 96
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                }
                                Label {
                                    text: "LX04 PC Bridge"
                                    font.pixelSize: 20
                                    font.bold: true
                                    color: win.ink
                                }
                                Label {
                                    text: "版本 v" + host.appVersion
                                    color: win.muted
                                }
                                Label {
                                    text: "用 USB 把小爱触屏音箱 LX04 接到电脑：麦克风、扬声器和屏幕都可以走这条线。"
                                    wrapMode: Text.Wrap
                                    color: win.ink
                                    Layout.fillWidth: true
                                }
                                Text {
                                    objectName: "aboutLicense"
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    color: win.muted
                                    font.pixelSize: 12
                                    font.family: "Microsoft YaHei"
                                    linkColor: win.accent
                                    textFormat: Text.RichText
                                    text: "Copyright © 2026 LX04 PC Bridge<br/>" +
                                          "作者 <a href=\"https://github.com/ndpyzwy-0w0\">ndpyzwy-0w0</a><br/><br/>" +
                                          "本软件使用：Python、" +
                                          "<a href=\"https://www.qt.io/\">Qt / PySide6</a>（The Qt Company，FluentWinUI3）、" +
                                          "<a href=\"https://fontawesome.com/license/free\">Font Awesome Free</a>（Fonticons, SIL OFL 1.1）、" +
                                          "Android platform-tools adb（Apache 2.0）、psutil、sounddevice、pycaw、tkinter。<br/><br/>" +
                                          "<a href=\"https://www.vb-cable.com/\">VB-CABLE</a> 与 " +
                                          "<a href=\"https://vb-audio.com/Cable/\">Hi-Fi Cable</a> 是 VB-Audio（Vincent Burel）的捐赠软件，本程序只启动官方安装包，不修改驱动。<br/>" +
                                          "<a href=\"https://www.msi.com/Landing/afterburner\">MSI Afterburner</a> 未随本软件分发，仅在需要 CPU 温度时打开官网或已安装的程序。"
                                    onLinkActivated: (link) => Qt.openUrlExternally(link)
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                Label {
                    text: (host.micEnabled || host.spkEnabled ? "●" : "○") + "  音频：" + (host.micEnabled || host.spkEnabled ? "正常" : "—")
                    color: win.muted
                    font.pixelSize: 12
                }
                Label {
                    text: "●  屏幕：" + host.screenMode
                    color: win.muted
                    font.pixelSize: 12
                }
                Label {
                    text: (host.toastMirror ? "●" : "○") + "  弹窗同步：" + (host.toastMirror ? "已开启" : "关")
                    color: win.muted
                    font.pixelSize: 12
                }
                Item { Layout.fillWidth: true }
                Label {
                    text: win.logLines.length ? ("最近日志 " + String(win.logLines[win.logLines.length - 1]).slice(0, 5)) : ""
                    color: win.muted
                    font.pixelSize: 12
                }
            }
        }
    }

    Connections {
        target: host
        function onLogLine(line) {
            win.logLines = win.logLines.concat([line])
            win.applyLog()
        }
        function onConnectedChanged() { win.uptimeSec = 0 }
    }
}
