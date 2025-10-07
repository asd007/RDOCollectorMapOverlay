import QtQuick 2.15
import QtQuick.Window 2.15
import RDOOverlay 1.0

Window {
    id: overlayWindow
    width: 1920
    height: 1080
    visible: true
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput | Qt.Tool

    // Test CollectibleCanvas WITH backend.visibleCollectibles
    CollectibleCanvas {
        id: canvas
        anchors.fill: parent
        collectibles: backend.visibleCollectibles
        opacityValue: 0.7
    }

    // Debug rectangle to verify window is showing
    Rectangle {
        x: 100
        y: 100
        width: 200
        height: 100
        color: "red"
        opacity: 0.5

        Text {
            anchors.centerIn: parent
            text: "CANVAS TEST"
            color: "white"
            font.pixelSize: 20
        }
    }
}
