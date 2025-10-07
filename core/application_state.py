"""
Single source of truth for application state.
Thread ownership: Lives on Qt main thread, updated via signals from capture thread.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict
from PySide6.QtCore import QObject, Signal, Property

from models.collectible import Collectible


@dataclass
class ViewportState:
    """Current viewport in detection space."""
    x: float
    y: float
    width: float
    height: float
    confidence: float
    timestamp: float


class ApplicationState(QObject):
    """
    Single source of truth for RDO Overlay application state.

    Thread ownership: Qt main thread
    Updates from capture thread: Via Signal/Slot (thread-safe)

    Organization:
    - Immutable reference data (loaded once, never changes)
    - Mutable tracking state (updated every frame)
    - Service references (matcher, capture, etc.)
    - UI preferences (user settings)
    """

    # Fixed screen dimensions
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 1080

    # Signals for reactive updates
    viewport_changed = Signal(ViewportState)
    collectibles_changed = Signal()
    tracker_visibility_changed = Signal(str, bool)  # category, visible

    def __init__(self, parent=None):
        super().__init__(parent)

        # === IMMUTABLE REFERENCE DATA ===
        # Loaded once at startup, never modified (thread-safe to read from any thread)

        self._all_collectibles: List[Collectible] = []  # All collectibles from Joan Ropke API
        self.collectibles_x: Optional[np.ndarray] = None  # Numpy arrays for fast lookup
        self.collectibles_y: Optional[np.ndarray] = None
        self.full_map: Optional[np.ndarray] = None  # Grayscale map for matching
        self.coord_transform = None  # LatLng <-> HQ coordinate transformer

        # === SERVICE REFERENCES ===
        # External services and components (set after initialization)

        self.matcher = None  # CascadeScaleMatcher
        self.capture_service = None  # ContinuousCaptureService
        self.backend = None  # OverlayBackend (QML bridge)
        self.game_focus_manager = None  # RDR2 window focus manager
        self.click_observer = None  # Global mouse click observer
        self.socketio = None  # SocketIO instance for WebSocket events
        self.game_capture = None  # WindowsCapture instance

        # === MUTABLE TRACKING STATE ===
        # Updated every frame from capture thread (write via signals, read on Qt thread)

        self._current_viewport: Optional[ViewportState] = None

        # === INITIALIZATION STATE ===
        self.is_initialized = False

        # === UI PREFERENCES ===
        # User settings (modified by UI, persisted)

        self._overlay_visible = True
        self._overlay_opacity = 0.9
        self._tracker_expanded = False

    # === Immutable Reference Data (Thread-safe reads) ===

    def set_collectibles(self, collectibles: List[Collectible]):
        """
        Update collectibles and prepare numpy arrays for fast lookup.
        Thread: Qt main thread only.
        """
        self._all_collectibles = collectibles
        if collectibles:
            self.collectibles_x = np.array([c.x for c in collectibles], dtype=np.int32)
            self.collectibles_y = np.array([c.y for c in collectibles], dtype=np.int32)
        else:
            self.collectibles_x = None
            self.collectibles_y = None
        self.collectibles_changed.emit()

    def get_all_collectibles(self) -> List[Collectible]:
        """
        Get all collectibles (thread-safe read of immutable data).
        Thread: Any thread (immutable after set_collectibles)
        """
        return self._all_collectibles

    @property
    def collectibles(self) -> List[Collectible]:
        """Property for backwards compatibility with OverlayState."""
        return self._all_collectibles

    def get_visible_collectibles(self, viewport: Dict) -> List[Dict]:
        """
        Get collectibles visible in current viewport.
        Viewport is from cropped image but collectibles display on full screen.

        Returns optimized payload with full field names for QML compatibility:
        - 'x', 'y': screen coordinates (essential)
        - 'type': collectible type
        - 'name': collectible name
        - 'category': collection category
        - 'help': help text (optional)
        - 'video': video URL (optional)
        - 'map_x', 'map_y': detection space coordinates (for drift tracking)
        - 'lat', 'lng': fallback coordinates (only if name missing)
        """
        if not self._all_collectibles or self.collectibles_x is None:
            return []

        x1, y1 = viewport['map_x'], viewport['map_y']
        x2, y2 = x1 + viewport['map_w'], y1 + viewport['map_h']

        # Fast numpy filtering for collectibles in map viewport
        in_view = (
            (self.collectibles_x >= x1) & (self.collectibles_x <= x2) &
            (self.collectibles_y >= y1) & (self.collectibles_y <= y2)
        )

        visible_indices = np.where(in_view)[0]

        # Scale from detection space viewport to full screen
        scale_x = self.SCREEN_WIDTH / viewport['map_w']
        scale_y = self.SCREEN_HEIGHT / viewport['map_h']

        visible = []
        for idx in visible_indices:
            col = self._all_collectibles[idx]

            # Calculate position on full screen
            screen_x = int((col.x - x1) * scale_x)
            screen_y = int((col.y - y1) * scale_y)

            # Check bounds against full 1920x1080 screen
            if 0 <= screen_x <= self.SCREEN_WIDTH and 0 <= screen_y <= self.SCREEN_HEIGHT:
                # Full field names for QML/Canvas compatibility
                item = {
                    'x': screen_x,
                    'y': screen_y,
                    'type': col.type,
                    'name': col.name,
                    'category': col.category
                }

                # Optional fields - only include if present
                if col.help:
                    item['help'] = col.help
                if col.video:
                    item['video'] = col.video

                # Map coordinates for drift tracking
                item['map_x'] = col.x
                item['map_y'] = col.y

                # Fallback ID coordinates - only if name is missing (rare)
                if not col.name and col.lat is not None:
                    item['lat'] = col.lat
                    item['lng'] = col.lng

                visible.append(item)

        return visible

    # === Mutable Tracking State (Signal-based updates) ===

    @property
    def current_viewport(self) -> Optional[ViewportState]:
        """
        Get current viewport.
        Thread: Qt main thread only (mutable state).
        """
        return self._current_viewport

    def update_viewport(self, x: float, y: float, width: float, height: float, confidence: float):
        """
        Update viewport from capture thread (via signal connection).
        Thread: Called on Qt main thread (via queued signal).
        """
        import time
        self._current_viewport = ViewportState(x, y, width, height, confidence, time.time())
        self.viewport_changed.emit(self._current_viewport)

    # === UI Preferences (Qt Properties for QML binding) ===

    def get_overlay_visible(self) -> bool:
        return self._overlay_visible

    def set_overlay_visible(self, visible: bool):
        self._overlay_visible = visible

    overlayVisible = Property(bool, get_overlay_visible, set_overlay_visible)

    def get_overlay_opacity(self) -> float:
        return self._overlay_opacity

    def set_overlay_opacity(self, opacity: float):
        self._overlay_opacity = opacity

    overlayOpacity = Property(float, get_overlay_opacity, set_overlay_opacity)
