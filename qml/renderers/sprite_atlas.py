"""
Sprite texture management for collectible overlay.

Handles SVG loading, GPU texture upload, and caching for all sprite types.
"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from typing import Dict, Optional


class SpriteAtlas:
    """
    Manages sprite textures for collectible rendering.

    Handles:
    - SVG loading and rasterization (48x48 sprites)
    - CPU-side image caching
    - GPU texture upload and caching
    - Collected state rendering (50% opacity)

    Thread safety: Must be created and used on Qt render thread only.
    QPainter and QSGTexture are NOT thread-safe.
    """

    SPRITE_TYPES = [
        'arrowhead', 'bottle', 'coin', 'egg', 'flower',
        'tarot', 'jewelry', 'heirloom', 'fossil', 'random'
    ]

    SPRITE_SIZE = 48  # 48x48 pixel sprites

    def __init__(self):
        """Initialize empty texture caches."""
        # GPU textures: "type_state" -> QSGTexture
        self._gpu_textures: Dict[str, any] = {}

        # CPU images: "type_state" -> QImage (for faster re-upload if needed)
        self._cpu_images: Dict[str, QImage] = {}

    def get_texture(self, window, sprite_type: str, collected: bool):
        """
        Get or create GPU texture for sprite.

        Args:
            window: QQuickWindow for texture creation
            sprite_type: Collectible type ('coin', 'flower', etc.)
            collected: True for 50% opacity, False for full opacity

        Returns:
            QSGTexture or None if creation failed
        """
        cache_key = f"{sprite_type}_{'collected' if collected else 'normal'}"

        # Return cached texture if available
        if cache_key in self._gpu_textures:
            return self._gpu_textures[cache_key]

        # Create new sprite image
        sprite_image = self._create_sprite_image(sprite_type, collected)

        # Upload to GPU
        try:
            texture = window.createTextureFromImage(sprite_image)
            if texture:
                self._gpu_textures[cache_key] = texture
                print(f"[SpriteAtlas] Created texture: {cache_key}")
                return texture
            else:
                print(f"[SpriteAtlas] ERROR: Failed to create texture for {cache_key}")
                return None
        except Exception as e:
            print(f"[SpriteAtlas] ERROR: Exception creating texture: {e}")
            return None

    def _create_sprite_image(self, sprite_type: str, collected: bool) -> QImage:
        """
        Create sprite image from SVG.

        Args:
            sprite_type: Collectible type
            collected: True for dimmed (50% opacity)

        Returns:
            QImage with rendered sprite
        """
        cache_key = f"{sprite_type}_{'collected' if collected else 'normal'}"

        # Return cached image if available
        if cache_key in self._cpu_images:
            return self._cpu_images[cache_key]

        # Create transparent 48x48 image
        sprite_image = QImage(
            self.SPRITE_SIZE,
            self.SPRITE_SIZE,
            QImage.Format.Format_ARGB32_Premultiplied
        )
        sprite_image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(sprite_image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Load SVG
        from qml.svg_icons import get_icon_svg
        svg_data = get_icon_svg(sprite_type)
        svg_renderer = QSvgRenderer()
        svg_renderer.load(svg_data.encode('utf-8'))

        if svg_renderer.isValid():
            # Apply opacity for collected state
            if collected:
                painter.setOpacity(0.5)
            svg_renderer.render(painter, QRectF(0, 0, self.SPRITE_SIZE, self.SPRITE_SIZE))
        else:
            # Fallback: colored circle
            painter.setBrush(QColor(255, 255, 0, 128 if collected else 255))
            painter.drawEllipse(4, 4, 40, 40)

        painter.end()

        # Cache the image
        self._cpu_images[cache_key] = sprite_image
        return sprite_image

    def clear_cache(self):
        """Clear all cached textures and images."""
        self._gpu_textures.clear()
        self._cpu_images.clear()
