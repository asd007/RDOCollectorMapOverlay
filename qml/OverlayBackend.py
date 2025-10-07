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
from core.collectibles.collection_tracker import CollectionTracker
from core.collectibles.collectibles_filter import filter_visible_collectibles
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
    isPanningChanged = Signal()  # Emitted when user starts/stops panning

    def __init__(self, overlay_state=None, parent=None):
        super().__init__(parent)

        # Backend state (from app.py)
        self._state = overlay_state

        # Collection tracker (reference to ApplicationState's tracker)
        # Note: For backwards compatibility, we keep self.tracker as a property
        # but it delegates to state.collection_tracker

        # Canvas reference (set from QML)
        self._canvas = None

        # GL renderer reference (set from app_qml.py)
        self.gl_renderer = None

        # Cached collectibles list for GL renderer (rebuilt only when tracker changes)
        self._cached_collectibles = None

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

        # Viewport velocity tracking (for frontend prediction)
        self._viewport_vx: float = 0.0  # Velocity in detection space units/sec
        self._viewport_vy: float = 0.0
        self._last_viewport_update: float = time.perf_counter()

        # Drift statistics (prediction accuracy)
        self._prediction_drift_x: float = 0.0  # Last prediction error in X
        self._prediction_drift_y: float = 0.0  # Last prediction error in Y
        self._avg_drift: float = 0.0  # Running average drift magnitude
        self._drift_samples: List[float] = []  # Last 100 drift samples
        self._last_predicted_x: float = 0.0  # Last predicted position
        self._last_predicted_y: float = 0.0

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

        # Panning detection (for prediction weighting)
        self._is_panning: bool = False  # True when left mouse button is down

        # Rendering stats
        self._render_fps: float = 0.0

        # Stats for troubleshooting
        self._viewport_update_count: int = 0
        self._collectibles_update_count: int = 0

        # FPS update timer (pass parent for proper cleanup)
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(500)  # Update every 500ms

    @property
    def tracker(self):
        """Get collection tracker from ApplicationState (backwards compatibility)."""
        return self._state.collection_tracker if self._state else None

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

            # Build initial collectibles list for renderer
            self._rebuild_collectibles_cache()

            # Emit signal to notify QML that collection sets are ready
            self.collectiblesChanged.emit()

    def _rebuild_collectibles_cache(self):
        """
        Rebuild collectibles list for renderer when tracker state changes.
        Only iterates through ALL collectibles when tracker visibility changes.
        NOT called on every frame - only when user toggles categories.
        """
        if not self._state or not self.gl_renderer:
            return

        # Build list of all visible collectibles in detection space
        collectibles_list = []
        first_collectible = None
        for col in self._state.collectibles:
            # Filter by tracker visibility
            if not self.tracker.is_visible(col.category):
                continue

            collectibles_list.append({
                'map_x': col.x,  # Detection space
                'map_y': col.y,
                'type': col.type,
                'collected': self.tracker.is_collected(col.category, col.name)
            })

            # Store first collectible for detailed logging
            if first_collectible is None:
                first_collectible = col

        # Pass to renderer (this is NOT on the render loop)
        self.gl_renderer.set_collectibles(collectibles_list)
        print(f"[Backend] Rebuilt collectibles cache: {len(collectibles_list)} items")

        # Log first collectible's coordinates in ALL spaces for verification
        if first_collectible:
            print(f"[Backend] First collectible '{first_collectible.name}':")
            print(f"  LatLng: ({first_collectible.lat:.4f}, {first_collectible.lng:.4f})")
            print(f"  HQ:     ({first_collectible.hq_x}, {first_collectible.hq_y})")
            print(f"  Detection: ({first_collectible.x}, {first_collectible.y})")
            print(f"  Type: {first_collectible.type}")

    @Slot(object, object)
    def update_viewport(self, viewport: Dict, collectibles: List[Dict]):
        """
        Update viewport transform only. Collectibles already loaded in renderer.
        Called from continuous_capture service.

        Args:
            viewport: {'x', 'y', 'width', 'height'} in detection space
            collectibles: Ignored - renderer already has ALL collectibles
        """
        self._viewport_update_count += 1
        self._viewport = viewport

        # Calculate viewport velocity for frontend prediction
        current_time = time.perf_counter()
        dt = current_time - self._last_viewport_update

        if dt > 0 and self._viewport_x != 0:  # Skip first frame
            # Calculate velocity in detection space units per second
            dx = viewport['x'] - self._viewport_x
            dy = viewport['y'] - self._viewport_y
            self._viewport_vx = dx / dt
            self._viewport_vy = dy / dt

        self._last_viewport_update = current_time

        # Debug: Log first viewport update
        if self._viewport_update_count == 1:
            print(f"[Backend] First viewport update: x={viewport['x']}, y={viewport['y']}, w={viewport['width']}, h={viewport['height']}")

        # Update viewport transform in renderer
        if self.gl_renderer:
            self.gl_renderer.set_viewport(
                viewport['x'],
                viewport['y'],
                viewport['width'],
                viewport['height']
            )

        # Update viewport properties for QML
        self._viewport_x = viewport['x']
        self._viewport_y = viewport['y']
        self._viewport_width = viewport['width']
        self._viewport_height = viewport['height']

        self.viewportChanged.emit()

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

        # Scene Graph renderer already has ALL collectibles cached (set in _rebuild_collectibles_cache)
        # It only needs viewport updates (handled in update_viewport_and_collectibles)
        # No per-frame collectible updates needed!

    def _update_visible_collectibles(self):
        """Filter and transform collectibles to screen coordinates using pure function"""
        if not self._viewport or not self._state:
            self._visible_collectibles = []
            self.collectiblesChanged.emit()
            return

        viewport = self._viewport

        # Use pure function for filtering and transformation
        visible = filter_visible_collectibles(
            all_collectibles=self._state.collectibles,
            viewport_x=viewport['x'],
            viewport_y=viewport['y'],
            viewport_width=viewport['width'],
            viewport_height=viewport['height'],
            screen_width=1920,
            screen_height=1080,
            is_category_visible=self.tracker.is_visible,
            is_collected=self.tracker.is_collected
        )

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
        self._rebuild_collectibles_cache()  # Rebuild renderer cache
        self._update_visible_collectibles()  # Refresh to update collected state

    @Slot(str)
    def toggle_category_visibility(self, category: str):
        """Toggle category visibility"""
        self.tracker.toggle_visibility(category)
        self._collection_sets_dirty = True  # Mark cache as dirty
        self._rebuild_collectibles_cache()  # Rebuild renderer cache
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

    @Slot(bool, bool)
    def handle_mouse_button_state(self, left_down: bool, right_down: bool):
        """
        Handle mouse button state change from pynput observer.
        Updates panning detection state (for prediction weighting).

        Args:
            left_down: True if left button is pressed
            right_down: True if right button is pressed
        """
        # User is panning when left mouse button is down
        was_panning = self._is_panning
        self._is_panning = left_down

        # Emit signal if panning state changed
        if was_panning != self._is_panning:
            self.isPanningChanged.emit()

    # Hotkey actions

    @Slot()
    def refresh_data(self):
        """F6 - Refresh collectibles from Joan Ropke API"""
        if not self._state:
            return
        print("[Hotkey] F6 - Refreshing collectibles...")
        try:
            from core.collectibles.collectibles_repository import CollectiblesRepository
            collectibles = CollectiblesRepository.load(self._state.coord_transform)
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

    # Opacity removed - panel is always opaque, only collected items dimmed

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

    def get_is_panning(self):
        """Whether user is currently panning (left mouse button down)"""
        return self._is_panning

    isPanning = Property(bool, get_is_panning, notify=isPanningChanged)

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

    def get_viewport_vx(self):
        """Viewport X velocity in detection space units/sec"""
        return self._viewport_vx

    viewportVx = Property(float, get_viewport_vx, notify=viewportChanged)

    def get_viewport_vy(self):
        """Viewport Y velocity in detection space units/sec"""
        return self._viewport_vy

    viewportVy = Property(float, get_viewport_vy, notify=viewportChanged)

    # Drift statistics properties
    def get_prediction_drift_x(self):
        """Last prediction drift in X (detection space)"""
        return self._prediction_drift_x

    predictionDriftX = Property(float, get_prediction_drift_x, notify=viewportChanged)

    def get_prediction_drift_y(self):
        """Last prediction drift in Y (detection space)"""
        return self._prediction_drift_y

    predictionDriftY = Property(float, get_prediction_drift_y, notify=viewportChanged)

    def get_avg_drift(self):
        """Average prediction drift magnitude (detection space)"""
        return self._avg_drift

    avgDrift = Property(float, get_avg_drift, notify=viewportChanged)

    @Slot(float, float)
    def report_predicted_position(self, predicted_x: float, predicted_y: float):
        """
        Called from QML to report predicted viewport position.
        Stores the prediction so drift can be calculated on next backend update.
        """
        # Store the predicted position
        self._last_predicted_x = predicted_x
        self._last_predicted_y = predicted_y
