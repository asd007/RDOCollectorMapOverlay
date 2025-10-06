"""
Hardware-accelerated collectible renderer using Qt Quick Scene Graph.

Uses QSGGeometry for batched GPU rendering - orders of magnitude faster than QPainter.
All sprite rendering happens on GPU with a single draw call per texture.
"""

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtQuick import QQuickItem, QSGGeometryNode, QSGGeometry, QSGFlatColorMaterial, QSGTexture, QSGTextureMaterial
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from typing import List, Dict
import time


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

    SPRITE_TYPES = [
        'arrowhead', 'bottle', 'coin', 'egg', 'flower',
        'tarot', 'jewelry', 'heirloom', 'fossil', 'random'
    ]

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

        # Sprite atlas (will be uploaded to GPU as texture)
        self.sprite_atlas = None
        self.sprite_rects = {}  # Map sprite type -> texture coordinates
        self.atlas_texture = None  # QSGTexture (GPU-side)

        # Performance tracking
        self.frame_times = []
        self.last_fps_log = time.time()

        print("[SceneGraph Renderer] Initialized (GPU-accelerated)")

    def set_collectibles(self, collectibles: List[Dict]):
        """
        Set ALL collectibles with map coordinates (detection space).
        Called once on init, or when collection tracker filter changes.

        Args:
            collectibles: List with map_x, map_y, type, collected
        """
        self._all_collectibles = collectibles
        print(f"[SceneGraph Renderer] Loaded {len(collectibles)} collectibles")
        if len(collectibles) > 0:
            sample = collectibles[0]
            print(f"[SceneGraph Renderer] Sample collectible: {sample}")
        self.update()  # Trigger updatePaintNode()

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
        self.update()  # Trigger updatePaintNode()

    def _init_sprite_atlas(self):
        """Create sprite atlas and upload to GPU"""
        if self.sprite_atlas is not None:
            return  # Already initialized

        print("[SceneGraph Renderer] Creating sprite atlas...")

        sprite_size = 48
        num_sprites = len(self.SPRITE_TYPES) * 2  # normal + collected

        # Create atlas image
        atlas_width = sprite_size * num_sprites
        atlas_height = sprite_size

        self.sprite_atlas = QImage(atlas_width, atlas_height, QImage.Format.Format_ARGB32_Premultiplied)
        self.sprite_atlas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(self.sprite_atlas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        atlas_x = 0

        # Import SVG icon getter
        from qml.svg_icons import get_icon_svg

        for sprite_type in self.SPRITE_TYPES:
            svg_data = get_icon_svg(sprite_type)
            svg_renderer = QSvgRenderer()
            svg_renderer.load(svg_data.encode('utf-8'))

            if svg_renderer.isValid():
                # Normal state
                svg_renderer.render(painter, QRectF(atlas_x, 0, sprite_size, sprite_size))
                # Store UV coordinates (normalized 0-1 for GPU)
                self.sprite_rects[f'{sprite_type}_normal'] = QRectF(
                    atlas_x / atlas_width,
                    0,
                    sprite_size / atlas_width,
                    sprite_size / atlas_height
                )
                atlas_x += sprite_size

                # Collected state (50% opacity)
                painter.setOpacity(0.5)
                svg_renderer.render(painter, QRectF(atlas_x, 0, sprite_size, sprite_size))
                painter.setOpacity(1.0)
                self.sprite_rects[f'{sprite_type}_collected'] = QRectF(
                    atlas_x / atlas_width,
                    0,
                    sprite_size / atlas_width,
                    sprite_size / atlas_height
                )
                atlas_x += sprite_size

        painter.end()
        print(f"[SceneGraph Renderer] Atlas created: {atlas_width}x{atlas_height}")

    def updatePaintNode(self, old_node, update_data):
        """
        Called by Qt Scene Graph to build/update GPU rendering commands.
        This is where the magic happens - we build batched geometry for GPU.

        IMPORTANT: No frame clearing needed! Scene Graph only renders sprite triangles.
        GPU blends sprites on transparent background - much faster than clearing entire frame.
        """
        frame_start = time.time()

        # Initialize atlas on first render
        if self.sprite_atlas is None:
            self._init_sprite_atlas()

        # Create or reuse geometry node
        if old_node is None:
            node = QSGGeometryNode()

            # Create texture from atlas (uploads to GPU)
            if self.atlas_texture is None and self.window():
                self.atlas_texture = self.window().createTextureFromImage(self.sprite_atlas)

            # Create geometry for batched rendering
            # We'll use textured quads (2 triangles per sprite)
            geometry = QSGGeometry(QSGGeometry.defaultAttributes_TexturedPoint2D(), 0)
            geometry.setDrawingMode(QSGGeometry.DrawingMode.DrawTriangles)
            node.setGeometry(geometry)
            node.setFlag(QSGGeometryNode.Flag.OwnsGeometry, True)

            # Attach texture material with premultiplied alpha (optimized for transparency)
            if self.atlas_texture:
                material = QSGTextureMaterial()
                material.setTexture(self.atlas_texture)
                # Enable alpha blending for transparent overlay (no clear needed)
                material.setFlag(QSGTextureMaterial.Flag.Blending, True)
                node.setMaterial(material)
                node.setFlag(QSGGeometryNode.Flag.OwnsMaterial, True)
        else:
            node = old_node

        # Build geometry for all visible sprites (only draws where sprites exist)
        self._update_geometry(node.geometry())
        # Note: Geometry is automatically marked dirty when updated

        # FPS tracking
        frame_time = (time.time() - frame_start) * 1000
        now = time.time()
        self.frame_times.append(now)

        if now - self.last_fps_log >= 1.0:
            cutoff = now - 1.0
            self.frame_times = [t for t in self.frame_times if t > cutoff]
            fps = len(self.frame_times)
            if fps > 0:
                print(f"[SceneGraph Renderer] FPS: {fps}, Frame time: {frame_time:.1f}ms, Total collectibles: {len(self._all_collectibles)}")
            self.last_fps_log = now

        return node

    def _update_geometry(self, geometry):
        """
        Transform ALL collectibles using viewport and build GPU geometry.
        NO CULLING - render everything for debugging.

        Each sprite = 2 triangles (6 vertices) with texture coordinates.
        GPU renders all sprites in a single draw call - MUCH faster than QPainter.
        """
        if not self._all_collectibles or self._viewport_width == 0:
            geometry.allocate(0)
            return

        # Calculate scale factors (same for all collectibles)
        scale_x = 1920.0 / self._viewport_width
        scale_y = 1080.0 / self._viewport_height

        # Build sprite list
        visible_sprites = []

        from qml.svg_icons import get_icon_name

        for col in self._all_collectibles:
            # Get map coordinates (detection space)
            map_x = col.get('map_x', 0)
            map_y = col.get('map_y', 0)

            # Apply transform: screen = (map - viewport) * scale
            screen_x = (map_x - self._viewport_x) * scale_x
            screen_y = (map_y - self._viewport_y) * scale_y

            # NO CULLING - draw everything
            # Center sprite (48x48)
            draw_x = screen_x - 24
            draw_y = screen_y - 24

            # Get texture coordinates
            col_type = col.get('type', 'random')
            is_collected = col.get('collected', False)
            icon_name = get_icon_name(col_type)
            cache_key = f'{icon_name}_{"collected" if is_collected else "normal"}'

            if cache_key not in self.sprite_rects:
                cache_key = f'random_{"collected" if is_collected else "normal"}'

            uv_rect = self.sprite_rects.get(cache_key)
            if uv_rect:
                visible_sprites.append((draw_x, draw_y, uv_rect))

        # Allocate geometry (6 vertices per sprite: 2 triangles)
        vertex_count = len(visible_sprites) * 6
        geometry.allocate(vertex_count)

        vertices = geometry.vertexDataAsPoint2D()
        tex_coords = geometry.vertexDataAsTexturedPoint2D()

        # Build triangles for each sprite
        idx = 0
        for draw_x, draw_y, uv_rect in visible_sprites:
            # Screen quad corners
            x0, y0 = draw_x, draw_y
            x1, y1 = draw_x + 48, draw_y + 48

            # UV corners (texture coordinates)
            u0, v0 = uv_rect.left(), uv_rect.top()
            u1, v1 = uv_rect.right(), uv_rect.bottom()

            # Triangle 1: top-left, top-right, bottom-left
            tex_coords[idx].set(x0, y0, u0, v0); idx += 1
            tex_coords[idx].set(x1, y0, u1, v0); idx += 1
            tex_coords[idx].set(x0, y1, u0, v1); idx += 1

            # Triangle 2: top-right, bottom-right, bottom-left
            tex_coords[idx].set(x1, y0, u1, v0); idx += 1
            tex_coords[idx].set(x1, y1, u1, v1); idx += 1
            tex_coords[idx].set(x0, y1, u0, v1); idx += 1
