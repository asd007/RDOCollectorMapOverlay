import QtQuick 2.15

/*
 * Collectible SVG Icon Component
 *
 * Renders SVG icons from backend (qml/svg_icons.py TRACKER_ICONS)
 * Used in CollectionSetItem for accordion headers
 */

Item {
    id: root

    property string iconName: "random"
    property int size: 24
    property var iconBackend: null  // Pass backend explicitly from parent

    width: size
    height: size

    // Get SVG string from backend (exposed via OverlayBackend)
    readonly property string svgString: iconBackend ? iconBackend.get_icon_svg(iconName) : ""

    // Render SVG using Image component with data URI
    Image {
        anchors.fill: parent
        sourceSize: Qt.size(size, size)
        source: svgString ? "data:image/svg+xml;utf8," + encodeURIComponent(svgString) : ""
        smooth: true
        antialiasing: true
        visible: svgString !== ""
    }

    // Fallback text if backend not available
    Text {
        anchors.centerIn: parent
        text: "?"
        font.pixelSize: size * 0.8
        color: "#ffd700"
        visible: !svgString
    }
}
