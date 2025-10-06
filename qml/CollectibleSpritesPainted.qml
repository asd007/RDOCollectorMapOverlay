import QtQuick 2.15
import RDOOverlay 1.0

/*
 * Pure QPainter collectible renderer - simpler than GL approach.
 *
 * Architecture:
 * - No property bindings
 * - Direct render calls from Python
 * - Pre-cached sprites
 * - Simple culling
 * - QPainter rendering (no FBO complexity)
 */

CollectibleRendererPainted {
    id: renderer
    objectName: "sprites"  // For Python findChild()
    anchors.fill: parent

    // Backend updates collectibles data, frontend renders at its own rate
    // This decouples backend matching from frontend rendering

    // Continuous render timer - runs at 60 FPS independent of backend
    Timer {
        interval: 16  // 60 FPS
        running: true
        repeat: true
        onTriggered: renderer.update()  // Request repaint
    }

    Component.onCompleted: {
        console.log("[CollectibleSpritesPainted] Pure QPainter renderer ready with 60 FPS timer, size:", width, "x", height)
    }
}
