import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: overlayWindow
    width: 1920
    height: 1080
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.Tool

    // Just a test rectangle - NO custom components, NO backend
    Rectangle {
        x: 100
        y: 100
        width: 200
        height: 100
        color: "red"
        opacity: 0.5

        Text {
            anchors.centerIn: parent
            text: "OVERLAY TEST"
            color: "white"
            font.pixelSize: 24
        }
    }
}
