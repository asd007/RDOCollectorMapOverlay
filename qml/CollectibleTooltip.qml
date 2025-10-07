import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import theme 1.0

/*
 * Collectible Tooltip - Optimized for Minimal Mouse Travel
 *
 * Shows collectible details on hover:
 * - Name (bold, yellow)
 * - Type
 * - Help text (if available)
 * - Collected status
 * - Video button(s) positioned near mouse entry point
 *
 * Smart positioning:
 * - Corner-anchors near collectible to minimize overlap
 * - Video buttons positioned adjacent to hover entry point for minimal travel
 */

Popup {
    id: tooltip

    // Input properties
    property var collectible: null
    property real collectibleX: 0
    property real collectibleY: 0
    property string anchorCorner: 'bottom-left' // Track which corner we're anchored to

    // Appearance
    padding: 0

    // Close policy: manual control only
    closePolicy: Popup.NoAutoClose
    modal: false

    // Content
    Rectangle {
        id: tooltipContent
        implicitWidth: mainLayout.implicitWidth + Theme.paddingLarge * 2
        implicitHeight: mainLayout.implicitHeight + Theme.paddingLarge * 2

        color: Theme.panelDark
        border.color: Theme.borderPrimary
        border.width: Theme.borderMedium
        radius: Theme.radiusMedium

        // Main horizontal layout that handles video button placement
        RowLayout {
            id: mainLayout
            anchors.fill: parent
            anchors.margins: Theme.paddingLarge
            spacing: Theme.spacingMedium

            // Video buttons column (left side when tooltip is right-anchored)
            Column {
                id: leftVideoColumn
                visible: videoButtonsRow.visible && isVideoOnLeft
                Layout.alignment: Qt.AlignTop
                spacing: Theme.spacingTiny

                Repeater {
                    model: visible ? videoUrls : []

                    Rectangle {
                        width: 36
                        height: 36
                        radius: Theme.radiusSmall

                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#ef4444" }
                            GradientStop { position: 1.0; color: "#dc2626" }
                        }

                        // Play icon or number for multiple videos
                        Text {
                            text: videoUrls.length > 1 ? String(index + 1) : ">"
                            color: "white"
                            font.pixelSize: videoUrls.length > 1 ? 14 : 18
                            font.weight: Font.Bold
                            anchors.centerIn: parent
                            anchors.horizontalCenterOffset: videoUrls.length > 1 ? 0 : 2
                        }

                        // Hover effect
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: "white"
                            opacity: leftVideoMouseArea.containsMouse ? 0.2 : 0

                            Behavior on opacity {
                                NumberAnimation { duration: 150 }
                            }
                        }

                        MouseArea {
                            id: leftVideoMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor

                            onClicked: {
                                var url = modelData
                                backend.open_video(url, collectible.name + (videoUrls.length > 1 ? " (Video " + (index + 1) + ")" : ""))
                            }
                        }
                    }
                }
            }

            // Text content column (always present)
            ColumnLayout {
                id: contentLayout
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: Theme.spacingSmall

                // Collectible name
                Text {
                    text: collectible !== null ? String(collectible.name) : ""
                    color: Theme.accentYellow
                    font.pixelSize: 16
                    font.weight: Theme.fontWeightBold
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    Layout.maximumWidth: 250
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    maximumLineCount: 2
                }

                // Type
                Text {
                    text: collectible !== null ? ("Type: " + String(collectible.type)) : ""
                    color: Theme.textSecondary
                    font.pixelSize: 12
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    Layout.maximumWidth: 250
                    elide: Text.ElideRight
                }

                // Help text (if available)
                Text {
                    visible: collectible !== null && collectible.help !== undefined && collectible.help !== ""
                    text: visible ? String(collectible.help) : ""
                    color: Theme.textPrimary
                    font.pixelSize: 12
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    Layout.maximumWidth: 250
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }

                // Collected status
                Text {
                    text: (collectible !== null && collectible.collected === true) ? "[COLLECTED]" : "[NOT COLLECTED]"
                    color: (collectible !== null && collectible.collected === true) ? Theme.success : Theme.error
                    font.pixelSize: 11
                    font.weight: Theme.fontWeightMedium
                    font.family: Theme.fontFamily
                    Layout.topMargin: Theme.spacingTiny
                }
            }

            // Video buttons column (right side when tooltip is left-anchored)
            Column {
                id: rightVideoColumn
                visible: videoButtonsRow.visible && !isVideoOnLeft
                Layout.alignment: Qt.AlignTop
                spacing: Theme.spacingTiny

                Repeater {
                    model: visible ? videoUrls : []

                    Rectangle {
                        width: 36
                        height: 36
                        radius: Theme.radiusSmall

                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#ef4444" }
                            GradientStop { position: 1.0; color: "#dc2626" }
                        }

                        // Play icon or number for multiple videos
                        Text {
                            text: videoUrls.length > 1 ? String(index + 1) : ">"
                            color: "white"
                            font.pixelSize: videoUrls.length > 1 ? 14 : 18
                            font.weight: Font.Bold
                            anchors.centerIn: parent
                            anchors.horizontalCenterOffset: videoUrls.length > 1 ? 0 : 2
                        }

                        // Hover effect
                        Rectangle {
                            anchors.fill: parent
                            radius: parent.radius
                            color: "white"
                            opacity: rightVideoMouseArea.containsMouse ? 0.2 : 0

                            Behavior on opacity {
                                NumberAnimation { duration: 150 }
                            }
                        }

                        MouseArea {
                            id: rightVideoMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor

                            onClicked: {
                                var url = modelData
                                backend.open_video(url, collectible.name + (videoUrls.length > 1 ? " (Video " + (index + 1) + ")" : ""))
                            }
                        }
                    }
                }
            }
        }

        // Hidden Row element used for compatibility with existing code
        Row {
            id: videoButtonsRow
            visible: collectible && hasVideos
            width: 0
            height: 0
        }
    }

    // Helper properties for video handling
    property bool hasVideos: collectible && collectible.video && collectible.video !== ""
    property var videoUrls: {
        if (!hasVideos) return []

        // Check if video is an array or single string
        if (Array.isArray(collectible.video)) {
            return collectible.video
        } else {
            return [collectible.video]
        }
    }

    // Determine if video buttons should be on left or right based on anchor corner
    property bool isVideoOnLeft: anchorCorner.includes('right')

    // Position tooltip near collectible with smart corner-anchoring
    function showNear(x, y) {
        collectibleX = x
        collectibleY = y

        // Calculate tooltip dimensions
        var tooltipWidth = tooltipContent.implicitWidth
        var tooltipHeight = tooltipContent.implicitHeight

        // Screen bounds
        var screenWidth = 1920
        var screenHeight = 1080
        var offset = 6

        // Try 4 positions (prioritize bottom-left to avoid covering collectible)
        var candidates = [
            // Bottom-left corner offset (tooltip to the right and up)
            { x: x + offset, y: y - tooltipHeight - offset, corner: 'bottom-left' },
            // Bottom-right corner offset (tooltip to the left and up)
            { x: x - tooltipWidth - offset, y: y - tooltipHeight - offset, corner: 'bottom-right' },
            // Top-left corner offset (tooltip to the right and down)
            { x: x + offset, y: y + offset, corner: 'top-left' },
            // Top-right corner offset (tooltip to the left and down)
            { x: x - tooltipWidth - offset, y: y + offset, corner: 'top-right' }
        ]

        // Filter out off-screen positions
        var validCandidates = candidates.filter(function(pos) {
            return pos.x >= 0 &&
                   pos.x + tooltipWidth <= screenWidth &&
                   pos.y >= 0 &&
                   pos.y + tooltipHeight <= screenHeight
        })

        // Use first valid position (or fallback)
        var selectedPos
        if (validCandidates.length > 0) {
            selectedPos = validCandidates[0]
        } else {
            // Fallback: center on collectible
            selectedPos = {
                x: Math.max(0, Math.min(x, screenWidth - tooltipWidth)),
                y: Math.max(0, Math.min(y, screenHeight - tooltipHeight)),
                corner: 'center'
            }
        }

        // Store anchor corner for video button positioning
        anchorCorner = selectedPos.corner

        // Position tooltip
        tooltip.x = selectedPos.x
        tooltip.y = selectedPos.y

        // Show tooltip
        tooltip.open()
    }

    // Hide with delay
    Timer {
        id: hideTimer
        interval: 50  // Quick hide for responsive feel
        onTriggered: tooltip.close()
    }

    function hideWithDelay() {
        hideTimer.restart()
    }

    function cancelHide() {
        hideTimer.stop()
    }

    // Hit-testing for video buttons (global coordinates)
    function isClickOnVideoButton(globalX, globalY) {
        if (!visible || !hasVideos) {
            return false
        }

        // Check left video column buttons if visible
        if (leftVideoColumn.visible) {
            for (var i = 0; i < leftVideoColumn.children.length; i++) {
                var button = leftVideoColumn.children[i]
                if (!button || button.toString().indexOf("Repeater") !== -1) continue

                // Get button bounds in global coordinates
                var buttonGlobalPos = button.mapToGlobal(Qt.point(0, 0))
                var left = buttonGlobalPos.x
                var top = buttonGlobalPos.y
                var right = left + button.width
                var bottom = top + button.height

                if (globalX >= left && globalX <= right && globalY >= top && globalY <= bottom) {
                    // Find which video URL this is
                    var videoIndex = Math.floor(i / 2) // Account for Repeater internals
                    if (videoIndex < videoUrls.length) {
                        var url = videoUrls[videoIndex]
                        var videoName = collectible.name + (videoUrls.length > 1 ? " (Video " + (videoIndex + 1) + ")" : "")
                        backend.open_video(url, videoName)
                    }
                    return true
                }
            }
        }

        // Check right video column buttons if visible
        if (rightVideoColumn.visible) {
            for (var j = 0; j < rightVideoColumn.children.length; j++) {
                var rightButton = rightVideoColumn.children[j]
                if (!rightButton || rightButton.toString().indexOf("Repeater") !== -1) continue

                // Get button bounds in global coordinates
                var rightButtonGlobalPos = rightButton.mapToGlobal(Qt.point(0, 0))
                var rightLeft = rightButtonGlobalPos.x
                var rightTop = rightButtonGlobalPos.y
                var rightRight = rightLeft + rightButton.width
                var rightBottom = rightTop + rightButton.height

                if (globalX >= rightLeft && globalX <= rightRight && globalY >= rightTop && globalY <= rightBottom) {
                    // Find which video URL this is
                    var rightVideoIndex = Math.floor(j / 2) // Account for Repeater internals
                    if (rightVideoIndex < videoUrls.length) {
                        var rightUrl = videoUrls[rightVideoIndex]
                        var rightVideoName = collectible.name + (videoUrls.length > 1 ? " (Video " + (rightVideoIndex + 1) + ")" : "")
                        backend.open_video(rightUrl, rightVideoName)
                    }
                    return true
                }
            }
        }

        return false
    }
}