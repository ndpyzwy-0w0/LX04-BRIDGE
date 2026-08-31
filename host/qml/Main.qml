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

    onClosing: (event) => { event.accepted = host.onWindowClosing() }

    header: TabBar {
        id: tabs
        TabButton { text: "连接" }
        TabButton { text: "音频" }
        TabButton { text: "屏幕" }
        TabButton { text: "设置" }
        TabButton { text: "日志" }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
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
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabs.currentIndex

            ScrollView {
                clip: true
                ColumnLayout {
                    width: win.width - 48
                    spacing: 12

                    RowLayout {
                        Label { text: "USB 设备" }
                        ComboBox {
                            Layout.fillWidth: true
                            model: host.deviceLabels
                            currentIndex: host.deviceIndex
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
                clip: true
                ColumnLayout {
                    width: win.width - 48
                    spacing: 12

                    RowLayout {
                        Switch {
                            text: "麦克风 → 电脑"
                            checked: host.micEnabled
                            onClicked: host.setMicEnabled(checked)
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            model: host.injectLabels
                            currentIndex: host.injectIndex
                            onActivated: (i) => host.setInjectIndex(i)
                        }
                    }
                    RowLayout {
                        Switch {
                            text: "电脑 → 音箱"
                            checked: host.spkEnabled
                            onClicked: host.setSpkEnabled(checked)
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            model: host.spkLabels
                            currentIndex: host.spkIndex
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
                clip: true
                ColumnLayout {
                    width: win.width - 48
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
                        ComboBox {
                            Layout.fillWidth: true
                            model: host.diskLabels
                            currentIndex: host.diskIndex
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
                        ComboBox {
                            Layout.fillWidth: true
                            model: host.monitorLabels
                            currentIndex: host.monitorIndex
                            onActivated: (i) => host.setMonitorIndex(i)
                        }
                        Label { text: "码率" }
                        ComboBox {
                            model: host.qualityLabels
                            currentIndex: host.qualityIndex
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
                clip: true
                ColumnLayout {
                    width: win.width - 48
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
                font.family: "Consolas"
            }
        }
    }

    Connections {
        target: host
        function onLogLine(line) { logArea.append(line) }
    }
}
