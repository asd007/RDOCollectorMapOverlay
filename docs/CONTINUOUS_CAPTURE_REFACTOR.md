# ContinuousCaptureService Refactoring Plan

## Current State Analysis

**File**: `core/continuous_capture.py`
**Current size**: 990 lines
**Target size**: ~400 lines (orchestration only)
**Estimated effort**: 5 days

### Identified Responsibilities (11 major concerns)

1. **Capture Loop Orchestration** (lines 375-429)
   - Thread management
   - Main loop timing
   - Frame scheduling

2. **Frame Processing** (lines 430-790)
   - Screenshot capture
   - Frame deduplication (hash-based)
   - Map detection
   - Matching orchestration

3. **Matching Coordination** (lines 430-790)
   - Cascade matcher integration
   - ROI tracking (ViewportKalmanTracker)
   - Fallback detection (FallbackDetector)
   - Motion-only vs AKAZE decision

4. **Adaptive FPS Control** (lines 164-170, 231-280)
   - Processing time tracking
   - Target FPS adjustment
   - Min/max FPS constraints

5. **Performance Monitoring** (lines 215-216)
   - Already extracted to PerformanceMonitor ✅

6. **Test Data Collection** (lines 171-180, 339-373)
   - Already extracted to TestDataCollector ✅

7. **Drift Tracking** (lines 222-224)
   - Collectible position monitoring
   - Coordinate accuracy verification

8. **Pan Tracking** (lines 226-229, 966-990)
   - Viewport movement detection
   - Speed/acceleration calculation

9. **Cycle Change Detection** (lines 181-184, 816-833)
   - Periodic cycle reload
   - Collectibles refresh

10. **Stats Collection** (lines 187-208, 840-965)
    - Legacy stats dict (should delegate to PerformanceMonitor)

11. **Result Management** (lines 147-148, 160-161, 808-815)
    - Thread-safe result sharing
    - Viewport updates via Qt signals

---

## Proposed Architecture

```
ContinuousCaptureService (~400 lines)
├── CaptureLoop (~150 lines)
│   ├── Thread management
│   ├── Frame timing/scheduling
│   ├── Adaptive FPS control
│   └── Main loop orchestration
│
├── FrameProcessor (~200 lines)
│   ├── Screenshot capture wrapper
│   ├── Frame deduplication
│   ├── Map detection
│   └── Preprocessing
│
├── MatchingCoordinator (~250 lines)
│   ├── CascadeScaleMatcher wrapper
│   ├── ViewportKalmanTracker
│   ├── FallbackDetector
│   ├── ROI vs full search decision
│   └── Motion-only tracking
│
├── ViewportMonitor (~100 lines)
│   ├── Drift tracking
│   ├── Pan tracking
│   └── Coordinate accuracy stats
│
└── CycleManager (~50 lines)
    ├── Periodic cycle checks
    └── Collectibles reload
```

---

## Implementation Steps

### Step 1: Extract CaptureLoop (Est: 1.5 days)

**Create**: `core/capture_loop.py`

**Responsibilities:**
- Thread lifecycle (start/stop/wait)
- Frame timing and scheduling
- Adaptive FPS control
- FPS statistics

**Interface:**
```python
class CaptureLoop:
    def __init__(self, target_fps=5, min_fps=5, max_fps=None):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.running = False
        self.thread = None
        # FPS adaptation state
        self.processing_times = deque(maxlen=10)
        self.frames_since_fps_update = 0

    def start(self, process_frame_callback):
        """Start capture loop in background thread."""
        pass

    def stop(self):
        """Stop capture loop."""
        pass

    def wait(self):
        """Wait for thread to finish."""
        pass

    def adapt_fps(self, processing_time_ms):
        """Adjust target FPS based on processing time."""
        pass

    def _loop(self, process_frame_callback):
        """Main loop (runs in background thread)."""
        while self.running:
            frame_start = time.perf_counter()

            # Call processor
            processing_time_ms = process_frame_callback()

            # Adapt FPS
            self.adapt_fps(processing_time_ms)

            # Sleep for remaining frame interval
            elapsed = time.perf_counter() - frame_start
            sleep_time = max(0, self.frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
```

**Migration:**
- Move adaptive FPS logic from `_adapt_fps()` → `CaptureLoop.adapt_fps()`
- Move thread management from `start()/stop()` → `CaptureLoop`
- Move main loop from `_capture_loop()` → `CaptureLoop._loop()`

---

### Step 2: Extract FrameProcessor (Est: 1 day)

**Create**: `core/frame_processor.py`

**Responsibilities:**
- Capture wrapper (calls `capture_func`)
- Frame deduplication via hash
- Map visibility detection
- Preprocessing utilities

**Interface:**
```python
class FrameProcessor:
    def __init__(self, capture_func):
        self.capture_func = capture_func
        self.previous_frame_hash = None
        self.cached_result = None

    def capture_and_preprocess(self) -> tuple[np.ndarray, bool]:
        """
        Capture screenshot and check for duplicates.

        Returns:
            (screenshot, is_duplicate)
        """
        screenshot, error = self.capture_func()
        if error:
            return None, False

        # Check if duplicate
        frame_hash = self._compute_hash(screenshot)
        is_duplicate = (frame_hash == self.previous_frame_hash)
        self.previous_frame_hash = frame_hash

        return screenshot, is_duplicate

    def is_map_visible(self, screenshot) -> bool:
        """Check if RDO map is visible in screenshot."""
        from core.map_detector import is_map_visible
        return is_map_visible(screenshot)

    def _compute_hash(self, screenshot) -> str:
        """Compute perceptual hash for deduplication."""
        import hashlib
        return hashlib.md5(screenshot.tobytes()).hexdigest()
```

---

### Step 3: Extract MatchingCoordinator (Est: 1.5 days)

**Create**: `core/matching_coordinator.py`

**Responsibilities:**
- Orchestrate cascade matcher
- ROI tracking (ViewportKalmanTracker)
- Fallback detection
- Motion-only vs AKAZE decision
- Match result processing

**Interface:**
```python
class MatchingCoordinator:
    def __init__(self, matcher):
        self.matcher = matcher
        self.tracker = ViewportKalmanTracker(dt=0.2)
        self.fallback_detector = FallbackDetector()
        self.previous_viewport = None

    def match(self, screenshot) -> Dict:
        """
        Match screenshot to map using ROI tracking + fallback.

        Returns:
            Match result dict with viewport, confidence, timing, etc.
        """
        # Decide: ROI match or full search
        use_roi = self._should_use_roi()

        if use_roi:
            roi = self._calculate_roi()
            result = self._match_in_roi(screenshot, roi)

            # Check if ROI match succeeded
            if result and result['success']:
                self._update_tracker(result['viewport'])
                return result
            else:
                self._record_fallback('roi_match_failed')

        # Fallback: full search
        result = self._match_full(screenshot)
        if result and result['success']:
            self._update_tracker(result['viewport'])

        return result

    def _should_use_roi(self) -> bool:
        """Decide if ROI tracking is viable."""
        return not self.fallback_detector.should_fallback(...)

    def _calculate_roi(self) -> tuple:
        """Calculate ROI bounds from tracker prediction."""
        predicted = self.tracker.predict()
        # Return ROI bounds
        pass

    def _match_in_roi(self, screenshot, roi) -> Dict:
        """Match within ROI."""
        pass

    def _match_full(self, screenshot) -> Dict:
        """Full map search."""
        return self.matcher.match(screenshot)
```

---

### Step 4: Extract ViewportMonitor (Est: 0.5 days)

**Create**: `core/viewport_monitor.py`

**Responsibilities:**
- Drift tracking (collectible position variance)
- Pan tracking (viewport movement)
- Coordinate accuracy statistics

**Interface:**
```python
class ViewportMonitor:
    def __init__(self):
        self.drift_tracking_collectible = None
        self.drift_history = deque(maxlen=100)
        self.pan_history = deque(maxlen=100)

    def update(self, viewport, visible_collectibles):
        """Update drift and pan tracking."""
        self._update_drift_tracking(viewport, visible_collectibles)
        self._update_pan_tracking(viewport)

    def get_drift_stats(self) -> Dict:
        """Get drift statistics."""
        pass

    def get_pan_stats(self) -> Dict:
        """Get pan movement statistics."""
        pass
```

---

### Step 5: Extract CycleManager (Est: 0.5 days)

**Create**: `core/cycle_manager.py`

**Responsibilities:**
- Periodic cycle change detection
- Collectibles reload

**Interface:**
```python
class CycleManager:
    def __init__(self, check_interval=300):
        self.check_interval = check_interval
        self.last_check = time.time()

    def should_reload(self) -> bool:
        """Check if cycles should be reloaded."""
        if time.time() - self.last_check > self.check_interval:
            self.last_check = time.time()
            return True
        return False

    def reload_cycles(self, state):
        """Reload collectibles from Joan Ropke API."""
        from core import CollectiblesLoader
        collectibles = CollectiblesLoader.load(state.coord_transform)
        state.set_collectibles(collectibles)
```

---

### Step 6: Slim ContinuousCaptureService (Est: 1 day)

**Final Structure:**

```python
class ContinuousCaptureService(QObject):
    """
    Orchestrates capture, matching, and viewport updates.
    Delegates all complex logic to specialized components.

    Thread: Background thread via CaptureLoop
    Signals: viewport_updated (emitted to Qt main thread)
    """

    viewport_updated = Signal(dict, list)  # Qt signal (thread-safe)

    def __init__(self, matcher, capture_func, collectibles_func, target_fps=5, parent=None):
        super().__init__(parent)

        # Components (dependency injection)
        self.frame_processor = FrameProcessor(capture_func)
        self.matching_coordinator = MatchingCoordinator(matcher)
        self.performance_monitor = PerformanceMonitor()
        self.viewport_monitor = ViewportMonitor()
        self.cycle_manager = CycleManager()
        self.capture_loop = CaptureLoop(target_fps)

        # Minimal state
        self.collectibles_func = collectibles_func
        self.latest_result = None
        self.result_lock = threading.Lock()

    def start(self):
        """Start continuous capture."""
        self.capture_loop.start(self._process_frame)

    def stop(self):
        """Stop continuous capture."""
        self.capture_loop.stop()

    def _process_frame(self) -> float:
        """
        Process one frame (called by CaptureLoop).

        Returns:
            Processing time in milliseconds
        """
        frame_start = time.perf_counter()

        # 1. Capture
        screenshot, is_duplicate = self.frame_processor.capture_and_preprocess()
        if is_duplicate or screenshot is None:
            return 0  # Skip

        # 2. Check map visibility
        if not self.frame_processor.is_map_visible(screenshot):
            return 0  # Skip

        # 3. Match
        match_result = self.matching_coordinator.match(screenshot)
        if not match_result or not match_result['success']:
            return 0  # Failed

        # 4. Get collectibles
        viewport = match_result['viewport']
        collectibles = self.collectibles_func(viewport)

        # 5. Update monitoring
        self.viewport_monitor.update(viewport, collectibles)
        self.performance_monitor.record_frame(...)

        # 6. Emit signal to Qt main thread
        viewport_dict = {'x': viewport.x, 'y': viewport.y, ...}
        self.viewport_updated.emit(viewport_dict, collectibles)

        # 7. Check cycle reload
        if self.cycle_manager.should_reload():
            self.cycle_manager.reload_cycles(self.state)

        processing_time_ms = (time.perf_counter() - frame_start) * 1000
        return processing_time_ms
```

**Result**: ContinuousCaptureService reduced from 990 → ~400 lines

---

## Testing Strategy

### Unit Tests

1. **CaptureLoop**
   - Test FPS adaptation
   - Test thread lifecycle
   - Test frame timing

2. **FrameProcessor**
   - Test deduplication
   - Test hash computation
   - Test map detection

3. **MatchingCoordinator**
   - Test ROI calculation
   - Test fallback logic
   - Test tracker updates

4. **ViewportMonitor**
   - Test drift tracking
   - Test pan tracking

5. **CycleManager**
   - Test reload timing

### Integration Tests

- Test full pipeline: capture → process → match → emit
- Verify Qt signal emission (thread-safe)
- Test error handling and recovery

---

## Migration Checklist

- [ ] Create `core/capture_loop.py`
- [ ] Create `core/frame_processor.py`
- [ ] Create `core/matching_coordinator.py`
- [ ] Create `core/viewport_monitor.py`
- [ ] Create `core/cycle_manager.py`
- [ ] Update `ContinuousCaptureService.__init__()` to use components
- [ ] Update `ContinuousCaptureService._process_frame()` to delegate
- [ ] Remove deprecated methods from `ContinuousCaptureService`
- [ ] Update tests
- [ ] Verify application runs without errors
- [ ] Verify performance (FPS, timing, memory)

---

## Success Criteria

**Before:**
- 990 lines
- 11+ responsibilities
- Hard to test
- Difficult to modify

**After:**
- 400 lines (orchestration)
- 5 focused components (150-250 lines each)
- Each component testable in isolation
- Clear separation of concerns

**Performance:**
- No FPS degradation
- No memory leaks
- Maintain <100ms match times

---

## Risks & Mitigation

### Risk: Thread synchronization issues
**Mitigation**: Use Qt signals for all cross-thread communication

### Risk: Performance regression
**Mitigation**: Profile before/after, maintain same logic flow

### Risk: Breaking existing functionality
**Mitigation**: Incremental migration, test each component

---

## Timeline

**Week 1:** Components extraction (3 days)
- Day 1: CaptureLoop + FrameProcessor
- Day 2: MatchingCoordinator
- Day 3: ViewportMonitor + CycleManager

**Week 2:** Integration + testing (2 days)
- Day 4: Update ContinuousCaptureService, wire components
- Day 5: Testing, bug fixes, validation
