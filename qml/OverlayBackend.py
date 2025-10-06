"""
QML Backend Bridge - Exposes Python data/logic to QML.

Provides reactive properties and slots for:
- Viewport tracking
- Collectible visibility
- Collection progress
- FPS monitoring
- Status updates
"""

import time
import re
from PySide6.QtCore import QObject, Signal, Property, Slot, QTimer, QUrl
from PySide6.QtGui import QCursor
from typing import List, Dict, Optional
from core.collection_tracker import CollectionTracker
from qml.svg_icons import get_icon_svg


class OverlayBackend(QObject):
    """
    Main backend exposed to QML.

    Usage in QML:
        import RDOOverlay 1.0

        OverlayBackend {
            id: backend
            // Auto-connected to singleton instance
        }
    """

    # Signals for reactive updates
    viewportChanged = Signal()
    collectiblesChanged = Signal()
    fpsChanged = Signal()
    statusChanged = Signal()
    mouseClicked = Signal(int, int, str)  # x, y, button
    trackerVisibilityChanged = Signal()
    opacityChanged = Signal()
    overlayVisibilityChanged = Signal()

    def __init__(self, overlay_state=None, parent=None):
        super().__init__(parent)

        # Backend state (from app.py)
        self._state = overlay_state

        # Collection tracker
        self.tracker = CollectionTracker()

        # Canvas reference (set from QML)
        self._canvas = None

        # Cached collection sets (only rebuild when tracker changes, not on every collectiblesChanged)
        self._collection_sets_cache = None
        self._collection_sets_dirty = True

        # Current viewport (detection space coordinates)
        self._viewport: Optional[Dict] = None

        # Viewport transform properties (for QML container transform)
        self._viewport_x: float = 0.0
        self._viewport_y: float = 0.0
        self._viewport_width: float = 3840.0  # Detection space default
        self._viewport_height: float = 2160.0

        # Visible collectibles (screen space coordinates) - never None!
        self._visible_collectibles: List[Dict] = []

        # FPS tracking
        self._fps: float = 0.0
        self._frame_times: List[float] = []

        # Status
        self._status_text: str = "Ready"
        self._status_color: str = "#22c55e"

        # UI state
        self._tracker_visible: bool = False  # Start with tracker collapsed
        self._opacity: float = 0.7
        self._overlay_visible: bool = True

        # Rendering stats
        self._render_fps: float = 0.0

        # Stats for troubleshooting
        self._viewport_update_count: int = 0
        self._collectibles_update_count: int = 0

        # FPS update timer (pass parent for proper cleanup)
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(500)  # Update every 500ms

    def set_state(self, state):
        """Connect to OverlayState from app.py"""
        self._state = state

        # Initialize collection tracker with collectibles
        if state and state.collectibles:
            collectibles_list = [
                {
                    'name': c.name,
                    'type': c.type,  # This is the actual category (e.g., 'arrowhead')
                    'category': c.category  # This is also the category, same as type
                }
                for c in state.collectibles
            ]
            self.tracker.initialize_from_collectibles(collectibles_list)

            # Emit signal to notify QML that collection sets are ready
            self.collectiblesChanged.emit()

    @Slot(dict, list)
    def update_viewport(self, viewport: Dict, collectibles: List[Dict]):
        """
        Update viewport and visible collectibles (pre-computed on capture thread).
        Called from continuous_capture service.

        Args:
            viewport: {'x', 'y', 'width', 'height'} in detection space
            collectibles: Pre-computed list of visible collectibles with screen coords
        """
        self._viewport_update_count += 1
        self._viewport = viewport

        # Update viewport transform properties for QML container
        self._viewport_x = viewport['x']
        self._viewport_y = viewport['y']
        self._viewport_width = viewport['width']
        self._viewport_height = viewport['height']

        self.viewportChanged.emit()

        # Use pre-computed collectibles from capture thread (avoid blocking UI thread)
        self._set_visible_collectibles_direct(collectibles)

        # Track frame time for FPS
        current_time = time.perf_counter()
        self._frame_times.append(current_time)

    def _set_visible_collectibles_direct(self, collectibles: List[Dict]):
        """
        Set visible collectibles directly from pre-computed list (from capture thread).
        Only needs to add 'collected' status from tracker (fast lookup).
        """
        self._collectibles_update_count += 1

        # Add collected status (fast O(1) lookups via tracker)
        for item in collectibles:
            item['collected'] = self.tracker.is_collected(item['category'], item['name'])

        self._visible_collectibles = list(collectibles)  # Explicit copy
        self.collectiblesChanged.emit()

        # Direct canvas update (bypasses QML property binding)
        if self._canvas:
            self._canvas.updateCollectibles(self._visible_collectibles)

    def _update_visible_collectibles(self):
        """Filter and transform collectibles to screen coordinates"""
        if not self._viewport or not self._state:
            self._visible_collectibles = []
            self.collectiblesChanged.emit()
            return

        viewport = self._viewport
        viewport_x = viewport['x']
        viewport_y = viewport['y']
        viewport_w = viewport['width']
        viewport_h = viewport['height']

        # Screen dimensions
        screen_w = 1920
        screen_h = 1080

        # Transform scale
        scale_x = screen_w / viewport_w
        scale_y = screen_h / viewport_h

        visible = []
        for col in self._state.collectibles:
            # Check if collectible is in viewport (detection space)
            if (viewport_x <= col.x <= viewport_x + viewport_w and
                viewport_y <= col.y <= viewport_y + viewport_h):

                # Check if category is visible (from collection tracker)
                if not self.tracker.is_visible(col.category):
                    continue

                # Transform to screen coordinates
                screen_x = int((col.x - viewport_x) * scale_x)
                screen_y = int((col.y - viewport_y) * scale_y)

                visible.append({
                    'x': screen_x,
                    'y': screen_y,
                    'type': col.type,
                    'name': col.name,
                    'category': col.category,
                    'help': col.help if hasattr(col, 'help') else '',
                    'video': col.video if hasattr(col, 'video') else '',
                    'collected': self.tracker.is_collected(col.category, col.name)
                })

        self._collectibles_update_count += 1
        # Force property change by creating a brand new list (QML reference comparison)
        self._visible_collectibles = list(visible)  # Explicit copy
        self.collectiblesChanged.emit()

    def _update_fps(self):
        """Calculate FPS from frame times"""
        current_time = time.perf_counter()

        # Remove old frame times (>1 second old)
        cutoff = current_time - 1.0
        self._frame_times = [t for t in self._frame_times if t > cutoff]

        # FPS = frames in last second
        self._fps = len(self._frame_times)
        self.fpsChanged.emit()

    @Slot(str, str)
    def toggle_collected(self, category: str, item_name: str):
        """Mark/unmark item as collected"""
        self.tracker.toggle_collected(category, item_name)
        self._collection_sets_dirty = True  # Mark cache as dirty
        self._update_visible_collectibles()  # Refresh to update collected state

    @Slot(str)
    def toggle_category_visibility(self, category: str):
        """Toggle category visibility"""
        self.tracker.toggle_visibility(category)
        self._collection_sets_dirty = True  # Mark cache as dirty
        self._update_visible_collectibles()

    @Slot(str)
    def toggle_set_expanded(self, category: str):
        """Toggle collection set expansion state"""
        self.tracker.toggle_expanded(category)
        self._collection_sets_dirty = True  # Mark cache as dirty
        self.collectiblesChanged.emit()  # Notify QML to refresh

    @Slot(str, result=str)
    def get_icon_svg(self, icon_name: str) -> str:
        """Get SVG string for an icon name (for QML rendering)"""
        return get_icon_svg(icon_name)

    @Slot(str, str)
    def update_status(self, text: str, color: str):
        """Update status display"""
        self._status_text = text
        self._status_color = color
        self.statusChanged.emit()

    @Slot(int, int, str)
    def handle_mouse_click(self, x: int, y: int, button: str):
        """
        Handle global mouse click from pynput observer.
        Emit signal for QML to do hit-testing.

        Args:
            x, y: Screen coordinates
            button: 'left' or 'right'
        """
        self.mouseClicked.emit(x, y, button)

    # Hotkey actions

    @Slot()
    def refresh_data(self):
        """F6 - Refresh collectibles from Joan Ropke API"""
        if not self._state:
            return
        print("[Hotkey] F6 - Refreshing collectibles...")
        try:
            from core import CollectiblesLoader
            collectibles = CollectiblesLoader.load(self._state.coord_transform)
            self._state.set_collectibles(collectibles)

            # Re-initialize tracker with new data
            collectibles_list = [
                {
                    'name': c.name,
                    'type': c.type,
                    'category': c.category
                }
                for c in collectibles
            ]
            self.tracker.initialize_from_collectibles(collectibles_list)

            self._update_visible_collectibles()
            self.update_status(f"Refreshed - {len(collectibles)} collectibles loaded", "#22c55e")
            print(f"[Hotkey] Loaded {len(collectibles)} collectibles")
        except Exception as e:
            self.update_status(f"Refresh failed: {e}", "#ef4444")
            print(f"[Hotkey] Refresh failed: {e}")

    @Slot()
    def toggle_tracker(self):
        """Toggle collection tracker visibility (via F5 hotkey or header click)"""
        self._tracker_visible = not self._tracker_visible
        self.trackerVisibilityChanged.emit()

    @Slot()
    def cycle_opacity(self):
        """F7 - Cycle opacity levels (0.3 -> 0.5 -> 0.7 -> 0.9)"""
        opacities = [0.3, 0.5, 0.7, 0.9]
        try:
            current_index = opacities.index(self._opacity)
            next_index = (current_index + 1) % len(opacities)
        except ValueError:
            next_index = 2  # Default to 0.7 if current value not in list

        self._opacity = opacities[next_index]
        self.opacityChanged.emit()
        print(f"[Hotkey] F7 - Opacity: {int(self._opacity * 100)}%")

    @Slot()
    def toggle_visibility(self):
        """F8 - Toggle overlay visibility"""
        self._overlay_visible = not self._overlay_visible
        self.overlayVisibilityChanged.emit()
        print(f"[Hotkey] F8 - Overlay {'visible' if self._overlay_visible else 'hidden'}")

    @Slot()
    def force_alignment(self):
        """F9 - Force alignment / reset tracking"""
        print("[Hotkey] F9 - Force alignment requested")
        # Reset viewport to force fresh alignment
        self._viewport = None
        self._visible_collectibles = []
        self.viewportChanged.emit()
        self.collectiblesChanged.emit()
        self.update_status("Press F9 in game to align", "#fbbf24")

    @Slot()
    def clear_collected(self):
        """Ctrl+Shift+C - Clear all collected items"""
        count = len([item for items in self.tracker._collected.values() for item in items])
        if count > 0:
            self.tracker._collected.clear()
            self.tracker._save_state()
            self._update_visible_collectibles()
            print(f"[Hotkey] Cleared {count} collected items")
            self.update_status(f"Cleared {count} collected items", "#22c55e")
        else:
            print("[Hotkey] No collected items to clear")
            self.update_status("No items to clear", "#9ca3af")

    @Slot(result='QVariantMap')
    def get_cursor_pos(self):
        """Get global cursor position for tooltip hover detection"""
        pos = QCursor.pos()
        return {'x': pos.x(), 'y': pos.y()}

    @Slot(float)
    def update_render_fps(self, fps: float):
        """Update rendering FPS from CollectibleCanvas"""
        self._render_fps = fps

    @Slot('QObject*')
    def set_canvas(self, canvas):
        """Register canvas reference for direct updates"""
        self._canvas = canvas
        print(f"[Backend] Canvas registered: {canvas}")

    def get_backend_stats(self) -> Dict:
        """Get backend statistics for debugging"""
        return {
            'viewport_updates': self._viewport_update_count,
            'collectibles_updates': self._collectibles_update_count,
            'current_viewport': self._viewport,
            'visible_collectibles_count': len(self._visible_collectibles),
            'total_collectibles': len(self._state.collectibles) if self._state else 0
        }

    def get_render_fps(self) -> float:
        """Get current rendering FPS for API stats"""
        return self._render_fps

    # Click-through management signals
    clickThroughDisableRequested = Signal()
    clickThroughEnableRequested = Signal()

    # Video player signals
    videoRequested = Signal(str, str)  # (url, name)

    @Slot()
    def disable_click_through(self):
        """Disable click-through (called when video player opens)"""
        self.clickThroughDisableRequested.emit()

    @Slot()
    def enable_click_through(self):
        """Re-enable click-through (called when video player closes)"""
        self.clickThroughEnableRequested.emit()

    @Slot(str, str)
    def open_video(self, video_url: str, collectible_name: str):
        """
        Open YouTube video in embedded QML video player.

        This replaces the old external browser approach with an in-app
        player window that appears on top of the game screen.

        Args:
            video_url: YouTube URL (may include timestamp)
            collectible_name: Name of collectible (for logging)
        """
        # Emit signal to video player (handled in QML)
        self.videoRequested.emit(video_url, collectible_name)

    # Qt Properties for QML binding

    def get_visible_collectibles(self):
        """List of visible collectibles with screen coordinates"""
        return self._visible_collectibles

    visibleCollectibles = Property('QVariantList', get_visible_collectibles, notify=collectiblesChanged)

    def get_fps(self):
        """Current FPS"""
        return self._fps

    fps = Property(float, get_fps, notify=fpsChanged)

    def get_status_text(self):
        """Status message"""
        return self._status_text

    statusText = Property(str, get_status_text, notify=statusChanged)

    def get_status_color(self):
        """Status indicator color"""
        return self._status_color

    statusColor = Property(str, get_status_color, notify=statusChanged)

    def get_total_collected(self):
        """Total collected items"""
        return self.tracker.totalCollected if hasattr(self, 'tracker') else 0

    totalCollected = Property(int, get_total_collected, notify=collectiblesChanged)

    def get_total_items(self):
        """Total items"""
        return self.tracker.totalItems if hasattr(self, 'tracker') else 0

    totalItems = Property(int, get_total_items, notify=collectiblesChanged)

    def get_completion_percent(self):
        """Completion percentage"""
        return self.tracker.completionPercent if hasattr(self, 'tracker') else 0

    completionPercent = Property(int, get_completion_percent, notify=collectiblesChanged)

    def get_collection_sets(self):
        """
        Get all collection sets for QML display (cached for performance).

        CRITICAL: This is called 30+ times/sec due to collectiblesChanged signal!
        Cache the result and only rebuild when tracker actually changes.
        """
        if not hasattr(self, 'tracker') or not self.tracker._sets:
            return []

        # Return cached sets if available and not dirty
        if not self._collection_sets_dirty and self._collection_sets_cache is not None:
            return self._collection_sets_cache

        # Rebuild collection sets (expensive operation)
        sets = []
        for category, set_obj in self.tracker._sets.items():
            collected_count = len(self.tracker._collected.get(category, set()))
            total_count = set_obj.total

            # Get items with collected status
            items = []
            for item_name in set_obj.items:
                items.append({
                    'name': item_name,
                    'collected': self.tracker.is_collected(category, item_name)
                })

            sets.append({
                'name': set_obj.name,
                'category': category,
                'icon': set_obj.icon,
                'items': items,
                'progress': collected_count,
                'total': total_count,
                'isVisible': self.tracker.is_visible(category),
                'isExpanded': self.tracker.is_expanded(category),
                'isRandom': set_obj.is_random
            })

        # Cache the result
        self._collection_sets_cache = sets
        self._collection_sets_dirty = False

        return sets

    collectionSets = Property('QVariantList', get_collection_sets, notify=collectiblesChanged)

    def get_tracker_visible(self):
        """Collection tracker visibility state"""
        return self._tracker_visible

    trackerVisible = Property(bool, get_tracker_visible, notify=trackerVisibilityChanged)

    def get_opacity(self):
        """Overlay opacity (0.0 - 1.0)"""
        return self._opacity

    opacity = Property(float, get_opacity, notify=opacityChanged)

    def get_overlay_visible(self):
        """Overall overlay visibility"""
        return self._overlay_visible

    overlayVisible = Property(bool, get_overlay_visible, notify=overlayVisibilityChanged)

    # Viewport transform properties (for QML container transform)
    def get_viewport_x(self):
        """Viewport X offset in detection space"""
        return self._viewport_x

    viewportX = Property(float, get_viewport_x, notify=viewportChanged)

    def get_viewport_y(self):
        """Viewport Y offset in detection space"""
        return self._viewport_y

    viewportY = Property(float, get_viewport_y, notify=viewportChanged)

    def get_viewport_width(self):
        """Viewport width in detection space"""
        return self._viewport_width

    viewportWidth = Property(float, get_viewport_width, notify=viewportChanged)

    def get_viewport_height(self):
        """Viewport height in detection space"""
        return self._viewport_height

    viewportHeight = Property(float, get_viewport_height, notify=viewportChanged)
