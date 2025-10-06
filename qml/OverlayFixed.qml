import QtQuick 2.15
import QtQuick.Window 2.15
import RDOOverlay 1.0
import theme 1.0

/*
 * Fixed Overlay Window with Selective Click-Through
 *
 * Uses ClickThroughManager for robust region-based interaction handling.
 */

Window {
    id: overlayWindow

    // Window properties
    width: 1920
    height: 1080
    visible: backend.overlayVisible
    color: "transparent"

    // Start with frameless, always-on-top, but NOT click-through
    // ClickThroughManager will handle the WS_EX_TRANSPARENT flag dynamically
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    // Component creation completed handler
    Component.onCompleted: {
        console.log("[OverlayFixed] Window created, initializing click-through manager")

        // Initialize click-through manager with this window
        clickThroughManager.setWindow(overlayWindow)

        // Update interactive regions based on UI state
        updateInteractiveRegions()

        // Start monitoring
        clickThroughManager.start()
    }

    // Click-through manager instance
    ClickThroughManager {
        id: clickThroughManager

        // Log state changes
        onClickThroughChanged: function(enabled) {
            console.log("[OverlayFixed] Click-through state:", enabled ? "ENABLED" : "DISABLED")
        }
    }

    // Function to update interactive regions
    function updateInteractiveRegions() {
        var regions = []

        // Add tracker region if visible
        if (backend.trackerVisible && tracker.visible) {
            var trackerRect = Qt.rect(0, 0, tracker.width, overlayWindow.height)
            regions.push(trackerRect)
            console.log("[OverlayFixed] Added tracker region:", trackerRect)
        }

        // Add tooltip region if visible
        if (collectibleTooltip.visible) {
            var tooltipRect = Qt.rect(
                collectibleTooltip.x,
                collectibleTooltip.y,
                collectibleTooltip.width,
                collectibleTooltip.height
            )
            regions.push(tooltipRect)
            console.log("[OverlayFixed] Added tooltip region:", tooltipRect)
        }

        // Update manager with new regions
        clickThroughManager.setInteractiveRegions(regions)
    }

    // Monitor tracker visibility changes
    Connections {
        target: backend

        function onTrackerVisibilityChanged() {
            console.log("[OverlayFixed] Tracker visibility changed:", backend.trackerVisible)
            updateInteractiveRegions()
        }
    }

    // Collectible canvas (always click-through)
    CollectibleCanvas {
        id: canvas
        anchors.fill: parent
        collectibles: backend.visibleCollectibles
        opacityValue: backend.opacity
    }

    // Bottom overlay container (click-through)
    Item {
        id: bottomOverlay
        anchors {
            bottom: parent.bottom
            left: parent.left
            right: parent.right
        }
        height: parent.height * 0.2

        Row {
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
                bottomMargin: Theme.marginSmall
            }
            spacing: Theme.marginMedium

            StatusPill {
                id: statusPill
                statusText: backend.statusText
                statusColor: backend.statusColor
            }

            FPSCounter {
                id: fpsCounter
                fps: backend.fps
            }
        }
    }

    // Collection tracker (interactive when visible)
    CollectionTracker {
        id: tracker
        anchors {
            left: parent.left
            top: parent.top
            bottom: parent.bottom
        }

        collapsed: !backend.trackerVisible

        // Update regions when visibility changes
        onVisibleChanged: {
            console.log("[OverlayFixed] Tracker visible changed:", visible)
            updateInteractiveRegions()
        }

        // Handle mouse events normally when not click-through
        MouseArea {
            anchors.fill: parent
            enabled: !clickThroughManager.isClickThrough
            acceptedButtons: Qt.LeftButton | Qt.RightButton

            onClicked: function(mouse) {
                console.log("[OverlayFixed] Tracker clicked at:", mouse.x, mouse.y)
                // Let child components handle the click
                mouse.accepted = false
            }
        }
    }

    // Collectible tooltip (interactive when visible)
    CollectibleTooltip {
        id: collectibleTooltip

        // Update regions when visibility changes
        onVisibleChanged: {
            console.log("[OverlayFixed] Tooltip visible changed:", visible)
            updateInteractiveRegions()
        }

        // Update regions when position changes
        onXChanged: {
            if (visible) updateInteractiveRegions()
        }
        onYChanged: {
            if (visible) updateInteractiveRegions()
        }
    }

    // Cursor hover detection for tooltips
    Timer {
        id: hoverTimer
        interval: 16  // ~60 FPS
        running: backend.overlayVisible
        repeat: true

        property var currentHovered: null

        onTriggered: {
            // Get cursor position from backend
            var cursorPos = backend.get_cursor_pos()
            if (!cursorPos) return

            // Skip hover detection if cursor is over UI
            if (!clickThroughManager.isClickThrough) {
                // Cursor is over interactive UI, don't update tooltips
                if (currentHovered) {
                    currentHovered = null
                    collectibleTooltip.hideWithDelay()
                }
                return
            }

            // Hit-test collectibles at cursor position
            var hoveredItem = findCollectibleAt(cursorPos.x, cursorPos.y)

            // Check if hover state changed
            if (hoveredItem !== currentHovered) {
                if (hoveredItem) {
                    // Started hovering - show tooltip
                    currentHovered = hoveredItem
                    collectibleTooltip.collectible = hoveredItem
                    collectibleTooltip.showNear(hoveredItem.x, hoveredItem.y)
                    collectibleTooltip.cancelHide()
                } else {
                    // Stopped hovering - hide tooltip
                    currentHovered = null
                    collectibleTooltip.hideWithDelay()
                }
            }
        }
    }

    // Right-click handler for collectibles
    Connections {
        target: backend

        function onMouseClicked(x, y, button) {
            console.log("[OverlayFixed] Mouse click received:", x, y, button)

            // Only handle right-clicks on collectibles when click-through is enabled
            if (button === "right" && clickThroughManager.isClickThrough) {
                var collectible = findCollectibleAt(x, y)
                if (collectible) {
                    console.log("[OverlayFixed] Right-click on collectible:", collectible.name)
                    backend.toggle_collected(collectible.category, collectible.name)
                }
            }
        }
    }

    // Helper function to find collectible at screen position
    function findCollectibleAt(screenX, screenY) {
        var collectibles = backend.visibleCollectibles
        if (!collectibles) return null

        var hitRadius = 24  // Half of sprite size (48x48)

        for (var i = 0; i < collectibles.length; i++) {
            var col = collectibles[i]
            var dx = screenX - col.x
            var dy = screenY - col.y
            var distance = Math.sqrt(dx * dx + dy * dy)

            if (distance <= hitRadius) {
                return col
            }
        }

        return null
    }
}