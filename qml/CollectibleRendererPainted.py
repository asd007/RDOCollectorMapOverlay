"""
Hardware-accelerated collectible renderer using QQuickPaintedItem + QPainter.

QPainter content is automatically uploaded to GPU texture by Qt, giving good performance
while maintaining compatibility with transparent windows.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtGui import QPainter, QPixmap, QImage
from typing import List, Dict

from qml.renderers import SpriteAtlas


class CollectibleRendererPainted(QQuickPaintedItem):
    """
    QPainter-based renderer for collectible sprites.

    Advantages:
    - Works with transparent windows (proven)
    - Hardware-accelerated via texture caching
    - Can batch render hundreds of sprites at 60fps
    - Simple, reliable implementation

    Usage in QML:
        CollectibleRendererPainted {
            anchors.fill: parent
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Disable antialiasing for performance (pre-rendered sprites don't need it)
        self.setAntialiasing(False)

        # Render to OpenGL framebuffer for best performance
        self.setRenderTarget(QQuickPaintedItem.RenderTarget.FramebufferObject)

        # Performance hint: content doesn't change size/shape
        self.setPerformanceHint(QQuickPaintedItem.PerformanceHint.FastFBOResizing, True)

        # ALL collectibles with map coordinates (set once by backend)
        # Format: [{map_x, map_y, type, collected}, ...]
        self._all_collectibles = []

        # Viewport data (updated every frame from backend)
        self._viewport_x = 0.0
        self._viewport_y = 0.0
        self._viewport_width = 1920.0
        self._viewport_height = 1080.0
        self._viewport_valid = False

        # Dirty tracking (only repaint when viewport changes)
        self._last_viewport_x = None
        self._last_viewport_y = None
        self._last_viewport_width = None
        self._last_viewport_height = None

        # Sprite pixmap cache (faster than creating from SVG each frame)
        self._sprite_pixmaps: Dict[str, QPixmap] = {}

        # Debug
        print(f"[PaintedRenderer] Initialized (size: {self.width()}x{self.height()})")

    def set_collectibles(self, collectibles: List[Dict]):
        """
        Set all collectibles with map coordinates (detection space).

        Called on init and when collection tracker filter changes.

        Args:
            collectibles: List of dicts with keys: map_x, map_y, type, collected
        """
        self._all_collectibles = collectibles
        print(f"[PaintedRenderer] Set {len(collectibles)} collectibles")
        self.update()  # Trigger repaint

    def set_viewport(self, x: float, y: float, width: float, height: float):
        """
        Update viewport bounds (detection space coordinates).

        Called whenever backend updates (variable rate from AKAZE matching).
        Timer handles 60fps repaints independently.

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
        # Note: No update() call needed - timer triggers repaints at 60fps

    def _get_sprite_pixmap(self, sprite_type: str, collected: bool) -> QPixmap:
        """Get cached sprite pixmap, creating if needed."""
        cache_key = f"{sprite_type}_{'collected' if collected else 'normal'}"

        if cache_key in self._sprite_pixmaps:
            return self._sprite_pixmaps[cache_key]

        # Create sprite image
        from qml.svg_icons import get_icon_svg
        from PySide6.QtSvg import QSvgRenderer

        sprite_image = QImage(48, 48, QImage.Format.Format_ARGB32_Premultiplied)
        sprite_image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(sprite_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        svg_data = get_icon_svg(sprite_type)
        svg_renderer = QSvgRenderer()
        svg_renderer.load(svg_data.encode('utf-8'))

        if svg_renderer.isValid():
            if collected:
                painter.setOpacity(0.5)
            svg_renderer.render(painter, QRectF(0, 0, 48, 48))

        painter.end()

        # Convert to pixmap and cache
        pixmap = QPixmap.fromImage(sprite_image)
        self._sprite_pixmaps[cache_key] = pixmap

        return pixmap

    def paint(self, painter: QPainter):
        """
        Render all collectible sprites using QPainter.

        Called by timer at 30fps. Always paints (no frame skipping).
        """
        if not self._viewport_valid:
            return

        if len(self._all_collectibles) == 0:
            return

        # Calculate viewport transform (detection space -> screen space)
        scale_x = 1920.0 / self._viewport_width
        scale_y = 1080.0 / self._viewport_height

        # OPTIMIZATION: Viewport culling - only render sprites within viewport bounds
        # Skip sprites outside detection space viewport (they won't be visible anyway)
        sprites_rendered = 0
        for collectible in self._all_collectibles:
            map_x = collectible.get('map_x', 0)
            map_y = collectible.get('map_y', 0)

            # Viewport culling: skip if outside viewport bounds (detection space)
            if not (self._viewport_x <= map_x <= self._viewport_x + self._viewport_width and
                    self._viewport_y <= map_y <= self._viewport_y + self._viewport_height):
                continue  # Skip offscreen sprites

            sprite_type = collectible.get('type', 'random')
            collected = collectible.get('collected', False)

            # Transform to screen coordinates
            screen_x = (map_x - self._viewport_x) * scale_x
            screen_y = (map_y - self._viewport_y) * scale_y

            # Screen culling: additional safety check (skip if way offscreen)
            if screen_x < -100 or screen_x > 2020 or screen_y < -100 or screen_y > 1180:
                continue

            # Get sprite pixmap (cached)
            pixmap = self._get_sprite_pixmap(sprite_type, collected)

            # Draw sprite (48x48 centered on screen coordinates)
            target_rect = QRectF(screen_x - 24, screen_y - 24, 48, 48)
            painter.drawPixmap(target_rect, pixmap, QRectF(pixmap.rect()))

            sprites_rendered += 1

        # Note: Qt automatically uploads this to GPU texture
        # Subsequent frames reuse the texture if content unchanged
