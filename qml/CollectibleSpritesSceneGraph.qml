import QtQuick 2.15
import RDOOverlay 1.0

/*
 * QML wrapper for hardware-accelerated Scene Graph renderer
 */

CollectibleRendererSceneGraph {
    id: renderer
    objectName: "sprites"  // For Python findChild()

    Component.onCompleted: {
        console.log("[CollectibleSpritesSceneGraph] GPU-accelerated renderer ready, size:", width, "x", height)
    }
}
