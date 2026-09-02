import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Lx04 1.0

ApplicationWindow {
    id: win
    objectName: "hudPreviewWin"
    visible: true
    title: "音箱屏幕预览"
    width: 1100
    height: 720
    minimumWidth: 720
    minimumHeight: 420
    font.family: "Microsoft YaHei"
    color: chrome
    readonly property bool dark: palette.window.hslLightness < 0.5
    readonly property color chrome: dark ? "#202020" : "#F3F3F3"
    readonly property color stroke: dark ? "#3F3F3F" : "#E6E6E6"
    readonly property color muted: dark ? "#9A9A9A" : "#6B6B6B"
    readonly property color ink: dark ? "#F0F0F0" : "#1A1A1A"
    readonly property int gen: hud.gen
    readonly property var api: hud
    property int scrollTick: 0
    function noteScroll() { scrollTick++ }

    component HostCombo: ComboBox {
        Layout.preferredWidth: 128
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

    component Swatch: Rectangle {
        required property int card
        required property string which
        width: 28
        height: 28
        radius: 4
        color: {
            win.gen
            if (which === "title")
                return hud.titleColor(card)
            if (which === "valueTo")
                return hud.valueColorTo(card)
            return hud.valueColor(card)
        }
        border.color: win.stroke
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: hud.pickColor(card, which)
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
        spacing: 10

        Label {
            text: "每个格子可加大字和多条小字。音箱上长按栏目也能改，两边会同步。"
            wrapMode: Text.Wrap
            color: win.muted
            Layout.fillWidth: true
        }

        HudView {
            objectName: "hudView"
            editor: win.api
            samples: host.hudSamples
            light: host.lightTheme
            Layout.fillWidth: true
            Layout.preferredHeight: {
                const aspect = Math.round(width * 480 / 800)
                const cap = Math.max(180, win.height - 280)
                return Math.max(180, Math.min(aspect, cap))
            }
            Layout.maximumHeight: Math.max(180, win.height - 260)
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
            id: hudEditor
            objectName: "hudEditor"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical.policy: ScrollBar.AsNeeded
            property real _bar: ScrollBar.vertical.position
            on_BarChanged: win.noteScroll()
            Component.onCompleted: {
                const f = contentItem
                if (f && f.contentYChanged)
                    f.contentYChanged.connect(win.noteScroll)
            }
            Column {
                width: hudEditor.availableWidth
                spacing: 8

                Repeater {
                    model: 4
                    Rectangle {
                        property int cardIndex: index
                        property var subIdx: { win.gen; return hud.subMetricIndexes(cardIndex) }
                        width: parent.width
                        height: row.implicitHeight + 12
                        radius: 6
                        border.color: win.stroke
                        color: "transparent"
                        RowLayout {
                            id: row
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 6
                            spacing: 6

                            Label {
                                text: hud.slotName(cardIndex)
                                font.bold: true
                                color: win.ink
                                Layout.preferredWidth: 40
                            }
                            TextField {
                                id: titleField
                                Layout.preferredWidth: 84
                                maximumLength: 8
                                Component.onCompleted: text = hud.cardTitle(cardIndex)
                                onTextEdited: hud.setTitle(cardIndex, text)
                                Connections {
                                    target: hud
                                    function onChanged() { titleField.text = hud.cardTitle(cardIndex) }
                                }
                            }
                            Swatch { card: cardIndex; which: "title" }
                            HostCombo {
                                model: hud.metricLabels
                                currentIndex: { win.gen; return hud.metricIndex(cardIndex) }
                                onActivated: (i) => hud.setMetric(cardIndex, i)
                            }
                            Swatch { card: cardIndex; which: "value" }
                            Swatch {
                                card: cardIndex
                                which: "valueTo"
                                visible: { win.gen; return hud.valueShift(cardIndex) }
                            }
                            Switch {
                                text: "变色"
                                checked: { win.gen; return hud.valueShift(cardIndex) }
                                onClicked: hud.setValueShift(cardIndex, checked)
                            }
                            Repeater {
                                model: subIdx.length
                                RowLayout {
                                    spacing: 2
                                    HostCombo {
                                        model: hud.subLabels
                                        currentIndex: subIdx[index]
                                        onActivated: (i) => hud.setSubMetric(cardIndex, index, i)
                                    }
                                    Button {
                                        text: "×"
                                        Layout.preferredWidth: 28
                                        onClicked: hud.removeSub(cardIndex, index)
                                    }
                                }
                            }
                            Button {
                                text: "+"
                                visible: subIdx.length < 4
                                Layout.preferredWidth: 28
                                onClicked: hud.addSub(cardIndex)
                            }
                            Item { Layout.fillWidth: true }
                            SpinBox {
                                from: 12
                                to: 56
                                editable: true
                                value: { win.gen; return hud.valueSize(cardIndex) }
                                onValueModified: hud.setValueSize(cardIndex, value)
                            }
                            SpinBox {
                                from: 8
                                to: 28
                                editable: true
                                value: { win.gen; return hud.subSize(cardIndex) }
                                onValueModified: hud.setSubSize(cardIndex, value)
                            }
                            Switch {
                                text: "折线"
                                checked: { win.gen; return hud.chartOn(cardIndex) }
                                onClicked: hud.setChart(cardIndex, checked)
                            }
                            HostCombo {
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
