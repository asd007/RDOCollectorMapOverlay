import QtQuick 2.15
import RDOOverlay 1.0

/*
 * QPainter Collectible Sprites Renderer
 *
 * Hardware-accelerated GPU rendering using QQuickPaintedItem + QPainter.
 * Python backend (CollectibleRendererPainted.py) handles all rendering logic.
 *
 * Advantages:
 * - GPU-accelerated (QPainter content cached to texture)
 * - Works with transparent windows (proven)
 * - Can render hundreds of sprites at 60 FPS
 */

CollectibleRendererPainted {
    id: root
    objectName: "spritesSceneGraph"  // Required for findChild() in app_qml.py

    // Explicit fullscreen size
    width: 1920
    height: 1080
    x: 0
    y: 0

    // Always behind other UI elements
    z: 0

    // Backend updates viewport at variable rate, frontend renders at 30 FPS
    // Dirty tracking skips painting when viewport unchanged (major performance boost)
    Timer {
        interval: 33  // 30 FPS (good balance of smoothness vs performance)
        running: true
        repeat: true
        onTriggered: root.update()  // Request QPainter repaint
    }

    Component.onCompleted: {
        console.log("[CollectibleRendererPainted] QPainter renderer ready (30 FPS rendering), size:", width, "x", height)
    }
}
