import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import theme 1.0

Rectangle {
    id: root

    // Properties from model
    required property var setData  // Contains: name, category, icon, items, progress, total, isVisible, isExpanded
    property var backend: null  // Reference to OverlayBackend (set from parent)

    width: parent.width
    height: isExpanded ? headerHeight + Math.ceil(setData.items.length / 2) * itemHeight : headerHeight
    color: "transparent"

    readonly property int headerHeight: 48  // Match Electron: 12px padding * 2 + content
    readonly property int itemHeight: 34   // Match Electron: 8px padding * 2 + content
    readonly property bool isExpanded: setData.isExpanded || false
    readonly property bool isComplete: setData.progress === setData.total

    // Debug: Log items when component loads
    Component.onCompleted: {
        console.log("[CollectionSetItem] Category:", setData.category,
                    "Items count:", setData.items ? setData.items.length : 0,
                    "Expanded:", isExpanded)
    }

    // Debug: Track expansion state changes
    onIsExpandedChanged: {
        console.log("[CollectionSetItem] Expanded state changed:", isExpanded, "Category:", setData.category)
    }

    Behavior on height {
        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
    }

    // Header Row (match Electron styling)
    Rectangle {
        id: header
        width: parent.width
        height: headerHeight
        color: mouseArea.containsMouse ? "#F2464646" : "#F2323232"  // Electron: rgba(70,70,70,0.95) : rgba(50,50,50,0.95)

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 4.5  // Match Electron gap
            z: 0  // Below mouse areas

            // Expand/Collapse Arrow (rotates 90deg when expanded)
            Text {
                text: "▶"  // Right-pointing triangle
                color: "#d1d5db"
                font.pixelSize: 15
                Layout.preferredWidth: 18
                opacity: setData.items && setData.items.length > 0 ? 1.0 : 0.3

                // Rotate 90 degrees when expanded
                rotation: isExpanded ? 90 : 0
                Behavior on rotation {
                    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                }

                // Center the rotation point
                transformOrigin: Item.Center
            }

            // Icon (SVG from backend - match Electron map icons)
            CollectibleIcon {
                iconName: setData.icon || "random"
                iconBackend: root.backend  // Pass backend reference directly
                size: 24
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
            }

            // Progress Counter (before name - match Electron layout)
            Text {
                text: setData.progress + "/" + setData.total
                color: "#d1d5db"
                font.pixelSize: 15
                Layout.minimumWidth: 52
            }

            // Set Name
            Text {
                text: setData.name
                color: isComplete ? "#34d399" : "#f3f4f6"  // Match Electron complete color
                font.pixelSize: 17  // Match Electron (rounded from 16.5)
                Layout.fillWidth: true
            }

            // Visibility Toggle (Eye Icon)
            Item {
                Layout.preferredWidth: 30
                Layout.preferredHeight: headerHeight

                Text {
                    id: eyeText
                    anchors.centerIn: parent
                    text: setData.isVisible ? "👁️" : "👁️‍🗨️"
                    color: setData.isVisible ? "#fcd34d" : "#9ca3af"
                    font.pixelSize: 21
                    opacity: setData.isVisible ? 1.0 : 0.5
                    horizontalAlignment: Text.AlignHCenter

                    // Hover effect
                    scale: eyeMouseArea.containsMouse ? 1.2 : 1.0
                    Behavior on scale {
                        NumberAnimation { duration: 200 }
                    }
                }

                MouseArea {
                    id: eyeMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    z: 10  // Ensure it's above header MouseArea

                    onClicked: function(mouse) {
                        console.log("[CollectionSetItem] Eye clicked, category:", setData.category)
                        if (backend) {
                            backend.toggle_category_visibility(setData.category)
                        }
                        mouse.accepted = true  // Stop propagation to header
                    }
                }
            }
        }

        // Header click area (entire header except eye icon) - ABOVE RowLayout in z-order
        MouseArea {
            id: mouseArea
            anchors.fill: parent
            anchors.rightMargin: 40  // Leave space for eye icon
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            z: 1  // Above RowLayout

            onClicked: function(mouse) {
                // Handle header click (expand/collapse)
                if (backend) {
                    console.log("[CollectionSetItem] Header clicked, category:", setData.category)
                    backend.toggle_set_expanded(setData.category)
                }
            }
        }
    }

    // Items List (two-column grid - match Electron)
    Flow {
        id: itemsList
        anchors.top: header.bottom
        width: parent.width
        visible: isExpanded
        opacity: isExpanded ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }

        // Debug visibility
        onVisibleChanged: {
            console.log("[CollectionSetItem] Items list visible changed:", visible,
                        "Category:", setData.category,
                        "Items:", setData.items ? setData.items.length : 0)
        }

        Repeater {
            model: setData.items || []

            onCountChanged: {
                console.log("[CollectionSetItem] Repeater count:", count, "for category:", setData.category)
            }

            Rectangle {
                width: itemsList.width / 2  // Two-column layout
                height: itemHeight
                color: itemMouseArea.containsMouse ? "#33D97706" : "transparent"  // Match Electron: rgba(217, 119, 6, 0.2)
                border.width: 1
                border.color: "#0DFFFFFF"  // rgba(255, 255, 255, 0.05)

                MouseArea {
                    id: itemMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor

                    onClicked: {
                        if (backend) {
                            backend.toggle_collected(setData.category, modelData.name)
                        }
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 6

                    // Checkbox (match Electron: ✓/○)
                    Text {
                        text: modelData.collected ? "✓" : "○"
                        color: modelData.collected ? "#34d399" : "#d1d5db"
                        font.pixelSize: 15
                        Layout.preferredWidth: 18
                    }

                    // Item Name
                    Text {
                        text: modelData.name
                        color: modelData.collected ? "#9ca3af" : "#f3f4f6"
                        font.pixelSize: 15  // Match Electron
                        font.strikeout: modelData.collected
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }

    // Bottom separator (match Electron)
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: "#1AFFFFFF"  // rgba(255, 255, 255, 0.1)
    }
}
