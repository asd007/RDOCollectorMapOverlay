"""
QQuickPaintedItem for rendering collectibles with QPainter.

This provides native-speed rendering in QML using Python/QPainter.
Much faster than JavaScript Canvas2D.
"""

from PySide6.QtCore import Qt, QRectF, Slot, Signal, Property, QPointF, QByteArray
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QFont
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtSvg import QSvgRenderer
from typing import List, Dict
from qml.svg_icons import get_icon_svg, get_icon_name
import time


class CollectibleCanvas(QQuickPaintedItem):
    """
    High-performance collectible rendering using native QPainter.

    Exposed to QML as a custom item:
        CollectibleCanvas {
            anchors.fill: parent
            viewport: backend.viewport
            collectibles: backend.visibleCollectibles
        }
    """

    # Signals
    viewportChanged = Signal()
    collectiblesChanged = Signal()
    opacityValueChanged = Signal(float)
    renderFpsChanged = Signal(float)  # Emits rendering FPS

    # Collectible type colors and emojis (matching Electron design)
    TYPE_ICONS = {
        'arrowhead': '🎯',
        'bottle': '🍾',
        'coin': '🪙',
        'egg': '🥚',
        'flower': '🌺',
        'card_tarot': '🃏',
        'cups': '🏆',
        'pentacles': '🃏',
        'swords': '🎴',
        'wands': '⭐',
        'jewelry_random': '💍',
        'bracelet': '💍',
        'earring': '💍',
        'necklace': '💍',
        'ring': '💍',
        'heirlooms': '👑',
        'coastal': '🦴',
        'oceanic': '🦴',
        'megafauna': '🦴',
        'fossils_random': '🦴',
        'random': '❓'
    }

    TYPE_COLORS = {
        'arrowhead': QColor(255, 193, 7),  # Amber
        'bottle': QColor(76, 175, 80),     # Green
        'coin': QColor(255, 235, 59),      # Yellow
        'egg': QColor(156, 39, 176),       # Purple
        'flower': QColor(233, 30, 99),     # Pink
        'card_tarot': QColor(103, 58, 183), # Deep Purple
        'cups': QColor(255, 152, 0),       # Orange
        'pentacles': QColor(255, 193, 7),  # Amber
        'swords': QColor(96, 125, 139),    # Blue Grey
        'wands': QColor(255, 87, 34),      # Deep Orange
        'jewelry_random': QColor(233, 30, 99),  # Pink
        'bracelet': QColor(233, 30, 99),
        'earring': QColor(233, 30, 99),
        'necklace': QColor(233, 30, 99),
        'ring': QColor(233, 30, 99),
        'heirlooms': QColor(255, 193, 7),  # Amber
        'coastal': QColor(121, 85, 72),    # Brown
        'oceanic': QColor(33, 150, 243),   # Blue
        'megafauna': QColor(156, 39, 176), # Purple
        'fossils_random': QColor(121, 85, 72),
        'random': QColor(158, 158, 158)    # Grey
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set rendering hints
        self.setRenderTarget(QQuickPaintedItem.RenderTarget.FramebufferObject)
        self.setAntialiasing(False)  # Pixel-perfect sprites
        self.setOpaquePainting(False)  # Transparent background

        # Data
        self._collectibles: List[Dict] = []
        self._opacity: float = 0.7

        # Sprite cache (pre-rendered SVG sprites)
        self._sprite_cache: Dict[str, QPixmap] = {}
        self._sprites_initialized = False

        # Rendering FPS tracking (lightweight)
        self._paint_times: List[float] = []
        self._render_fps: float = 0.0
        self._last_fps_update: float = time.time()

    def ensureSpritesLoaded(self):
        """Ensure sprites are loaded (thread-safe, idempotent)"""
        if not self._sprites_initialized:
            try:
                self._generate_sprites()
                self._sprites_initialized = True
            except Exception as e:
                print(f"[CollectibleCanvas] Failed to generate sprites: {e}")

    def _generate_sprites(self):
        """Pre-render all SVG sprites to QPixmap for fast blitting (matching Electron)"""
        sprite_size = 48  # 48x48 pixels (matching Electron SPRITE_SIZE)

        # Get all unique icon names needed
        unique_icons = set(get_icon_name(col_type) for col_type in self.TYPE_ICONS.keys())

        for icon_name in unique_icons:
            # Get SVG string
            svg_data = get_icon_svg(icon_name)

            # Render normal state
            pixmap_normal = self._render_svg_to_pixmap(svg_data, sprite_size, is_collected=False)

            # Render collected state (50% opacity)
            pixmap_collected = self._render_svg_to_pixmap(svg_data, sprite_size, is_collected=True)

            # Cache with keys matching usage pattern
            self._sprite_cache[f'{icon_name}_normal'] = pixmap_normal
            self._sprite_cache[f'{icon_name}_collected'] = pixmap_collected

        print(f"[CollectibleCanvas] Generated {len(unique_icons)} SVG sprites (normal + collected states)")

    def _render_svg_to_pixmap(self, svg_string: str, size: int, is_collected: bool) -> QPixmap:
        """Render SVG string to QPixmap with optional collected state"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Apply collected state opacity
        if is_collected:
            painter.setOpacity(0.5)

        # Render SVG
        svg_renderer = QSvgRenderer(QByteArray(svg_string.encode('utf-8')))
        if svg_renderer.isValid():
            svg_renderer.render(painter)
        else:
            print(f"[CollectibleCanvas] Warning: Invalid SVG data")

        painter.end()
        return pixmap

    def paint(self, painter: QPainter):
        """
        Fast collectible rendering using QPainter.
        Called automatically by QML whenever update() is triggered.

        Renders all collectibles - GPU handles off-screen culling efficiently.
        """
        paint_start = time.time()

        # Debug: Track paint calls
        if not hasattr(self, '_paint_call_count'):
            self._paint_call_count = 0
            self._paint_last_log = time.time()
        self._paint_call_count += 1

        # Log every second
        if time.time() - self._paint_last_log >= 1.0:
            print(f"[CollectibleCanvas] paint() called {self._paint_call_count} times in last second")
            self._paint_call_count = 0
            self._paint_last_log = time.time()

        # Ensure sprites are loaded (happens once, on first paint, main thread)
        self.ensureSpritesLoaded()

        # Clear with transparent background
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(0, 0, int(self.width()), int(self.height()),
                        Qt.GlobalColor.transparent)

        # Draw collectibles
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setOpacity(self._opacity)

        for item in self._collectibles:
            col_type = item.get('type', 'random')
            x = item.get('x', 0)
            y = item.get('y', 0)
            is_collected = item.get('collected', False)

            # Get icon name and sprite from cache
            icon_name = get_icon_name(col_type)
            cache_key = f'{icon_name}_{"collected" if is_collected else "normal"}'
            sprite = self._sprite_cache.get(cache_key)

            if not sprite:
                # Fallback to random icon
                cache_key = f'random_{"collected" if is_collected else "normal"}'
                sprite = self._sprite_cache.get(cache_key)

            if sprite:
                # Center sprite (48x48) on collectible position
                draw_x = x - 24
                draw_y = y - 24

                # No bounds check - let GPU/compositor handle clipping
                painter.drawPixmap(QPointF(draw_x, draw_y), sprite)

        # Track rendering FPS (update every second)
        current_time = time.time()
        self._paint_times.append(current_time)

        # Update FPS every second
        if current_time - self._last_fps_update >= 1.0:
            # Remove old paint times (>1 second old)
            cutoff = current_time - 1.0
            self._paint_times = [t for t in self._paint_times if t > cutoff]

            # Calculate FPS
            self._render_fps = len(self._paint_times)
            self._last_fps_update = current_time
            self.renderFpsChanged.emit(self._render_fps)

    # Qt Properties for QML binding
    @Property('QVariantList', notify=collectiblesChanged)
    def collectibles(self):
        """List of visible collectibles with screen coordinates"""
        return self._collectibles

    @collectibles.setter
    def collectibles(self, value):
        # No deduplication - always update to ensure smooth rendering
        self._collectibles = value
        self.collectiblesChanged.emit()
        self.update()  # Trigger repaint

        # Debug: Track setter calls
        if not hasattr(self, '_setter_call_count'):
            self._setter_call_count = 0
            self._setter_last_log = time.time()
        self._setter_call_count += 1

        # Log every second
        if time.time() - self._setter_last_log >= 1.0:
            print(f"[CollectibleCanvas] Setter called {self._setter_call_count} times in last second")
            self._setter_call_count = 0
            self._setter_last_log = time.time()

    @Property(float, notify=opacityValueChanged)
    def opacityValue(self):
        """Sprite opacity (0.0 - 1.0)"""
        return self._opacity

    @opacityValue.setter
    def opacityValue(self, value):
        if self._opacity != value:
            self._opacity = value
            self.opacityValueChanged.emit()
            self.update()

    @Property(float, notify=renderFpsChanged)
    def renderFps(self):
        """Current rendering FPS"""
        return self._render_fps

    @Slot()
    def refresh(self):
        """Force repaint (can be called from QML)"""
        self.update()

    @Slot(list)
    def updateCollectibles(self, collectibles):
        """
        Direct update slot - bypasses QML property binding entirely.
        Called from OverlayBackend when collectibles change.
        """
        self._collectibles = collectibles
        self.collectiblesChanged.emit()
        self.update()  # Trigger immediate repaint
