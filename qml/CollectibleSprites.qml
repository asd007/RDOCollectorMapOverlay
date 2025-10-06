import QtQuick 2.15
import QtQuick.Controls 2.15

/*
 * High-performance collectible rendering using viewport transform.
 *
 * Instead of updating individual sprite positions, we transform the entire
 * container based on viewport offset. This allows the GPU to handle all
 * sprite positioning with a single matrix operation.
 *
 * Architecture:
 * 1. Sprites have static positions in detection space (map coordinates)
 * 2. Backend sends viewport offset (x, y, scale) - only 3 numbers per frame
 * 3. Container applies inverse transform to "move the camera"
 * 4. GPU handles all sprite positioning automatically
 */

Item {
    id: root
    anchors.fill: parent
    clip: true  // Clip sprites outside screen bounds

    // Viewport properties (bound to backend)
    property real viewportX: backend.viewportX
    property real viewportY: backend.viewportY
    property real viewportWidth: backend.viewportWidth
    property real viewportHeight: backend.viewportHeight
    property real spriteOpacity: backend.opacity

    // All collectibles list (static positions in detection/map space)
    property var collectibles: backend.visibleCollectibles

    // Screen dimensions
    readonly property real screenWidth: 1920
    readonly property real screenHeight: 1080

    // Calculate scale factor to fit viewport into screen
    readonly property real scaleX: screenWidth / viewportWidth
    readonly property real scaleY: screenHeight / viewportHeight

    // Container for all sprites (transformed as one unit)
    Item {
        id: spriteContainer

        // Transform: offset + scale to map detection space → screen space
        transform: [
            // Scale detection space to screen space
            Scale {
                xScale: scaleX
                yScale: scaleY
            },
            // Translate to move viewport into view (inverse of viewport position)
            Translate {
                x: -viewportX * scaleX
                y: -viewportY * scaleY
            }
        ]

        // Render all collectibles (static positions in detection space)
        Repeater {
            model: root.collectibles

            delegate: Image {
                // Static position in detection space (never updated!)
                // map_x and map_y are in detection space coordinates
                x: modelData.map_x ? (modelData.map_x - 24) : 0  // Center sprite (48x48)
                y: modelData.map_y ? (modelData.map_y - 24) : 0

                width: 48
                height: 48

                opacity: root.spriteOpacity * (modelData.collected ? 0.5 : 1.0)

                // Use SVG data URL for sprite (cached by QML)
                source: "data:image/svg+xml;utf8," + backend.get_icon_svg(getIconName(modelData.type))

                cache: true  // Cache decoded image
                smooth: true
                antialiasing: true

                // Helper to map collectible type to icon name
                function getIconName(colType) {
                    var iconMap = {
                        'arrowhead': 'arrowhead',
                        'bottle': 'bottle',
                        'coin': 'coin',
                        'egg': 'egg',
                        'flower': 'flower',
                        'card_tarot': 'tarot',
                        'cups': 'tarot',
                        'pentacles': 'tarot',
                        'swords': 'tarot',
                        'wands': 'tarot',
                        'jewelry_random': 'jewelry',
                        'bracelet': 'jewelry',
                        'earring': 'jewelry',
                        'necklace': 'jewelry',
                        'ring': 'jewelry',
                        'heirlooms': 'heirloom',
                        'coastal': 'fossil',
                        'oceanic': 'fossil',
                        'megafauna': 'fossil',
                        'fossils_random': 'fossil',
                        'random': 'random'
                    }
                    return iconMap[colType] || 'random'
                }
            }
        }
    }
}
