"""
Test QSGSimpleTextureNode with TRANSPARENT overlay window.
This demonstrates rendering sprites on a see-through window for overlays.
"""

import sys
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor
from PySide6.QtQuick import QQuickItem, QSGSimpleTextureNode
from PySide6.QtQml import qmlRegisterType, QQmlApplicationEngine
from PySide6.QtCore import QUrl
from PySide6.QtSvg import QSvgRenderer


class TexturedSpriteItem(QQuickItem):
    """Render a textured sprite using QSGSimpleTextureNode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)

        self._texture = None
        self._node = None
        self._sprite_image = None

        print("[TextureTest] Item created")

    def _create_sprite_texture(self):
        """Create sprite texture from SVG."""
        if self._texture is not None:
            return

        print("[TextureTest] Creating sprite texture...")

        # Create 48x48 sprite image
        sprite_size = 48
        sprite_image = QImage(sprite_size, sprite_size, QImage.Format.Format_ARGB32_Premultiplied)
        sprite_image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(sprite_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Load arrowhead SVG
        from qml.svg_icons import get_icon_svg
        svg_data = get_icon_svg('arrowhead')
        svg_renderer = QSvgRenderer()
        svg_renderer.load(svg_data.encode('utf-8'))

        if svg_renderer.isValid():
            svg_renderer.render(painter, QRectF(0, 0, sprite_size, sprite_size))
            print("[TextureTest] Rendered arrowhead SVG to image")
        else:
            # Fallback: draw a circle
            painter.setBrush(QColor(255, 255, 0, 255))  # Yellow
            painter.drawEllipse(4, 4, 40, 40)
            print("[TextureTest] SVG failed, using yellow circle")

        painter.end()

        # Store image (will upload to GPU in updatePaintNode)
        self._sprite_image = sprite_image
        print("[TextureTest] Sprite texture created")

    def updatePaintNode(self, old_node, update_data):
        """Render sprite using QSGSimpleTextureNode."""

        if self.width() == 0 or self.height() == 0:
            return old_node

        # Create sprite texture on first render
        if self._sprite_image is None:
            self._create_sprite_texture()

        if old_node is not None:
            return old_node

        print(f"[TextureTest] Creating QSGSimpleTextureNode (size: {self.width()}x{self.height()})")

        # Upload texture to GPU
        if not self.window():
            print("[TextureTest] ERROR: No window")
            return None

        try:
            self._texture = self.window().createTextureFromImage(self._sprite_image)
            if not self._texture:
                print("[TextureTest] ERROR: Texture creation failed")
                return None
            print("[TextureTest] Texture uploaded to GPU")
        except Exception as e:
            print(f"[TextureTest] ERROR: {e}")
            return None

        # Create texture node
        node = QSGSimpleTextureNode()
        node.setTexture(self._texture)

        # Draw sprite in CENTER of screen (200x200 size)
        center_x = self.width() / 2
        center_y = self.height() / 2
        sprite_size = 200

        rect = QRectF(
            center_x - sprite_size / 2,
            center_y - sprite_size / 2,
            sprite_size,
            sprite_size
        )
        node.setRect(rect)

        # Enable texture filtering for smooth scaling
        from PySide6.QtQuick import QSGTexture
        node.setFiltering(QSGTexture.Linear)

        print(f"[TextureTest] Sprite node created at {rect}")

        self._node = node
        return node


def main():
    app = QGuiApplication(sys.argv)

    qmlRegisterType(TexturedSpriteItem, "TestModule", 1, 0, "TexturedSpriteItem")

    engine = QQmlApplicationEngine()

    def on_warnings(warnings):
        for warning in warnings:
            print(f"[QML WARNING] {warning.toString()}")

    engine.warnings.connect(on_warnings)

    qml_code = """
import QtQuick 2.15
import QtQuick.Window 2.15
import TestModule 1.0

Window {
    visible: true
    width: 800
    height: 600
    title: "Transparent Overlay Test - Sprite Rendering"
    
    // CRITICAL: Enable window transparency
    color: "transparent"
    
    // CRITICAL: Set window flags for overlay behavior
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    
    // Optional: Make window click-through (events pass to windows below)
    // Uncomment if you want a true overlay that doesn't intercept clicks
    // flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput

    // Semi-transparent background rectangle for debugging
    // This shows where the window is - remove for production overlay
    Rectangle {
        anchors.fill: parent
        color: "#40000000"  // 25% black for debugging
        border.color: "red"
        border.width: 2
        
        Text {
            x: 10
            y: 10
            text: "Transparent Overlay Test\\nLook for sprite in center"
            color: "white"
            font.pixelSize: 14
            style: Text.Outline
            styleColor: "black"
        }
    }

    // The actual sprite renderer
    TexturedSpriteItem {
        anchors.fill: parent
    }
}
"""

    engine.loadData(qml_code.encode('utf-8'), QUrl())

    if not engine.rootObjects():
        print("[TextureTest] ERROR: Failed to load QML")
        return -1

    print("[TextureTest] Transparent overlay window shown")
    print("[TextureTest] Window should be see-through with sprite in center")

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())