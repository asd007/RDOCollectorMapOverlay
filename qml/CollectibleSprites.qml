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

    // Viewport properties from backend
    property real backendViewportX: backend.viewportX  // Predicted position
    property real backendViewportY: backend.viewportY
    property real backendRawX: backend.viewportRawX    // Raw phase correlation (ground truth)
    property real backendRawY: backend.viewportRawY
    property real backendViewportWidth: backend.viewportWidth
    property real backendViewportHeight: backend.viewportHeight

    // Predicted viewport (interpolated at 60 FPS for smooth motion)
    property real viewportX: backendViewportX
    property real viewportY: backendViewportY
    property real viewportWidth: backendViewportWidth
    property real viewportHeight: backendViewportHeight

    // Track viewport changes for FPS measurement (only count X to avoid double-counting)
    onViewportXChanged: renderFrameCount++

    // Mouse-based prediction state
    property real lastMouseX: 0
    property real lastMouseY: 0
    property bool mouseValid: false

    // Pan detection state - active after short delay to distinguish clicks from drags
    property bool isPanning: false
    property int panStartDelay: 30  // ms delay to detect intentional pan

    // Pan end convergence tracking
    property real panEndTargetX: 0  // Where mouse left the viewport when pan ended
    property real panEndTargetY: 0
    property real lastBackendX: 0   // Track backend's previous position
    property real lastBackendY: 0
    property bool waitingForConvergence: false
    property real convergenceThreshold: 10  // Pixels - when to accept backend again

    property real spriteOpacity: backend.opacity

    // All collectibles list (static positions in detection/map space)
    property var collectibles: backend.visibleCollectibles

    // Initialize FPS timer on load
    Component.onCompleted: {
        lastRenderFpsTime = Date.now()
    }


    // Screen dimensions (full screen - no cropping)
    readonly property real screenWidth: 1920
    readonly property real screenHeight: 1080

    // Calculate scale factor to fit viewport into screen
    readonly property real scaleX: screenWidth / viewportWidth
    readonly property real scaleY: screenHeight / viewportHeight

    // Prediction state
    property real lastBackendUpdate: 0
    property real predictionStartTime: 0

    // FPS monitoring for rendering performance
    property int renderFrameCount: 0
    property real lastRenderFpsTime: 0
    property real renderFps: 0

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

                cache: true
                smooth: false  // Disable expensive bilinear filtering
                antialiasing: false  // Disable antialiasing for performance
                asynchronous: true  // Load images asynchronously

                // Counter-scale to maintain constant size regardless of container scale
                transform: Scale {
                    xScale: 1.0 / root.scaleX
                    yScale: 1.0 / root.scaleY
                }

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

    // Smooth transition state
    property bool isTransitioning: false
    property real transitionStartX: 0
    property real transitionStartY: 0
    property real transitionProgress: 0
    property int transitionDuration: 100  // ms for smooth transition

    // When backend updates, decide whether to use it or keep mouse prediction
    onBackendViewportXChanged: {
        if (isPanning) {
            // Active panning - ignore backend, mouse has authority
            lastBackendX = backendViewportX
            lastBackendY = backendViewportY
            return
        }

        if (waitingForConvergence) {
            // Check if backend is converging toward pan end target
            var currentDist = Math.sqrt(
                Math.pow(backendViewportX - panEndTargetX, 2) +
                Math.pow(backendViewportY - panEndTargetY, 2)
            )
            var previousDist = Math.sqrt(
                Math.pow(lastBackendX - panEndTargetX, 2) +
                Math.pow(lastBackendY - panEndTargetY, 2)
            )

            // Update backend tracking
            lastBackendX = backendViewportX
            lastBackendY = backendViewportY

            if (currentDist < convergenceThreshold) {
                // Backend caught up - accept it
                waitingForConvergence = false
                viewportX = backendViewportX
                viewportY = backendViewportY
            } else if (currentDist < previousDist) {
                // Backend is converging - keep current position (don't snap back)
                // Don't update viewportX/Y - stay where we are
            } else {
                // Backend diverging - accept it immediately (something changed)
                waitingForConvergence = false
                viewportX = backendViewportX
                viewportY = backendViewportY
            }
        } else if (!isTransitioning) {
            // Normal mode - use backend truth (authoritative)
            viewportX = backendViewportX
            viewportY = backendViewportY
            lastBackendX = backendViewportX
            lastBackendY = backendViewportY
        }
    }

    // Pan activation timer - short delay to distinguish clicks from drags
    Timer {
        id: panActivationTimer
        interval: panStartDelay
        running: false
        repeat: false
        onTriggered: {
            isPanning = true
        }
    }

    // Listen to backend panning state changes
    Connections {
        target: backend
        function onIsPanningChanged() {
            if (backend.isPanning) {
                // Mouse button down - start short timer
                panActivationTimer.restart()
            } else {
                // Mouse button released
                panActivationTimer.stop()
                if (isPanning) {
                    // Pan just ended - record target and enable convergence tracking
                    panEndTargetX = viewportX
                    panEndTargetY = viewportY
                    lastBackendX = backendViewportX
                    lastBackendY = backendViewportY
                    waitingForConvergence = true

                    isPanning = false
                    mouseValid = false
                }
            }
        }
    }

    // Mouse tracking timer (high frequency for smooth prediction)
    Timer {
        id: mouseTracker
        interval: 8  // ~120 Hz for ultra-smooth tracking
        running: true
        repeat: true

        onTriggered: {
            var cursorPos = backend.get_cursor_pos()
            if (!cursorPos) return

            if (mouseValid && isPanning) {
                // Calculate mouse delta in screen pixels
                var mouseDx = cursorPos.x - lastMouseX
                var mouseDy = cursorPos.y - lastMouseY
                var mouseDist = Math.sqrt(mouseDx * mouseDx + mouseDy * mouseDy)

                // Apply mouse prediction when panning and mouse moved
                if (mouseDist > 0.5) {
                    // "Grab map" panning: mouse left = map moves left = viewport moves right
                    // Mouse delta in screen pixels needs to convert to detection space
                    // scaleX = screen/viewport, so viewport/screen = 1/scaleX
                    // But we also invert direction: mouseDx > 0 (right) → viewportDx < 0 (left)
                    var viewportDx = -mouseDx * (viewportWidth / screenWidth)
                    var viewportDy = -mouseDy * (viewportHeight / screenHeight)

                    // Update predicted viewport
                    viewportX += viewportDx
                    viewportY += viewportDy
                }
            }

            // Calculate rendering FPS
            var now = Date.now()
            var elapsed = now - lastRenderFpsTime
            if (elapsed >= 1000) {
                renderFps = (renderFrameCount * 1000.0) / elapsed
                console.log("[Render] FPS:", renderFps.toFixed(1), "frames in", elapsed, "ms")
                renderFrameCount = 0
                lastRenderFpsTime = now
            }

            // Update mouse tracking
            lastMouseX = cursorPos.x
            lastMouseY = cursorPos.y
            mouseValid = true
        }
    }
}
