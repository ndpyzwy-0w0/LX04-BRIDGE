import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Lx04 1.0

ApplicationWindow {
    id: win
    objectName: "hudPreviewWin"
    visible: true
    title: "音箱屏幕预览"
    width: 800
    height: 720
    minimumWidth: 560
    minimumHeight: 420
    font.family: "Microsoft YaHei"
    color: chrome
    readonly property bool dark: palette.window.hslLightness < 0.5
    readonly property color chrome: dark ? "#202020" : "#F3F3F3"
    readonly property color stroke: dark ? "#3F3F3F" : "#E6E6E6"
    readonly property color muted: dark ? "#9A9A9A" : "#6B6B6B"
    readonly property color ink: dark ? "#F0F0F0" : "#1A1A1A"
    readonly property int gen: hud.gen

    component HostCombo: ComboBox {
        popup.parent: Overlay.overlay
    }

    component GroupCard: Rectangle {
        id: card
        default property alias extra: body.data
        property string title: ""
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
            Label {
                visible: card.title.length > 0
                text: card.title
                font.bold: true
                font.pixelSize: 16
                color: win.ink
            }
            ColumnLayout {
                id: body
                Layout.fillWidth: true
                spacing: 8
            }
        }
    }

    onClosing: hud.closePreview()

    Timer {
        interval: 1000
        running: win.visible
        repeat: true
        onTriggered: hud.tick()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Label {
            text: "每个格子可加大字和多条小字。音箱上长按栏目也能改，两边会同步。"
            wrapMode: Text.Wrap
            color: win.muted
            Layout.fillWidth: true
        }

        HudView {
            objectName: "hudView"
            hud: hud
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(160, width * 480 / 800)
        }

        RowLayout {
            Layout.fillWidth: true
            Switch {
                text: "浅色"
                checked: { win.gen; return hud.light }
                onClicked: hud.setLight(checked)
            }
            Label {
                text: "浅色和板块样式会同步到已连接的音箱。"
                color: win.muted
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            Button { text: "恢复默认"; onClicked: hud.reset() }
        }

        ScrollView {
            objectName: "hudEditor"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ColumnLayout {
                width: Math.max(240, win.width - 56)
                spacing: 12

                Repeater {
                    model: 4
                    GroupCard {
                        property int cardIndex: index
                        title: hud.slotName(cardIndex)
                        property var subIdx: { win.gen; return hud.subMetricIndexes(cardIndex) }

                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "标题字母"; color: win.muted }
                            TextField {
                                id: titleField
                                Layout.fillWidth: true
                                maximumLength: 8
                                Component.onCompleted: text = hud.cardTitle(cardIndex)
                                onTextEdited: hud.setTitle(cardIndex, text)
                                Connections {
                                    target: hud
                                    function onChanged() { titleField.text = hud.cardTitle(cardIndex) }
                                }
                            }
                            Rectangle {
                                width: 36
                                height: 32
                                radius: 4
                                color: { win.gen; return hud.titleColor(cardIndex) }
                                border.color: win.stroke
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: hud.pickColor(cardIndex, "title")
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "大字内容"; color: win.muted }
                            HostCombo {
                                Layout.fillWidth: true
                                model: hud.metricLabels
                                currentIndex: { win.gen; return hud.metricIndex(cardIndex) }
                                onActivated: (i) => hud.setMetric(cardIndex, i)
                            }
                            Rectangle {
                                width: 36
                                height: 32
                                radius: 4
                                color: { win.gen; return hud.valueColor(cardIndex) }
                                border.color: win.stroke
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: hud.pickColor(cardIndex, "value")
                                }
                            }
                        }

                        Label { text: "小字内容"; color: win.muted }
                        Repeater {
                            model: subIdx.length
                            RowLayout {
                                Layout.fillWidth: true
                                HostCombo {
                                    Layout.fillWidth: true
                                    model: hud.subLabels
                                    currentIndex: subIdx[index]
                                    onActivated: (i) => hud.setSubMetric(cardIndex, index, i)
                                }
                                Button {
                                    text: "×"
                                    onClicked: hud.removeSub(cardIndex, index)
                                }
                            }
                        }
                        Button {
                            text: "+ 小字"
                            visible: subIdx.length < 4
                            onClicked: hud.addSub(cardIndex)
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "大字号"; color: win.muted }
                            SpinBox {
                                from: 12
                                to: 56
                                value: { win.gen; return hud.valueSize(cardIndex) }
                                onValueModified: hud.setValueSize(cardIndex, value)
                            }
                            Label { text: "小字号"; color: win.muted }
                            SpinBox {
                                from: 8
                                to: 28
                                value: { win.gen; return hud.subSize(cardIndex) }
                                onValueModified: hud.setSubSize(cardIndex, value)
                            }
                            Switch {
                                text: "折线"
                                checked: { win.gen; return hud.chartOn(cardIndex) }
                                onClicked: hud.setChart(cardIndex, checked)
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "折线内容"; color: win.muted }
                            HostCombo {
                                Layout.fillWidth: true
                                model: hud.chartLabels
                                currentIndex: { win.gen; return hud.chartIndex(cardIndex) }
                                onActivated: (i) => hud.setChartMetric(cardIndex, i)
                            }
                        }
                    }
                }
            }
        }
    }
}
