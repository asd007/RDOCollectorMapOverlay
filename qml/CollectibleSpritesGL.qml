import QtQuick 2.15
import RDOOverlay 1.0

/*
 * Pure OpenGL collectible renderer - no QML overhead.
 *
 * Architecture:
 * - No property bindings
 * - Direct render calls from Python
 * - Pre-cached sprites
 * - Simple culling
 * - OpenGL FBO rendering with QPainter
 */

CollectibleRendererGL {
    id: renderer
    objectName: "sprites"  // For Python findChild()
    anchors.fill: parent

    // CRITICAL: Must be visible and have size for Qt to call render()
    visible: true
    width: parent.width
    height: parent.height

    // No properties! Backend calls renderer.render_frame() directly from Python
    // This eliminates ALL QML binding overhead

    Component.onCompleted: {
        console.log("[CollectibleSpritesGL] Pure GL renderer ready, size:", width, "x", height)
    }
}
