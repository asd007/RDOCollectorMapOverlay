"""
Hardware-accelerated collectible renderer using Qt Quick Scene Graph.

Uses QSGGeometry for batched GPU rendering - orders of magnitude faster than QPainter.
All sprite rendering happens on GPU with a single draw call per texture.
"""

from PySide6.QtCore import QRectF
from PySide6.QtQuick import QQuickItem, QSGSimpleTextureNode, QSGTexture, QSGNode
from typing import List, Dict

from qml.renderers import SpriteAtlas


class CollectibleRendererSceneGraph(QQuickItem):
    """
    Hardware-accelerated renderer using Qt Quick Scene Graph.

    Advantages over QPainter:
    - GPU-accelerated (uses OpenGL/Vulkan/Metal depending on platform)
    - Batched rendering (single draw call per texture)
    - Automatic vsync and double buffering
    - Scales to thousands of sprites effortlessly

    Usage in QML:
        CollectibleRendererSceneGraph {
            anchors.fill: parent
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Enable scene graph rendering
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)

        # ALL collectibles with map coordinates (set once by backend)
        # Format: [{map_x, map_y, type, collected}, ...]
        self._all_collectibles = []

        # Viewport data (updated every frame from backend)
        self._viewport_x = 0.0
        self._viewport_y = 0.0
        self._viewport_width = 1920.0
        self._viewport_height = 1080.0
        self._viewport_valid = False  # Only render after first viewport update

        # Sprite texture manager
        self._sprite_atlas = SpriteAtlas()

        # Scene graph root node
        self.root_node = None

    def set_collectibles(self, collectibles: List[Dict]):
        """
        Set all collectibles with map coordinates (detection space).

        Called on init and when collection tracker filter changes.

        Args:
            collectibles: List of dicts with keys: map_x, map_y, type, collected
        """
        self._all_collectibles = collectibles
        self.update()  # Trigger updatePaintNode() on render thread

    def set_viewport(self, x: float, y: float, width: float, height: float):
        """
        Update viewport bounds (detection space coordinates).

        Called every frame after AKAZE matching.

        Args:
            x: Left edge of viewport in detection space
            y: Top edge of viewport in detection space
            width: Viewport width in detection space
            height: Viewport height in detection space
        """
        self._viewport_x = x
        self._viewport_y = y
        self._viewport_width = width
        self._viewport_height = height
        self._viewport_valid = True
        self.update()  # Trigger updatePaintNode() on render thread


    def updatePaintNode(self, old_node, update_data):
        """
        Build/update Scene Graph using individual QSGSimpleTextureNode for each sprite.
        Each sprite is a separate GPU quad - Qt handles batching and optimization.
        """
        # Safety: Skip if item has zero size
        if self.width() == 0 or self.height() == 0:
            return old_node

        # Safety: Need valid window for texture creation
        if not self.window():
            return old_node

        # Don't render until we have a valid viewport from AKAZE match
        if not self._viewport_valid:
            return old_node

        # Create root node on first frame
        if old_node is None:
            self.root_node = QSGNode()
        else:
            self.root_node = old_node
            # Clear all children to rebuild scene
            while self.root_node.childCount() > 0:
                child = self.root_node.firstChild()
                self.root_node.removeChildNode(child)

        # Calculate viewport transform (detection space -> screen space)
        scale_x = 1920.0 / self._viewport_width
        scale_y = 1080.0 / self._viewport_height

        # Render all collectibles (no viewport culling - GPU handles offscreen efficiently)
        for collectible in self._all_collectibles:
            map_x = collectible.get('map_x', 0)
            map_y = collectible.get('map_y', 0)
            sprite_type = collectible.get('type', 'random')
            collected = collectible.get('collected', False)

            # Transform to screen coordinates
            screen_x = (map_x - self._viewport_x) * scale_x
            screen_y = (map_y - self._viewport_y) * scale_y

            # Get or create sprite texture via atlas
            texture = self._sprite_atlas.get_texture(self.window(), sprite_type, collected)
            if not texture:
                continue

            # Create texture node for sprite
            sprite_node = QSGSimpleTextureNode()
            sprite_node.setTexture(texture)
            sprite_node.setFiltering(QSGTexture.Linear)

            # Position sprite (48x48 centered on screen coordinates)
            sprite_rect = QRectF(screen_x - 24, screen_y - 24, 48, 48)
            sprite_node.setRect(sprite_rect)

            # Add to scene (Qt handles ownership automatically)
            self.root_node.appendChildNode(sprite_node)

        return self.root_node
