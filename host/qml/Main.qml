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
    property bool navOpen: true

    onClosing: (event) => { event.accepted = host.onWindowClosing() }

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

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Frame {
            id: nav
            objectName: "navPane"
            Layout.fillHeight: true
            Layout.preferredWidth: win.navOpen ? 176 : 52
            clip: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 2
                ToolButton {
                    objectName: "navToggle"
                    Layout.fillWidth: true
                    text: win.navOpen ? "收回" : "☰"
                    onClicked: win.navOpen = !win.navOpen
                }
                Repeater {
                    model: ["连接", "音频", "屏幕", "设置", "日志"]
                    ItemDelegate {
                        Layout.fillWidth: true
                        text: win.navOpen ? modelData : modelData[0]
                        highlighted: pages.currentIndex === index
                        onClicked: pages.currentIndex = index
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        ColumnLayout {
            id: content
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 16
            spacing: 8

        Label {
            text: "LX04 PC Bridge"
            font.pixelSize: 22
            font.bold: true
        }
        Label {
            text: host.headline
            wrapMode: Text.Wrap
            Layout.fillWidth: true
        }
        Label {
            text: host.detail
            opacity: 0.7
            wrapMode: Text.Wrap
            Layout.fillWidth: true
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
                    width: Math.max(240, content.width - 32)
                    spacing: 12

                    RowLayout {
                        Label { text: "USB 设备" }
                        HostCombo {
                            objectName: "usbBox"
                            hostModel: host.deviceModel
                            hostIndex: host.deviceIndex
                            emptyText: "正在扫描…"
                            onActivated: (i) => host.setDeviceIndex(i)
                        }
                        Button { text: "刷新"; onClicked: host.refreshDevices() }
                        Button { text: "连接"; onClicked: host.connectDevice() }
                        Button { text: "断开"; onClicked: host.disconnectDevice() }
                    }
                    Label {
                        text: "USB 连接小爱触屏音箱 LX04。插上线后点刷新，再点连接。"
                        opacity: 0.7
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }
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
                    width: Math.max(240, content.width - 32)
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
                    width: Math.max(240, content.width - 32)
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
                    width: Math.max(240, content.width - 32)
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

            TextArea {
                id: logArea
                readOnly: true
                wrapMode: TextEdit.Wrap
                font.family: "Microsoft YaHei"
            }
        }
        }
    }

    Connections {
        target: host
        function onLogLine(line) { logArea.append(line) }
    }
}
