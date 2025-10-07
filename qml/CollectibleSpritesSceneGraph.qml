import QtQuick 2.15
import RDOOverlay 1.0

/*
 * SceneGraph Collectible Sprites Renderer
 *
 * Hardware-accelerated GPU rendering using Qt Quick Scene Graph.
 * Python backend (CollectibleRendererSceneGraph.py) handles all rendering logic.
 *
 * Advantages over QPainter:
 * - GPU-accelerated (OpenGL/Vulkan/Metal)
 * - Batched rendering (single draw call per texture)
 * - Scales to thousands of sprites at 60+ FPS
 */

CollectibleRendererSceneGraph {
    id: root
    objectName: "spritesSceneGraph"  // Required for findChild() in app_qml.py

    // Fill parent window
    anchors.fill: parent

    // Always behind other UI elements
    z: 0

    // Backend updates collectibles data, frontend renders at its own rate
    // This decouples backend matching from frontend rendering

    // Continuous render timer - runs at 60 FPS independent of backend
    Timer {
        interval: 16  // 60 FPS
        running: true
        repeat: true
        onTriggered: root.update()  // Request Scene Graph rebuild
    }

    Component.onCompleted: {
        console.log("[CollectibleSpritesSceneGraph] GPU renderer ready with 60 FPS timer, size:", width, "x", height)
    }
}
