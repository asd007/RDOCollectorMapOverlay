# Refactoring Roadmap - Phase 2

This document provides step-by-step implementation instructions for Phase 2 refactoring: breaking up the god objects and unifying state management.

## Overview

**Goal**: Reduce complexity by 50% and improve testability
**Effort**: 5-7 days of focused work
**Risk**: Medium (touching hot code paths)

## Prerequisites (✅ Complete)

- [x] Threading documentation (`docs/THREADING.md`)
- [x] TestDataCollector already extracted
- [x] Recent renderer cleanup (SpriteAtlas extraction)

---

## Task 1: Create Unified ApplicationState (Priority 0)

### Problem
Three overlapping state stores causing data races and confusion:
- `api/state.py` - OverlayState (collectibles, matcher, map)
- `qml/OverlayBackend.py` - viewport, visible collectibles, tracker
- `core/continuous_capture.py` - latest_result, viewport tracking

### Solution
Single source of truth with clear ownership.

### Implementation Steps

#### Step 1.1: Create ApplicationState Class

**Create**: `core/application_state.py`

```python
"""
Single source of truth for application state.
Thread ownership: Lives on Qt main thread, updated via signals from capture thread.
"""

from dataclasses import dataclass
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Property

from models.collectible import Collectible
from matching.viewport_tracker import Viewport
from core.collection_tracker import CollectionTracker


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
    - UI preferences (user settings)
    """

    # Signals for reactive updates
    viewport_changed = Signal(ViewportState)
    collectibles_changed = Signal()
    tracker_visibility_changed = Signal(str, bool)  # category, visible

    def __init__(self, parent=None):
        super().__init__(parent)

        # === IMMUTABLE REFERENCE DATA ===
        # Loaded once at startup, never modified (thread-safe to read from any thread)

        self._all_collectibles: List[Collectible] = []  # All collectibles from Joan Ropke API
        self._reference_map = None  # Grayscale map for matching
        self._coord_transform = None  # LatLng <-> HQ coordinate transformer

        # === MUTABLE TRACKING STATE ===
        # Updated every frame from capture thread (write via signals, read on Qt thread)

        self._current_viewport: Optional[ViewportState] = None
        self._collection_tracker: Optional[CollectionTracker] = None

        # === UI PREFERENCES ===
        # User settings (modified by UI, persisted)

        self._overlay_visible = True
        self._overlay_opacity = 0.9
        self._tracker_expanded = False

    # === Immutable Reference Data (Thread-safe reads) ===

    def set_collectibles(self, collectibles: List[Collectible]):
        """
        Set all collectibles (called once at startup).
        Thread: Qt main thread only.
        """
        self._all_collectibles = collectibles
        self.collectibles_changed.emit()

    def get_all_collectibles(self) -> List[Collectible]:
        """
        Get all collectibles (thread-safe read of immutable data).
        Thread: Any thread (immutable after set_collectibles)
        """
        return self._all_collectibles

    def set_reference_data(self, reference_map, coord_transform):
        """
        Set reference map and coordinate transformer (called once at startup).
        Thread: Qt main thread only.
        """
        self._reference_map = reference_map
        self._coord_transform = coord_transform

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

    @property
    def collection_tracker(self) -> CollectionTracker:
        """
        Get collection tracker.
        Thread: Qt main thread only.
        """
        return self._collection_tracker

    def set_collection_tracker(self, tracker: CollectionTracker):
        """
        Set collection tracker (called once at startup).
        Thread: Qt main thread only.
        """
        self._collection_tracker = tracker

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
```

#### Step 1.2: Migrate api/state.py to ApplicationState

**Before**:
```python
# api/state.py
class OverlayState:
    def __init__(self):
        self.collectibles = []
        self.matcher = None
        self.map_loader = None
```

**After**: Remove `api/state.py` entirely, replace all imports with:
```python
from core.application_state import ApplicationState
state = ApplicationState()
```

**Files to update**:
- `api/routes.py` - Replace `OverlayState` with `ApplicationState`
- `app_qml.py` - Create single `ApplicationState` instance
- Any other files importing `from api.state import state`

#### Step 1.3: Migrate OverlayBackend to use ApplicationState

**Before** (`qml/OverlayBackend.py` - 697 lines):
```python
class OverlayBackend(QObject):
    def __init__(self):
        self._viewport = None
        self._visible_collectibles = []
        self._tracker = CollectionTracker()
```

**After** (slim adapter):
```python
class OverlayBackend(QObject):
    """
    Thin adapter: ApplicationState -> QML properties.
    Thread ownership: Qt main thread.
    """

    def __init__(self, state: ApplicationState):
        super().__init__()
        self._state = state

        # Connect to state changes
        state.viewport_changed.connect(self._on_viewport_changed)
        state.collectibles_changed.connect(self._on_collectibles_changed)

    @Slot(ViewportState)
    def _on_viewport_changed(self, viewport: ViewportState):
        # Update QML properties
        self.viewportXChanged.emit()
        self.viewportYChanged.emit()

    # Qt Properties delegate to ApplicationState
    def get_viewport_x(self) -> float:
        vp = self._state.current_viewport
        return vp.x if vp else 0.0

    viewportX = Property(float, get_viewport_x, notify=viewportXChanged)
```

#### Step 1.4: Update app_qml.py Initialization

**Before**:
```python
# Create state in multiple places
from api.state import state
backend = OverlayBackend()
tracker = CollectionTracker()
```

**After**:
```python
# Single ApplicationState initialization
from core.application_state import ApplicationState

# Create state (Qt main thread)
app_state = ApplicationState(app)

# Load immutable reference data
collectibles = load_collectibles()
app_state.set_collectibles(collectibles)

reference_map = load_map()
coord_transform = CoordinateTransform()
app_state.set_reference_data(reference_map, coord_transform)

# Set up tracker
tracker = CollectionTracker()
app_state.set_collection_tracker(tracker)

# Create backend adapter
backend = OverlayBackend(app_state)

# Connect capture service
capture_service.viewport_updated.connect(
    lambda x, y, w, h, conf: app_state.update_viewport(x, y, w, h, conf),
    Qt.QueuedConnection
)
```

### Testing Checklist

- [ ] Application starts without errors
- [ ] Collectibles load and display correctly
- [ ] Viewport updates from capture thread propagate to UI
- [ ] Collection tracker state persists
- [ ] No crashes when switching between views
- [ ] Memory usage stable (no leaks from duplicate state)

### Rollback Plan

If issues arise:
1. Keep `application_state.py` but don't remove old code yet
2. Gradually migrate one component at a time
3. Test each migration step independently

---

## Task 2: Extract PerformanceMonitor (Priority 1)

### Problem
`ContinuousCaptureService` handles metrics collection + capture loop + matching.

### Solution
Separate `PerformanceMonitor` wrapping `MetricsTracker`.

### Implementation

**Create**: `core/performance_monitor.py`

```python
"""
Performance monitoring and metrics aggregation.
Thread ownership: Capture background thread.
"""

from core.metrics import MetricsTracker


class PerformanceMonitor:
    """
    Aggregates performance metrics from capture/match operations.
    Thread-safe: Can be read from Flask HTTP thread via get_stats().
    """

    def __init__(self):
        self._metrics = MetricsTracker()

    def record_frame(self, timing: dict, quality: dict):
        """
        Record frame metrics.
        Thread: Capture background thread.

        Args:
            timing: {capture_ms, match_ms, overlay_ms, total_ms}
            quality: {confidence, inliers, cascade_level}
        """
        self._metrics.record_frame_timing(**timing)
        self._metrics.record_match_quality(**quality)

    def get_stats(self) -> dict:
        """
        Get aggregated statistics.
        Thread: Any thread (thread-safe via internal lock).

        Returns:
            Comprehensive stats dict for /stats endpoint.
        """
        return self._metrics.get_stats()
```

**Update `ContinuousCaptureService`**:
```python
class ContinuousCaptureService:
    def __init__(self, ...):
        self.performance_monitor = PerformanceMonitor()

    def _capture_loop(self):
        # ... capture and match ...

        self.performance_monitor.record_frame(
            timing={'capture_ms': capture_ms, ...},
            quality={'confidence': confidence, ...}
        )
```

**Update `api/routes.py`**:
```python
@app.route('/stats')
def get_stats():
    return jsonify(state.capture_service.performance_monitor.get_stats())
```

---

## Task 3: Extract CollectiblesFilter (Priority 1)

### Problem
Collectibles filtering logic in `OverlayBackend` (UI layer).

### Solution
Pure function for filtering collectibles by viewport.

### Implementation

**Create**: `core/collectibles_filter.py`

```python
"""
Filter collectibles by viewport visibility.
Pure functions - no state, no threads.
"""

from typing import List, Dict
from models.collectible import Collectible


def filter_visible_collectibles(
    all_collectibles: List[Collectible],
    viewport_x: float,
    viewport_y: float,
    viewport_width: float,
    viewport_height: float,
    tracker_visibility: Dict[str, bool]
) -> List[Dict]:
    """
    Filter collectibles visible in current viewport.

    Pure function - no side effects, safe to call from any thread.

    Args:
        all_collectibles: All collectibles in detection space
        viewport_x, viewport_y: Viewport top-left in detection space
        viewport_width, viewport_height: Viewport size in detection space
        tracker_visibility: Which categories are visible per tracker

    Returns:
        List of dicts with screen coordinates + metadata
    """
    visible = []

    # Calculate screen transform
    scale_x = 1920.0 / viewport_width
    scale_y = 1080.0 / viewport_height

    for collectible in all_collectibles:
        # Check category visibility (tracker filter)
        if not tracker_visibility.get(collectible.type, True):
            continue

        # Check if in viewport bounds (detection space)
        if not (viewport_x <= collectible.x <= viewport_x + viewport_width and
                viewport_y <= collectible.y <= viewport_y + viewport_height):
            continue

        # Transform to screen coordinates
        screen_x = (collectible.x - viewport_x) * scale_x
        screen_y = (collectible.y - viewport_y) * scale_y

        visible.append({
            'x': screen_x,
            'y': screen_y,
            'type': collectible.type,
            'name': collectible.name,
            'collected': collectible.collected
        })

    return visible
```

**Usage in OverlayBackend**:
```python
from core.collectibles_filter import filter_visible_collectibles

class OverlayBackend(QObject):
    def _on_viewport_changed(self, viewport: ViewportState):
        visible = filter_visible_collectibles(
            self._state.get_all_collectibles(),
            viewport.x, viewport.y, viewport.width, viewport.height,
            self._state.collection_tracker.get_visibility()
        )
        # Update QML property
        self._visible_collectibles = visible
        self.visibleCollectiblesChanged.emit()
```

---

## Task 4: Break Up ContinuousCaptureService (Priority 2)

### Problem
990 lines, handles capture + matching + tracking + metrics + test collection.

### Solution
Extract to 4 focused services.

### High-Level Structure

```
ContinuousCaptureService (200 lines - orchestration only)
├── CaptureLoop (150 lines - timing, FPS, frame scheduling)
├── MatchingCoordinator (250 lines - matcher, tracker, fallback logic)
├── PerformanceMonitor (done above)
└── TestDataCollector (already extracted)
```

### Implementation Order

1. **CaptureLoop** - Extract timing and frame scheduling
2. **MatchingCoordinator** - Extract matching logic
3. **Slim down ContinuousCaptureService** - Keep only orchestration

**Note**: This is the most complex refactoring. Detailed steps are in `docs/CONTINUOUS_CAPTURE_REFACTOR.md` (to be created).

---

## Success Metrics

### Before Refactoring
- Largest file: `continuous_capture.py` - 990 lines
- State stores: 3 overlapping (OverlayState, OverlayBackend, ContinuousCaptureService)
- Test coverage: ~10% (no mocks for Qt components)

### After Refactoring
- Largest file: <300 lines
- State stores: 1 (`ApplicationState`)
- Test coverage: >40% (business logic testable without Qt)
- Complexity: 50% reduction (Cyclomatic complexity, file lengths)

---

## Risk Mitigation

### High-Risk Changes
- ApplicationState migration (touches all components)
- ContinuousCaptureService breakup (hot code path)

### Mitigation Strategies
1. **Feature flag**: Add `USE_NEW_STATE = True` toggle
2. **Incremental migration**: One component at a time
3. **Parallel implementation**: Keep old code until new code proven
4. **Comprehensive testing**: Test each step before next
5. **Performance monitoring**: Track /stats before and after

### Rollback Triggers
- FPS drops below 5 fps average
- Match confidence drops >10%
- Memory usage increases >20%
- Crash rate >1 per hour

---

## Timeline

### Week 1: ApplicationState (5 days)
- Day 1: Create ApplicationState class
- Day 2: Migrate api/state.py
- Day 3: Migrate OverlayBackend
- Day 4: Update app_qml.py, test integration
- Day 5: Bug fixes, performance validation

### Week 2: Service Extraction (5 days)
- Day 1: Extract PerformanceMonitor, CollectiblesFilter
- Day 2-3: Extract CaptureLoop
- Day 4-5: Extract MatchingCoordinator, slim ContinuousCaptureService

### Week 3: Polish (2 days)
- Day 1: Documentation, docstrings
- Day 2: Performance tuning, final validation

**Total**: 12 working days (~2.5 weeks)

---

## Next Steps

1. **Review this roadmap** - Confirm approach
2. **Schedule refactoring time** - Block 2-3 weeks
3. **Create feature branch** - `refactor/unified-state`
4. **Start with Task 1** - ApplicationState (highest value)
5. **Test thoroughly** - Each task before moving to next

---

## References

- [Threading Model](THREADING.md) - Thread ownership rules
- [Architecture Review](../architecture_review_2024.txt) - Original recommendations
- [CLAUDE.md](../CLAUDE.md) - Project architecture overview
