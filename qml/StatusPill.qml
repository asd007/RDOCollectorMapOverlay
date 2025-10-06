import QtQuick 2.15
import theme 1.0

/*
 * Status Indicator Pill
 *
 * Shows status icon + text (e.g., "* Tracking")
 *
 * Uses centralized Theme for all styling.
 */

Rectangle {
    id: root

    // Required properties (set by parent)
    required property string statusText
    required property string statusColor

    // Size from theme
    width: Theme.statusPillWidth
    height: Theme.statusPillHeight

    // Styling from theme
    color: Theme.widgetBackground
    border.color: Theme.borderWidget
    border.width: Theme.borderThin
    radius: Theme.radiusSmall

    // Content
    Row {
        anchors.centerIn: parent
        spacing: Theme.spacingTiny

        // Status dot/icon
        Text {
            id: statusIcon
            text: "*"
            color: root.statusColor
            font.pixelSize: Theme.fontBody
            font.weight: Theme.fontWeightBold
            font.family: Theme.fontFamily
        }

        // Status text
        Text {
            text: root.statusText
            color: Theme.textPrimary
            font.pixelSize: Theme.fontBody
            font.weight: Theme.fontWeightBold
            font.family: Theme.fontFamily
        }
    }

    // Smooth fade animation from theme
    Behavior on opacity {
        NumberAnimation {
            duration: Theme.animationFast
            easing.type: Theme.easingStandard
        }
    }
}
