import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import theme 1.0

/*
 * Collection Tracker Panel
 *
 * Collapsible panel showing:
 * - Collectible sets (guaranteed/random tabs)
 * - Per-item collection checkboxes
 * - Visibility toggles (eye icons)
 * - Overall progress
 *
 * Uses centralized Theme for all styling.
 * Header is separate component in Overlay.qml.
 */

Rectangle {
    id: root

    // Collapse state (controlled by parent via backend.trackerVisible)
    property bool collapsed

    // Backend reference (should be set from parent)
    property var trackerBackend: null

    // Dimensions from theme
    width: Theme.trackerWidth
    height: parent.height

    // Styling from theme
    color: Theme.panelDark
    border.color: Theme.borderAccent
    border.width: Theme.borderThick

    // Component initialization
    Component.onCompleted: {
        // Force initial position based on collapsed state
        if (collapsed) {
            x = -width
        }
    }

    // Slide animation (left to right / right to left)
    x: collapsed ? -width : 0
    Behavior on x {
        NumberAnimation {
            duration: 200  // Fast animation (200ms)
            easing.type: Easing.OutCubic  // Smooth deceleration
        }
    }

    // Fade animation (fade out when collapsing, fade in when expanding)
    opacity: collapsed ? 0.0 : 1.0
    Behavior on opacity {
        NumberAnimation {
            duration: 200  // Match slide duration
            easing.type: Easing.OutCubic
        }
    }

    // Hit-testing function for global mouse clicks (panel only, header is separate)
    function handleGlobalClick(globalX, globalY) {
        // Tracker panel - check if click is within bounds
        var trackerGlobalPos = root.mapToGlobal(Qt.point(0, 0))
        if (globalX < trackerGlobalPos.x || globalX > trackerGlobalPos.x + root.width ||
            globalY < trackerGlobalPos.y || globalY > trackerGlobalPos.y + root.height) {
            return false  // Not on tracker panel
        }

        // Check tab clicks
        var tabBarGlobalPos = tabBar.mapToGlobal(Qt.point(0, 0))
        if (globalY >= tabBarGlobalPos.y && globalY < tabBarGlobalPos.y + tabBar.height) {
            var tabWidth = tabBar.width / 2
            if (globalX >= tabBarGlobalPos.x && globalX < tabBarGlobalPos.x + tabWidth) {
                setsTab.checked = true
                randomTab.checked = false
                return true
            } else if (globalX >= tabBarGlobalPos.x + tabWidth && globalX < tabBarGlobalPos.x + tabBar.width) {
                setsTab.checked = false
                randomTab.checked = true
                return true
            }
        }

        // For now, return true to indicate click was on tracker
        // TODO: Add hit-testing for set items, checkboxes, eye icons
        return true
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Tabs (header is now separate in Overlay.qml)
        Rectangle {
            id: tabBar
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.trackerTabHeight
            color: Theme.panelLight

            RowLayout {
                anchors.fill: parent
                spacing: 0

                TabButton {
                    id: setsTab
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    text: "Sets"
                    checked: true

                    onClicked: {
                        setsTab.checked = true
                        randomTab.checked = false
                    }

                    // Custom styling from theme
                    background: Rectangle {
                        color: setsTab.checked ? Theme.activeBackground : "transparent"

                        // Bottom border when active
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: setsTab.checked ? Theme.borderThick : 0
                            color: Theme.accentYellow
                        }
                    }

                    contentItem: Text {
                        text: setsTab.text
                        color: setsTab.checked ? Theme.accentYellow : Theme.textSecondary
                        font.pixelSize: Theme.fontMedium
                        font.family: Theme.fontFamily
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                TabButton {
                    id: randomTab
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    text: "Random"
                    checked: false

                    onClicked: {
                        setsTab.checked = false
                        randomTab.checked = true
                    }

                    background: Rectangle {
                        color: randomTab.checked ? Theme.activeBackground : "transparent"

                        // Bottom border when active
                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: randomTab.checked ? Theme.borderThick : 0
                            color: Theme.accentYellow
                        }
                    }

                    contentItem: Text {
                        text: randomTab.text
                        color: randomTab.checked ? Theme.accentYellow : Theme.textSecondary
                        font.pixelSize: Theme.fontMedium
                        font.family: Theme.fontFamily
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        // Content (scrollable sets/items)
        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            // Custom scrollbar styling from theme
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: Theme.scrollbarWidth

                contentItem: Rectangle {
                    radius: Theme.scrollbarRadius
                    color: Theme.scrollbarThumb
                }

                background: Rectangle {
                    color: Theme.scrollbarTrack
                }
            }

            // Content area
            ColumnLayout {
                width: parent.width
                spacing: 0

                // Implicit height from children for ScrollView to work
                implicitHeight: childrenRect.height

                // Render collection sets from backend
                Repeater {
                    id: setsRepeater
                    model: trackerBackend ? trackerBackend.collectionSets.filter(function(set) {
                        return setsTab.checked ? !set.isRandom : set.isRandom
                    }) : []

                    delegate: CollectionSetItem {
                        required property var modelData
                        Layout.fillWidth: true
                        setData: modelData
                        backend: trackerBackend
                    }
                }

                // Empty state
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.marginHuge
                    text: trackerBackend.totalItems === 0 ? "Loading collectibles..." : "No items in this tab"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontMedium
                    font.family: Theme.fontFamily
                    horizontalAlignment: Text.AlignHCenter
                    visible: trackerBackend.totalItems === 0 ||
                             (trackerBackend.collectionSets && trackerBackend.collectionSets.filter(function(set) {
                                 if (setsTab.checked) return !set.isRandom
                                 else return set.isRandom
                             }).length === 0)
                }
            }
        }

        // Footer with overall progress
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.trackerFooterHeight
            color: Theme.panelMedium

            // Top border
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: Theme.borderMedium
                color: Theme.borderPrimary
            }

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Theme.spacingSmall

                Text {
                    text: trackerBackend.totalCollected + "/" + trackerBackend.totalItems +
                          " (" + trackerBackend.completionPercent + "%)"
                    color: Theme.accentYellow
                    font.pixelSize: Theme.fontMedium
                    font.weight: Theme.fontWeightBold
                    font.family: Theme.fontFamily
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: "Data from Jean Ropke's Collectors Map"
                    color: Theme.textTertiary
                    font.pixelSize: Theme.fontTiny
                    font.family: Theme.fontFamily
                    horizontalAlignment: Text.AlignHCenter
                    Layout.alignment: Qt.AlignHCenter
                }
            }
        }
    }

}
