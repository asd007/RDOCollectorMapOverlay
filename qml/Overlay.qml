import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Layouts 1.15
import RDOOverlay 1.0
import theme 1.0

/*
 * Main Overlay Window
 *
 * Fullscreen transparent overlay displaying:
 * - Collectible markers (fast QPainter rendering)
 * - Status bar (bottom-left)
 * - FPS counter (bottom-right)
 * - Collection tracker (left sidebar)
 *
 * Uses centralized Theme for all styling and spacing.
 */

Window {
    id: overlayWindow

    // Window properties
    width: 1920
    height: 1080
    visible: backend.overlayVisible  // Controlled by F8
    color: "transparent"

    // Frameless, always-on-top
    // ClickThroughManager will handle WS_EX_TRANSPARENT flag dynamically
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    // Component initialization
    Component.onCompleted: {
        // Click-through manager is initialized from Python (app_qml.py)
        // updateInteractiveRegions() will be called from Python after setup
    }

    // Centralized registry of interactive components
    // Add new interactive components here with their logic
    readonly property var interactiveComponents: [
        {
            "name": "trackerHeader",
            "component": trackerHeader,
            "visible": function() {
                // Header is always visible
                return true
            },
            "enabled": function() {
                // Header is interactive (not click-through)
                return true
            },
            "getRect": function() {
                return Qt.rect(0, 0, trackerHeader.width, trackerHeader.height)
            },
            "handleClick": function(x, y, button) {
                if (button === "left") {
                    var rect = this.getRect()
                    if (x >= rect.x && x < rect.x + rect.width &&
                        y >= rect.y && y < rect.y + rect.height) {
                        backend.toggle_tracker()
                        return true
                    }
                }
                return false
            }
        },
        {
            "name": "trackerPanel",
            "component": tracker,
            "visible": function() {
                // Panel is visible when expanded
                return backend.trackerVisible
            },
            "enabled": function() {
                // Panel is interactive when expanded
                return backend.trackerVisible
            },
            "getRect": function() {
                return Qt.rect(0, trackerHeader.height, tracker.width, tracker.height)
            },
            "handleClick": function(x, y, button) {
                if (button === "left") {
                    // Forward to component's handleGlobalClick
                    return this.component.handleGlobalClick(x, y)
                }
                return false
            }
        },
        {
            "name": "tooltip",
            "component": collectibleTooltip,
            "visible": function() {
                // Tooltip visible state from component
                return collectibleTooltip.visible
            },
            "enabled": function() {
                // Tooltip is interactive when visible
                return collectibleTooltip.visible
            },
            "getRect": function() {
                return Qt.rect(
                    collectibleTooltip.x,
                    collectibleTooltip.y,
                    collectibleTooltip.width,
                    collectibleTooltip.height
                )
            },
            "handleClick": function(x, y, button) {
                if (button === "left") {
                    // Check video button
                    if (this.component.isClickOnVideoButton(x, y)) {
                        return true
                    }
                }
                return false
            }
        }
    ]

    // Update interactive regions based on component states
    function updateInteractiveRegions() {
        // Check if clickThroughManager is available (initialized from Python)
        if (typeof clickThroughManager === 'undefined') {
            return
        }

        var regions = []

        // Iterate through all registered interactive components
        for (var i = 0; i < interactiveComponents.length; i++) {
            var item = interactiveComponents[i]

            // Only add regions for enabled components
            // (enabled means interactive, not click-through)
            if (item.enabled && item.enabled()) {
                var rect = item.getRect()
                regions.push(rect)
            }
        }

        clickThroughManager.setInteractiveRegions(regions)
    }

    // Monitor tracker visibility
    Connections {
        target: backend
        function onTrackerVisibilityChanged() {
            updateInteractiveRegions()
        }
    }

    // Collectible sprites (Painted renderer) - always click-through
    CollectibleSpritesPainted {
        id: sprites
        anchors.fill: parent
        z: 0  // Behind UI elements
        // Backend calls render_frame() directly, no QML bindings
    }

    // Bottom overlay container (centered at bottom) - click-through
    Item {
        id: bottomOverlay
        anchors {
            bottom: parent.bottom
            left: parent.left
            right: parent.right
        }
        height: parent.height * 0.2  // 20% of screen height

        // Centered content
        Row {
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
                bottomMargin: Theme.marginSmall
            }
            spacing: Theme.marginMedium

            // Status pill (click-through)
            StatusPill {
                id: statusPill
                statusText: backend.statusText
                statusColor: backend.statusColor
            }

            // FPS counter (click-through)
            FPSCounter {
                id: fpsCounter
                fps: backend.fps
                avgDrift: backend.avgDrift
            }
        }
    }

    // Collection tracker header (always visible button)
    Rectangle {
        id: trackerHeader
        anchors {
            left: parent.left
            top: parent.top
        }
        width: Theme.trackerWidth
        height: Theme.trackerHeaderHeight
        color: Theme.panelMedium
        border.color: Theme.borderAccent
        border.width: Theme.borderThick

        RowLayout {
            anchors.fill: parent
            anchors.margins: Theme.paddingLarge
            spacing: Theme.spacingMedium

            // Title
            Text {
                text: "Collections"
                color: Theme.accentYellow
                font.pixelSize: Theme.fontLarge
                font.weight: Theme.fontWeightBold
                font.family: Theme.fontFamily
            }

            // Hotkey hint
            Text {
                text: "F5"
                color: Theme.textTertiary
                font.pixelSize: Theme.fontSmall
                font.family: Theme.fontFamilyMono
            }

            Item { Layout.fillWidth: true }  // Spacer

            // Timer
            ColumnLayout {
                spacing: Theme.spacingMicro

                Text {
                    text: "NEXT:"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontTiny
                    font.letterSpacing: 0.75
                    font.family: Theme.fontFamily
                }

                Text {
                    id: timerText
                    text: "00:00:00"
                    color: Theme.accentYellow
                    font.pixelSize: Theme.fontMedium
                    font.weight: Theme.fontWeightBold
                    font.family: Theme.fontFamilyMono
                }
            }
        }

        // Bottom border
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: Theme.borderMedium
            color: Theme.borderPrimary
        }

        // Countdown timer (updates every second)
        Timer {
            interval: 1000  // 1 second
            running: true
            repeat: true
            onTriggered: {
                var now = new Date();
                var utcNow = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
                var tomorrow = new Date(utcNow);
                tomorrow.setUTCHours(24, 0, 0, 0);
                var diff = tomorrow - utcNow;
                var hours = Math.floor(diff / (1000 * 60 * 60));
                var minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                var seconds = Math.floor((diff % (1000 * 60)) / 1000);
                timerText.text = String(hours).padStart(2, '0') + ":" +
                                String(minutes).padStart(2, '0') + ":" +
                                String(seconds).padStart(2, '0');
            }
        }
    }

    // Collection tracker panel (slides in/out below header)
    CollectionTracker {
        id: tracker
        anchors {
            left: parent.left
            top: trackerHeader.bottom
            bottom: parent.bottom
        }

        // Pass backend explicitly
        trackerBackend: backend

        // Controlled by F5 hotkey
        collapsed: !backend.trackerVisible
    }

    // Collectible tooltip
    CollectibleTooltip {
        id: collectibleTooltip

        // Update interactive regions when tooltip visibility changes
        onVisibleChanged: {
            updateInteractiveRegions()
        }
    }

    // Video player window (loaded on demand)
    Loader {
        id: videoPlayerLoader
        active: false
        source: "VideoPlayer.qml"

        // Store pending video request
        property string pendingUrl: ""
        property string pendingName: ""

        onLoaded: {
            console.log("[Overlay] VideoPlayer loaded")

            // If there's a pending video request, show it now
            if (pendingUrl !== "") {
                console.log("[Overlay] Showing pending video:", pendingUrl, pendingName)
                item.show(pendingUrl, pendingName)
                pendingUrl = ""
                pendingName = ""
            }
        }
    }

    // Connect backend signal to video player
    Connections {
        target: backend
        function onVideoRequested(url, name) {
            console.log("[Overlay] Video requested:", url, name)

            // If loader is already active and loaded, show immediately
            if (videoPlayerLoader.active && videoPlayerLoader.item) {
                console.log("[Overlay] VideoPlayer already loaded, showing video")
                videoPlayerLoader.item.show(url, name)
            } else {
                // Loader not active or not loaded yet - activate and queue the request
                console.log("[Overlay] Loading VideoPlayer...")
                videoPlayerLoader.pendingUrl = url
                videoPlayerLoader.pendingName = name
                videoPlayerLoader.active = true
            }
        }
    }

    // Connect click-through signals from backend
    Connections {
        target: backend
        function onClickThroughDisableRequested() {
            clickThroughManager.setClickThrough(false)
        }
        function onClickThroughEnableRequested() {
            clickThroughManager.setClickThrough(true)
        }
    }

    // Cursor polling timer for tooltip hover detection
    Timer {
        id: cursorPollTimer
        interval: 16  // ~60 FPS
        running: backend.overlayVisible
        repeat: true

        property var currentHovered: null

        onTriggered: {
            var cursorPos = backend.get_cursor_pos()
            if (!cursorPos) return

            // Check if cursor is over UI elements (skip collectible hover if so)
            var overTooltip = collectibleTooltip.visible &&
                              cursorPos.x >= collectibleTooltip.x &&
                              cursorPos.x < collectibleTooltip.x + collectibleTooltip.width &&
                              cursorPos.y >= collectibleTooltip.y &&
                              cursorPos.y < collectibleTooltip.y + collectibleTooltip.height

            var overTracker = backend.trackerVisible &&
                              cursorPos.x >= 0 && cursorPos.x < tracker.width

            if (overTooltip || overTracker) {
                if (overTracker && currentHovered) {
                    currentHovered = null
                    collectibleTooltip.hideWithDelay()
                }
                return
            }

            // Hit-test collectibles at cursor position
            var hoveredItem = findCollectibleAt(cursorPos.x, cursorPos.y)

            if (hoveredItem !== currentHovered) {
                if (hoveredItem) {
                    currentHovered = hoveredItem
                    collectibleTooltip.collectible = hoveredItem
                    collectibleTooltip.showNear(hoveredItem.x, hoveredItem.y)
                    collectibleTooltip.cancelHide()
                } else {
                    currentHovered = null
                    collectibleTooltip.hideWithDelay()
                }
            }
        }
    }

    // Global mouse click handler (from backend via pynput)
    Connections {
        target: backend

        function onMouseClicked(x, y, button) {
            // Iterate through interactive components (in priority order)
            for (var i = 0; i < interactiveComponents.length; i++) {
                var component = interactiveComponents[i]
                if (component.handleClick && component.handleClick(x, y, button)) {
                    return
                }
            }

            // No component handled the click - check collectibles
            if (button === "right") {
                // Hit-test collectibles at cursor position
                var collectible = findCollectibleAt(x, y)
                if (collectible) {
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
