"""
Pure QPainter collectible renderer - No QML property overhead.

Simpler than QQuickFramebufferObject:
- Direct QPainter rendering
- No FBO complexity
- Same sprite caching strategy
- Zero QML bindings
"""

from PySide6.QtCore import Qt, QRectF, QByteArray, QPointF
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from qml.svg_icons import get_icon_svg, get_icon_name
import time
from typing import List, Dict


class CollectibleRendererPainted(QQuickPaintedItem):
    """
    Pure QPainter renderer for collectibles.

    Usage in QML:
        CollectibleRendererPainted {
            anchors.fill: parent
        }

    Then call from Python:
        renderer.render_frame(collectibles, viewport_x, viewport_y, scale, opacity)
    """

    SPRITE_TYPES = [
        'arrowhead', 'bottle', 'coin', 'egg', 'flower',
        'tarot', 'jewelry', 'heirloom', 'fossil', 'random'
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        # Enable antialiasing
        self.setAntialiasing(True)

        # ALL collectibles with map coordinates (set once by backend)
        # Format: [{map_x, map_y, type, collected}, ...]
        self._all_collectibles = []

        # Viewport data (updated every frame from backend)
        self._viewport_x = 0.0
        self._viewport_y = 0.0
        self._viewport_width = 1920.0
        self._viewport_height = 1080.0

        # Sprite cache (pre-rendered)
        self.sprite_cache = {}
        self.cache_initialized = False

        # FPS tracking
        self.frame_times = []
        self.last_fps_log = time.time()

        print("[Painted Renderer] Initialized")

    def set_collectibles(self, collectibles: List[Dict]):
        """
        Set ALL collectibles with map coordinates (detection space).
        Called once on init, or when collection tracker filter changes.

        Args:
            collectibles: List with map_x, map_y, type, collected
        """
        self._all_collectibles = collectibles
        print(f"[Painted Renderer] Loaded {len(collectibles)} collectibles")
        if len(collectibles) > 0:
            sample = collectibles[0]
            print(f"[Painted Renderer] Sample collectible: {sample}")

    def set_viewport(self, x: float, y: float, width: float, height: float):
        """
        Update viewport transform (detection space).
        Called every frame from backend.

        Single transform applied to entire scene:
        screen_x = (map_x - viewport_x) * (1920 / viewport_width)
        screen_y = (map_y - viewport_y) * (1080 / viewport_height)
        """
        self._viewport_x = x
        self._viewport_y = y
        self._viewport_width = width
        self._viewport_height = height

    def render_frame(self):
        """
        Trigger repaint with current viewport transform.
        Called at 60 FPS by QML Timer.
        """
        self.update()  # Trigger paint()

    def paint(self, painter: QPainter):
        """Main paint - called by Qt when update() is requested"""
        paint_start = time.time()

        # Initialize sprite cache on first paint
        if not self.cache_initialized:
            print("[Painted Renderer] Initializing sprite cache...")
            try:
                self._init_sprite_cache()
                self.cache_initialized = True
                print("[Painted Renderer] Sprite cache initialized successfully")
            except Exception as e:
                print(f"[Painted Renderer ERROR] Failed to initialize sprite cache: {e}")
                import traceback
                traceback.print_exc()
                return

        # Track FPS
        now = time.time()
        self.frame_times.append(now)
        if now - self.last_fps_log >= 1.0:
            cutoff = now - 1.0
            self.frame_times = [t for t in self.frame_times if t > cutoff]
            fps = len(self.frame_times)
            if fps > 0:
                print(f"[Painted Renderer] FPS: {fps}, Total collectibles: {len(self._all_collectibles)}")
            self.last_fps_log = now

        # Clear to transparent
        clear_start = time.time()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(0, 0, int(self.width()), int(self.height()), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        clear_time = (time.time() - clear_start) * 1000

        # Render all sprites (panel is opaque, collected items have 50% opacity in atlas)
        render_start = time.time()
        visible_count = self._render_sprites(painter)
        render_time = (time.time() - render_start) * 1000

        # Total paint time
        paint_time = (time.time() - paint_start) * 1000

        # Log detailed timing once per second
        if now - self.last_fps_log >= 1.0:
            print(f"[Painted Renderer] Paint: {paint_time:.1f}ms (clear: {clear_time:.1f}ms, render: {render_time:.1f}ms, drawn: {visible_count}/{len(self._all_collectibles)})")
            print(f"[Painted Renderer] Viewport: x={self._viewport_x:.1f}, y={self._viewport_y:.1f}, w={self._viewport_width:.1f}, h={self._viewport_height:.1f}")

    def _init_sprite_cache(self):
        """Pre-render all sprite types to pixmaps and create texture atlas"""
        print("[Painted Renderer] Pre-rendering sprite cache...")

        sprite_size = 48
        num_sprites = len(self.SPRITE_TYPES) * 2  # normal + collected states

        # Create texture atlas (all sprites in one image for faster batch drawing)
        # Layout: horizontal strip (easier to index)
        atlas_width = sprite_size * num_sprites
        atlas_height = sprite_size

        self.sprite_atlas = QImage(atlas_width, atlas_height, QImage.Format.Format_ARGB32_Premultiplied)
        self.sprite_atlas.fill(Qt.GlobalColor.transparent)

        atlas_painter = QPainter(self.sprite_atlas)
        atlas_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        atlas_x = 0

        for sprite_type in self.SPRITE_TYPES:
            svg_data = get_icon_svg(sprite_type)
            svg_renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))

            if svg_renderer.isValid():
                # Normal state
                svg_renderer.render(atlas_painter, QRectF(atlas_x, 0, sprite_size, sprite_size))
                self.sprite_cache[f'{sprite_type}_normal'] = QRectF(atlas_x, 0, sprite_size, sprite_size)
                atlas_x += sprite_size

                # Collected state (50% opacity)
                atlas_painter.setOpacity(0.5)
                svg_renderer.render(atlas_painter, QRectF(atlas_x, 0, sprite_size, sprite_size))
                atlas_painter.setOpacity(1.0)
                self.sprite_cache[f'{sprite_type}_collected'] = QRectF(atlas_x, 0, sprite_size, sprite_size)
                atlas_x += sprite_size

        atlas_painter.end()
        print(f"[Painted Renderer] Created texture atlas: {atlas_width}x{atlas_height} ({len(self.SPRITE_TYPES)} types)")

    def _render_sprites(self, painter: QPainter):
        """
        Transform ALL collectibles using viewport and render.
        NO CULLING - render everything for debugging.
        """
        if not self._all_collectibles:
            return 0

        if self._viewport_width == 0:
            return 0

        # Calculate scale factors (same for all collectibles)
        scale_x = 1920.0 / self._viewport_width
        scale_y = 1080.0 / self._viewport_height

        # Group sprites by type for batching
        sprite_batches = {}
        transformed_count = 0

        for col in self._all_collectibles:
            # Get map coordinates (detection space)
            map_x = col.get('map_x', 0)
            map_y = col.get('map_y', 0)

            # Apply transform: screen = (map - viewport) * scale
            screen_x = (map_x - self._viewport_x) * scale_x
            screen_y = (map_y - self._viewport_y) * scale_y

            # NO CULLING - draw everything
            transformed_count += 1

            col_type = col.get('type', 'random')
            is_collected = col.get('collected', False)

            # Center sprite (48x48)
            draw_x = screen_x - 24
            draw_y = screen_y - 24

            # Determine cache key
            icon_name = get_icon_name(col_type)
            cache_key = f'{icon_name}_{"collected" if is_collected else "normal"}'
            if cache_key not in self.sprite_cache:
                cache_key = f'random_{"collected" if is_collected else "normal"}'

            # Add to batch
            if cache_key not in sprite_batches:
                sprite_batches[cache_key] = []
            sprite_batches[cache_key].append((draw_x, draw_y))

        # Draw each batch (using texture atlas for faster rendering)
        total_drawn = 0
        for cache_key, positions in sprite_batches.items():
            sprite_rect = self.sprite_cache.get(cache_key)
            if sprite_rect and hasattr(self, 'sprite_atlas'):
                # Draw from atlas: source rect -> destination positions
                for draw_x, draw_y in positions:
                    painter.drawImage(
                        QRectF(draw_x, draw_y, 48, 48),  # Destination rect
                        self.sprite_atlas,  # Source image (atlas)
                        sprite_rect  # Source rect within atlas
                    )
                    total_drawn += 1

        return total_drawn  # Return count of sprites actually drawn
