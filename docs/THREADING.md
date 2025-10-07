# Threading Model

The RDO Overlay uses a **multi-threaded architecture** with three concurrent threads. This document defines thread ownership, boundaries, and communication rules.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Threads                       │
├─────────────────┬─────────────────┬──────────────────────────┤
│  Qt Main/Render │ Capture Thread  │  Flask HTTP Thread       │
│  (Primary)      │  (Background)   │  (HTTP Server)           │
└─────────────────┴─────────────────┴──────────────────────────┘
```

---

## Thread 1: Qt Main/Render Thread

### Ownership
- **QML UI** - All QML components and visual elements
- **Scene Graph** - GPU rendering pipeline (updatePaintNode)
- **OverlayBackend** - Python/QML bridge object
- **CollectionTracker** - User collection state
- **Qt Event Loop** - Processes events, signals, timers

### Entry Points
- `main()` in `app_qml.py`
- Qt event handlers (mouse, keyboard, timers)
- QML interactions (button clicks, property bindings)
- Signal handlers connected with `Qt.AutoConnection` or `Qt.QueuedConnection`

### Rules
1. **All Qt objects MUST be created with Qt main thread as parent**
2. **Scene Graph updates ONLY via `updatePaintNode()`**
   - Never modify Scene Graph from other threads
   - Qt automatically calls `updatePaintNode()` on render thread
3. **Use Signal/Slot for cross-thread communication**
   - Always use `Signal` from `PySide6.QtCore`
   - Connect with `Qt.QueuedConnection` for cross-thread
4. **Never block this thread**
   - No heavy computation
   - No blocking I/O
   - Keep frame budget <16ms for 60 FPS

### Owned Objects
```python
# Lives on Qt main thread
- QGuiApplication
- QQmlApplicationEngine
- OverlayBackend (QObject with Qt parent)
- CollectibleRendererSceneGraph (QQuickItem)
- CollectionTracker (QObject with Qt parent)
- All QML components
```

---

## Thread 2: Capture Background Thread

### Ownership
- **ContinuousCaptureService** - Main capture loop orchestrator
- **CascadeScaleMatcher** - AKAZE feature matching
- **TranslationTracker** - Motion-only tracking between AKAZE frames
- **MetricsTracker** - Performance statistics aggregation
- **Screenshot Capture** - MSS screen grabbing

### Entry Points
- `ContinuousCaptureService._capture_loop()` method
- Runs in dedicated thread created by `ContinuousCaptureService.start()`

### Rules
1. **Never call Qt UI methods directly**
   - Qt UI objects are not thread-safe
   - Use `Signal.emit()` to send data to Qt thread
2. **Emit signals for UI updates**
   - Signals automatically queue to Qt thread
   - Connection type: `Qt.QueuedConnection` (automatic for cross-thread)
3. **Read-only access to immutable reference data**
   - Can read: collectibles list, reference map, configuration
   - Safe because data never changes after initialization
4. **Lock-free communication via atomic dict assignment**
   - Python dict assignment is atomic with GIL
   - Used for latest viewport sharing

### Owned Objects
```python
# Lives on capture background thread
- ContinuousCaptureService (QObject but runs on background thread)
- CascadeScaleMatcher (pure Python, thread-isolated)
- TranslationTracker (pure Python, thread-isolated)
- MetricsTracker (thread-safe aggregator)
- mss.mss() screenshot grabber instance
```

### Communication Pattern
```python
# Capture thread emits signal
self.viewport_updated.emit(viewport_dict, collectibles_list)

# Qt thread receives via slot (queued connection)
@Slot(dict, list)
def _on_viewport_updated(self, viewport, collectibles):
    # Executes on Qt main thread
    self.renderer.set_viewport(...)
```

---

## Thread 3: Flask HTTP Server Thread

### Ownership
- **Flask Application** - HTTP server
- **API Routes** - `/stats`, `/status`, `/refresh-data`, etc.
- **HTTP Request Handlers** - Process incoming requests

### Entry Points
- `flask.run()` in background thread (started in `app_qml.py`)
- HTTP requests from external clients (curl, browser)

### Rules
1. **Read-only access to stats**
   - Can read: `MetricsTracker.get_stats()`
   - MetricsTracker is thread-safe (uses internal locks)
2. **Never modify application state**
   - Flask thread is observer-only
   - Any state changes must go through Qt signals
3. **Return snapshots, not live references**
   - Copy data before returning in HTTP response
   - Never return references to mutable objects
4. **Keep handlers fast**
   - Target <50ms response time
   - No blocking operations

### Owned Objects
```python
# Lives on Flask HTTP thread
- Flask app instance
- HTTP request/response objects
- OverlayState (shared, read-only from Flask)
```

### Safe Access Pattern
```python
# Safe: Read thread-safe stats
@app.route('/stats')
def get_stats():
    stats = state.metrics.get_stats()  # Thread-safe copy
    return jsonify(stats)

# Unsafe: Direct state modification
@app.route('/set-viewport')  # DO NOT DO THIS
def set_viewport():
    state.viewport = ...  # UNSAFE - race condition
```

---

## Thread-Safe Communication Patterns

### Pattern 1: Qt Signal/Slot (Preferred)

**Use Case**: Capture thread → Qt UI updates

```python
# Producer (Capture thread)
class ContinuousCaptureService(QObject):
    viewport_updated = Signal(dict, list)  # Thread-safe signal

    def _capture_loop(self):
        # Emitting signal is thread-safe
        self.viewport_updated.emit(viewport_dict, collectibles)

# Consumer (Qt main thread)
class OverlayBackend(QObject):
    def __init__(self):
        service.viewport_updated.connect(
            self._on_viewport_updated,
            Qt.QueuedConnection  # Explicit queued for clarity
        )

    @Slot(dict, list)
    def _on_viewport_updated(self, viewport, collectibles):
        # Executes on Qt main thread (safe)
        self.renderer.set_viewport(...)
```

### Pattern 2: Lock-Free Atomic Read

**Use Case**: Sharing latest viewport between threads

```python
# Writer (Capture thread)
class ContinuousCaptureService:
    def _capture_loop(self):
        # Python dict assignment is atomic with GIL
        self._last_viewport = viewport_dict  # Thread-safe write

# Reader (Qt thread)
class OverlayBackend:
    def get_current_viewport(self):
        # Reading dict reference is atomic
        return service._last_viewport  # Thread-safe read
```

**Requirements**:
- Single writer, multiple readers
- Write is simple assignment (no compound operations)
- Read is reference copy (no iteration)

### Pattern 3: Thread-Safe Metrics Collection

**Use Case**: Flask thread reading performance stats

```python
# Collector (Capture thread)
class MetricsTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = []

    def record(self, metric):
        with self._lock:
            self._metrics.append(metric)

# Reader (Flask thread)
@app.route('/stats')
def get_stats():
    # MetricsTracker.get_stats() uses internal lock
    return jsonify(metrics_tracker.get_stats())  # Thread-safe
```

---

## Anti-Patterns (DO NOT DO)

### ❌ Direct Qt UI Call from Background Thread

```python
# WRONG - Will crash or corrupt
def _capture_loop(self):  # Capture thread
    self.renderer.set_viewport(...)  # Qt object - NOT thread-safe!
```

**Fix**: Emit signal instead
```python
def _capture_loop(self):  # Capture thread
    self.viewport_updated.emit(viewport_dict)  # Signal is thread-safe
```

### ❌ Flask Thread Modifying State

```python
# WRONG - Race condition
@app.route('/set-config')
def set_config():
    state.config = new_config  # Multiple threads writing!
```

**Fix**: Make Flask read-only, use Qt signals for writes

### ❌ Blocking Qt Main Thread

```python
# WRONG - Freezes UI
@Slot()
def on_button_click(self):  # Qt main thread
    result = matcher.match(screenshot)  # Takes 50-100ms - BAD!
```

**Fix**: Offload to background thread
```python
@Slot()
def on_button_click(self):  # Qt main thread
    # Emit signal to capture thread to trigger match
    self.match_requested.emit()
```

### ❌ Iterating Shared Collections Without Lock

```python
# WRONG - Race condition if collection modified
for metric in metrics_tracker._metrics:  # Another thread may append!
    process(metric)
```

**Fix**: Copy first or use lock
```python
with metrics_tracker._lock:
    metrics_copy = list(metrics_tracker._metrics)
for metric in metrics_copy:  # Safe to iterate
    process(metric)
```

---

## Thread Lifecycle

### Startup Sequence

```python
def main():
    # 1. Create Qt application (Qt main thread)
    app = QGuiApplication(sys.argv)

    # 2. Initialize immutable reference data (main thread)
    collectibles = load_collectibles()  # Read-only after this
    matcher = create_matcher()

    # 3. Create background services (main thread, but will run on background)
    capture_service = ContinuousCaptureService(...)

    # 4. Connect cross-thread signals (main thread)
    capture_service.viewport_updated.connect(
        backend._on_viewport_updated,
        Qt.QueuedConnection
    )

    # 5. Start background capture thread
    capture_service.start()  # Spawns background thread

    # 6. Start Flask HTTP server (separate thread)
    flask_thread = threading.Thread(target=flask_app.run, daemon=True)
    flask_thread.start()

    # 7. Enter Qt event loop (main thread blocks here)
    sys.exit(app.exec())
```

### Shutdown Sequence

```python
def cleanup():
    # 1. Stop capture service (sets flag, thread exits on next iteration)
    capture_service.stop()

    # 2. Wait for capture thread to finish
    capture_service.wait()  # Join thread

    # 3. Flask thread is daemon, will terminate automatically

    # 4. Qt app exit (main thread continues after app.exec())
```

---

## Debugging Threading Issues

### Symptoms of Thread-Safety Bugs

1. **Random Crashes**
   - Qt objects accessed from wrong thread
   - Segfaults in Qt rendering code

2. **Data Corruption**
   - Partial updates (saw half-old, half-new data)
   - Inconsistent state across components

3. **Race Conditions**
   - Behavior changes based on timing
   - "Works on my machine" problems

4. **Deadlocks**
   - Application freezes
   - No crash, just stops responding

### Debugging Tools

1. **Enable Qt Thread Checker** (development mode)
```python
# Add to app_qml.py
import os
os.environ['QT_FATAL_WARNINGS'] = '1'  # Crash on thread violations
```

2. **Log Thread IDs**
```python
import threading
print(f"[{threading.current_thread().name}] Operation X")
```

3. **Verify Signal Connections**
```python
# Check connection type
capture_service.viewport_updated.connect(
    backend._on_viewport_updated,
    Qt.QueuedConnection  # Explicit queued for cross-thread
)
```

4. **Profile Lock Contention**
```python
# If performance degrades, check for lock contention
import cProfile
cProfile.run('app.exec()')
```

---

## Summary Checklist

### When Adding New Functionality

- [ ] Identify which thread owns the new component
- [ ] Document thread ownership in docstring
- [ ] Use Signal/Slot for cross-thread communication
- [ ] Never call Qt UI methods from background threads
- [ ] Never block Qt main thread with heavy computation
- [ ] Use locks for shared mutable state
- [ ] Prefer immutable data for cross-thread sharing
- [ ] Test with Qt thread checker enabled

### When Debugging Issues

- [ ] Check thread IDs in logs
- [ ] Verify signal connection types (QueuedConnection for cross-thread)
- [ ] Look for direct Qt object access from wrong thread
- [ ] Check for missing locks on shared mutable data
- [ ] Profile for lock contention
- [ ] Run with `QT_FATAL_WARNINGS=1`

---

## References

- **Qt Thread Basics**: https://doc.qt.io/qt-6/thread-basics.html
- **Qt Signal/Slot Thread Safety**: https://doc.qt.io/qt-6/threads-qobject.html
- **Python Threading**: https://docs.python.org/3/library/threading.html
- **Python GIL**: https://docs.python.org/3/glossary.html#term-global-interpreter-lock
