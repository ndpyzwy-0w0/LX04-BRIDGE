import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    visible: true
    title: "LX04 上位机"
    width: 920
    height: 640
    minimumWidth: 560
    minimumHeight: 420
    font.family: "Microsoft YaHei"
    color: "#F3F3F3"
    property bool navOpen: true
    readonly property var navPages: [
        { title: "总览", sub: "连接状态与诊断", glyph: "\uf015" },
        { title: "音频", sub: "麦克风与扬声器", glyph: "\uf001" },
        { title: "屏幕", sub: "音箱显示与镜像", glyph: "\uf108" },
        { title: "设置", sub: "启动与托盘", glyph: "\uf013" },
        { title: "日志", sub: "调试信息", glyph: "\uf15c" },
        { title: "关于", sub: "LX04 PC Bridge", glyph: "\uf05a" }
    ]

    onClosing: (event) => { event.accepted = host.onWindowClosing() }

    FontLoader { id: faSolid; source: faFontUrl }

    component FaText: Text {
        property string glyph: ""
        font.family: faSolid.name
        font.pixelSize: 15
        text: glyph
        color: "#1A1A1A"
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
        popup.onAboutToShow: {
            const p = mapToItem(Overlay.overlay, 0, height)
            popup.x = p.x
            popup.y = p.y
        }
    }

    component PageHead: ColumnLayout {
        required property string title
        required property string subtitle
        spacing: 2
        Label {
            text: title
            font.pixelSize: 26
            font.bold: true
        }
        Label {
            text: subtitle
            color: "#6B6B6B"
            font.pixelSize: 13
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
            color: "#F3F3F3"
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
                    implicitHeight: 36
                    FaText {
                        anchors.centerIn: parent
                        glyph: win.navOpen ? "\uf053" : "\uf0c9"
                        font.pixelSize: 16
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.navOpen = !win.navOpen
                    }
                }

                Repeater {
                    model: win.navPages
                    Rectangle {
                        required property int index
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 40
                        radius: 6
                        color: pages.currentIndex === index ? "#E6E6E6" : (hover.containsMouse ? "#EEEEEE" : "transparent")
                        RowLayout {
                            anchors.fill: parent
                            spacing: 8
                            Rectangle {
                                width: 3
                                Layout.fillHeight: true
                                Layout.topMargin: 8
                                Layout.bottomMargin: 8
                                radius: 1
                                color: pages.currentIndex === index ? "#0078D4" : "transparent"
                            }
                            FaText {
                                glyph: modelData.glyph
                                Layout.preferredWidth: 22
                            }
                            Label {
                                text: modelData.title
                                visible: win.navOpen
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                        MouseArea {
                            id: hover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: pages.currentIndex = index
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#E0E0E0"
                    visible: win.navOpen
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    spacing: 8
                    FaText {
                        glyph: host.connected ? "\uf058" : "\uf111"
                        color: host.connected ? "#107C10" : "#8A8A8A"
                        Layout.preferredWidth: 22
                    }
                    ColumnLayout {
                        spacing: 0
                        visible: win.navOpen
                        Label { text: host.connected ? "已连接" : "未连接" }
                        Label {
                            text: host.connected ? host.headline : "请连接 LX04"
                            color: "#8A8A8A"
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
                radius: 10
                color: "#FFFFFF"
                border.color: "#E6E6E6"
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

                        ScrollView {
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            clip: true
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 16

                                Rectangle {
                                    Layout.fillWidth: true
                                    radius: 8
                                    color: "#FFF4D6"
                                    implicitHeight: bannerCol.implicitHeight + 20
                                    ColumnLayout {
                                        id: bannerCol
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.margins: 12
                                        spacing: 4
                                        RowLayout {
                                            FaText { glyph: "\uf05a"; color: "#8A5A00" }
                                            Label {
                                                text: host.headline
                                                font.bold: true
                                                wrapMode: Text.Wrap
                                                Layout.fillWidth: true
                                            }
                                        }
                                        Label {
                                            text: host.detail
                                            wrapMode: Text.Wrap
                                            color: "#5C4A1F"
                                            Layout.fillWidth: true
                                            Layout.leftMargin: 26
                                        }
                                    }
                                }

                                Label { text: "设备"; font.bold: true; font.pixelSize: 15 }
                                RowLayout {
                                    HostCombo {
                                        objectName: "usbBox"
                                        hostModel: host.deviceModel
                                        hostIndex: host.deviceIndex
                                        emptyText: "正在扫描…"
                                        onActivated: (i) => host.setDeviceIndex(i)
                                    }
                                    Button { text: "刷新设备"; onClicked: host.refreshDevices() }
                                    Button { text: "连接"; onClicked: host.connectDevice() }
                                    Button { text: "断开"; onClicked: host.disconnectDevice() }
                                }

                                Label { text: "连接诊断"; font.bold: true; font.pixelSize: 15 }
                                Label { text: "麦克风"; opacity: 0.7 }
                                ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: host.micLevel }
                                Label { text: "扬声器"; opacity: 0.7 }
                                ProgressBar { Layout.fillWidth: true; from: 0; to: 1; value: host.spkLevel }
                            }
                        }

                        ScrollView {
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            clip: true
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                RowLayout {
                                    Switch {
                                        text: "麦克风 → 电脑"
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
                                RowLayout {
                                    Switch {
                                        text: "电脑 → 音箱"
                                        checked: host.spkEnabled
                                        onClicked: host.setSpkEnabled(checked)
                                    }
                                    HostCombo {
                                        hostModel: host.spkModel
                                        hostIndex: host.spkIndex
                                        emptyText: "暂无设备"
                                        onActivated: (i) => host.setSpkIndex(i)
                                    }
                                    Switch {
                                        text: "设为默认播放"
                                        checked: host.setDefaultSpk
                                        onClicked: host.setSetDefaultSpk(checked)
                                    }
                                }
                                Switch {
                                    text: "同步系统音量"
                                    checked: host.volumeSync
                                    onClicked: host.setVolumeSync(checked)
                                }
                                Label {
                                    text: "开了后电脑和音箱音量一起变；关掉则各自调节、互不影响。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                RowLayout {
                                    Label { text: "微信请选麦克风" }
                                    Label { text: host.wechatMic }
                                }
                                RowLayout {
                                    Label { text: "麦克风增益" }
                                    Slider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: 300
                                        value: host.gainPercent
                                        onMoved: host.setGain(value)
                                    }
                                    Label { text: host.gainLabel }
                                }
                                RowLayout {
                                    Button { text: "试音"; onClicked: host.testTone() }
                                    Button { text: "音箱试音"; onClicked: host.speakerTest() }
                                    Button { text: "静音切换"; onClicked: host.toggleMute() }
                                    Item { Layout.fillWidth: true }
                                    Button { text: "安装 Hi-Fi Cable"; onClicked: host.installHifi() }
                                    Button { text: "安装 VB-CABLE"; onClicked: host.installVb() }
                                }
                                Label {
                                    text: "CABLE Input 已从系统播放列表隐藏，上位机仍会把麦克风灌进去。微信选 CABLE Output。扬声器选 Hi-Fi Cable Input。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        ScrollView {
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            clip: true
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                RowLayout {
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
                                    Label { text: "倒转音箱屏幕"; opacity: 0.7 }
                                }
                                RowLayout {
                                    Switch {
                                        text: "音箱显示电脑状态"
                                        checked: host.pcStatsEnabled
                                        onClicked: host.setPcStatsEnabled(checked)
                                    }
                                    Label { text: "磁盘" }
                                    HostCombo {
                                        hostModel: host.diskModel
                                        hostIndex: host.diskIndex
                                        onActivated: (i) => host.setDiskIndex(i)
                                    }
                                }
                                RowLayout {
                                    Button { text: "预览屏幕"; onClicked: host.openHudPreview() }
                                    Button { text: "上传背景"; onClicked: host.uploadHudBg() }
                                    Button { text: "CPU 温度 / Afterburner"; onClicked: host.afterburner() }
                                }
                                Label {
                                    text: host.pcLine
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                RowLayout {
                                    Label { text: "同步屏幕" }
                                    HostCombo {
                                        hostModel: host.monitorModel
                                        hostIndex: host.monitorIndex
                                        onActivated: (i) => host.setMonitorIndex(i)
                                    }
                                    Label { text: "码率" }
                                    HostCombo {
                                        hostModel: host.qualityModel
                                        hostIndex: host.qualityIndex
                                        Layout.fillWidth: false
                                        Layout.preferredWidth: 120
                                        onActivated: (i) => host.setQualityIndex(i)
                                    }
                                }
                                Label {
                                    text: "码率越高越清晰，USB 忙时可能更卡。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                Switch {
                                    text: "同步系统弹窗"
                                    checked: host.toastMirror
                                    onClicked: host.setToastMirror(checked)
                                }
                                Label {
                                    text: "开了后系统通知的标题、正文、按钮会显示到音箱，点按钮即点系统通知。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        ScrollView {
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            clip: true
                            ColumnLayout {
                                width: Math.max(240, content.width - 72)
                                spacing: 12

                                Switch {
                                    text: "开机自启动"
                                    checked: host.autostart
                                    onClicked: host.setAutostart(checked)
                                }
                                Label {
                                    text: "登录 Windows 后自动打开上位机。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                                Switch {
                                    text: "关闭后最小化到托盘"
                                    checked: host.minimizeToTray
                                    onClicked: host.setMinimizeToTray(checked)
                                }
                                Label {
                                    text: "开了后点窗口关闭会藏到托盘继续跑。左键图标恢复窗口，右键可选退出。"
                                    opacity: 0.7
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        ColumnLayout {
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            spacing: 10

                            RowLayout {
                                Item { Layout.fillWidth: true }
                                Button {
                                    text: "复制"
                                    onClicked: host.copyText(logArea.text)
                                }
                                Button {
                                    text: "清空"
                                    onClicked: logArea.clear()
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 8
                                border.color: "#E0E0E0"
                                color: "#FFFFFF"
                                TextArea {
                                    id: logArea
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    readOnly: true
                                    wrapMode: TextEdit.Wrap
                                    font.family: "Microsoft YaHei"
                                    background: null
                                }
                            }
                        }

                        ScrollView {
                            objectName: "aboutPage"
                            visible: StackLayout.isCurrentItem
                            enabled: StackLayout.isCurrentItem
                            clip: true
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
                                }
                                Label {
                                    text: "版本 v" + host.appVersion
                                    color: "#6B6B6B"
                                }
                                Label {
                                    text: "用 USB 把小爱触屏音箱 LX04 接到电脑：麦克风、扬声器和屏幕都可以走这条线。"
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
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
                    text: (host.micEnabled || host.spkEnabled ? "●" : "○") + "  音频: " + (host.micEnabled || host.spkEnabled ? "开" : "—")
                    color: "#5C5C5C"
                    font.pixelSize: 12
                }
                Label {
                    text: (host.pcStatsEnabled ? "●" : "○") + "  屏幕: " + (host.pcStatsEnabled ? "状态监视" : "关")
                    color: "#5C5C5C"
                    font.pixelSize: 12
                }
                Label {
                    text: (host.toastMirror ? "●" : "○") + "  弹窗同步: " + (host.toastMirror ? "开" : "关")
                    color: "#5C5C5C"
                    font.pixelSize: 12
                }
                Item { Layout.fillWidth: true }
            }
        }
    }

    Connections {
        target: host
        function onLogLine(line) { logArea.append(line) }
    }
}
