import QtQuick 2.15
import theme 1.0

/*
 * FPS Counter Display
 *
 * Shows current frames per second.
 * Uses centralized Theme for all styling.
 */

Rectangle {
    id: root

    // Required property
    required property real fps

    // Optional drift statistics
    property real avgDrift: 0.0

    // Size from theme (expanded to fit drift stats)
    width: Theme.fpsCounterWidth + 50
    height: Theme.fpsCounterHeight

    // Styling from theme
    color: Theme.widgetBackground
    border.color: Theme.borderSubtle
    border.width: Theme.borderThin
    radius: Theme.radiusSmall

    // FPS and drift text
    Text {
        anchors.centerIn: parent
        text: "FPS: " + Math.round(root.fps) +
              (root.avgDrift > 0 ? " | Drift: " + root.avgDrift.toFixed(1) : "")
        color: Theme.textTertiary
        font.pixelSize: Theme.fontBody
        font.family: Theme.fontFamily
    }

    // Smooth updates from theme
    Behavior on opacity {
        NumberAnimation {
            duration: Theme.animationFast
            easing.type: Theme.easingStandard
        }
    }
}
