#!/usr/bin/env python3
"""
RDO Map Overlay - QML Version
Pixel-perfect collectible tracking overlay with QML UI
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import SERVER, MAP_DIMENSIONS
from core.map.coordinate_transform import CoordinateTransform
from core.collectibles.collectibles_repository import CollectiblesRepository
from core.capture.continuous_capture import ContinuousCaptureService
from core.interactions.click_observer import ClickObserver
from core.state.application_state import ApplicationState
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching import SimpleMatcher
import cv2

# QML imports
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

# Import custom QML types
from qml.CollectibleRendererSceneGraph import CollectibleRendererSceneGraph
from qml.CollectibleRendererPainted import CollectibleRendererPainted
from qml.OverlayBackend import OverlayBackend
from qml.ClickThroughManagerFixed import ClickThroughManager, GlobalHotkeyManager

# Import Windows capture
try:
    from windows_capture import WindowsCapture
    import win32gui
    CAPTURE_AVAILABLE = True
except ImportError:
    print("Warning: windows-capture not available - continuous capture disabled")
    CAPTURE_AVAILABLE = False


def _find_rdr2_window():
    """Find RDR2 window by title."""
    if not CAPTURE_AVAILABLE:
        return None

    windows = []
    def enum_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.lower() == 'red dead redemption 2':
                windows.append(title)
    win32gui.EnumWindows(enum_handler, None)
    return windows[0] if windows else None


def initialize_system(app=None):
    """Initialize the overlay system

    Args:
        app: QGuiApplication instance (required for QObject-based capture service)
    """
    print("RDO Map Overlay (QML) - Initializing...")

    # Create unified application state (Qt main thread)
    state = ApplicationState(parent=app)

    try:
        # Initialize coordinate transform
        print("Initializing coordinate system...")
        state.coord_transform = CoordinateTransform()

        # Load map and features (with caching for fast startup)
        print("Loading map...")
        from config.paths import CachePaths
        from core.map.feature_cache import FeatureCache

        hq_source = CachePaths.find_hq_map_source()
        if not hq_source or not hq_source.exists():
            print("ERROR: HQ map not found!")
            return None

        # Initialize feature cache
        cache_params = {
            'scale': MAP_DIMENSIONS.DETECTION_SCALE,
            'max_features': 0,  # No limit - use all features
            'use_spatial_distribution': True,
            'spatial_grid_size': 50
        }

        cache_paths = CachePaths()
        feature_cache = FeatureCache(cache_paths.CACHE_DIR)
        cached_data = feature_cache.load(hq_source, cache_params)

        if cached_data:
            print("[CACHE] Loading preprocessed map and features from cache...")
            detection_map, keypoint_data, descriptors = cached_data
            # Reconstruct keypoints
            keypoints = FeatureCache.keypoints_from_data(keypoint_data)
            print(f"[CACHE] Loaded {len(keypoints)} features from cache")
            print(f"Detection map: {detection_map.shape[1]}x{detection_map.shape[0]}")
        else:
            print("[CACHE] No valid cache found, computing features...")
            hq_map = cv2.imread(str(hq_source))
            h, w = hq_map.shape[:2]
            print(f"HQ map loaded: {w}x{h}")

            from core.matching.image_preprocessing import preprocess_with_resize
            detection_map = preprocess_with_resize(hq_map, scale=MAP_DIMENSIONS.DETECTION_SCALE)
            print(f"Detection map: {detection_map.shape[1]}x{detection_map.shape[0]}")

            # Compute features (will be cached)
            detector = cv2.AKAZE_create()
            keypoints, descriptors = detector.detectAndCompute(detection_map, None)
            print(f"Detected {len(keypoints)} features")

            # Save to cache
            feature_cache.save(hq_source, cache_params, detection_map, keypoints, descriptors)

        state.full_map = detection_map

        # Initialize matcher with cached features
        print("Initializing Cascade Scale Matcher...")
        base_matcher = SimpleMatcher(
            max_features=0,
            ratio_test_threshold=0.75,
            min_inliers=5,
            min_inlier_ratio=0.5,
            ransac_threshold=5.0,
            use_spatial_distribution=True,
            spatial_grid_size=50,
            max_screenshot_features=300,
            use_flann=False,
            use_gpu=True
        )

        # Set features directly instead of recomputing
        from matching.spatial_keypoint_index import SpatialKeypointIndex
        base_matcher.kp_map = keypoints
        base_matcher.desc_map = descriptors
        print(f"Reference map features: {len(base_matcher.kp_map)}")

        # Build spatial index
        print("Building spatial index for ROI filtering...")
        base_matcher.spatial_index = SpatialKeypointIndex(base_matcher.kp_map)
        print(f"Spatial index ready for {len(base_matcher.kp_map)} keypoints")

        cascade_levels = [
            ScaleConfig(0.25, 100, 0.50, 6, 12, "Fast (25%)"),
            ScaleConfig(0.5, 150, 0.45, 5, 10, "Reliable (50%)"),
            ScaleConfig(1.0, 300, 0.0, 5, 8, "Full (100%)")
        ]

        state.matcher = CascadeScaleMatcher(
            base_matcher,
            cascade_levels,
            use_scale_prediction=False,
            verbose=False,
            enable_roi_tracking=True
        )

        # Load collectibles
        print("Loading collectibles...")
        collectibles = CollectiblesRepository.load(state.coord_transform)
        state.set_collectibles(collectibles)

        # Initialize continuous capture
        if CAPTURE_AVAILABLE and SERVER.CONTINUOUS_CAPTURE:
            print("Initializing continuous capture...")
            window_title = _find_rdr2_window()
            if not window_title:
                print("ERROR: RDR2 window not found!")
                state.capture_service = None
            else:
                import threading

                latest_frame = None
                frame_lock = threading.Lock()

                game_capture = WindowsCapture(
                    window_name=window_title,
                    cursor_capture=False,
                    minimum_update_interval=16
                )

                frame_count = 0

                @game_capture.event
                def on_frame_arrived(frame, capture_control):
                    nonlocal latest_frame, frame_count
                    with frame_lock:
                        latest_frame = frame.frame_buffer.copy()
                        frame_count += 1
                        if frame_count == 1:
                            print(f"[GameCapture] First frame received ({frame.frame_buffer.shape})")

                @game_capture.event
                def on_closed():
                    print("[GameCapture] Window closed")

                print(f"[GameCapture] Starting capture: {window_title}")
                game_capture.start_free_threaded()
                print("[GameCapture] Free-threaded capture started, waiting for frames...")

                def capture_screenshot():
                    try:
                        with frame_lock:
                            if latest_frame is None:
                                return None, "No frame captured yet"
                            img = cv2.cvtColor(latest_frame, cv2.COLOR_BGRA2BGR)
                            return img, None
                    except Exception as e:
                        return None, f"Capture error: {e}"

                def get_collectibles(viewport):
                    return state.get_visible_collectibles({
                        'map_x': viewport.x,
                        'map_y': viewport.y,
                        'map_w': viewport.width,
                        'map_h': viewport.height
                    })

                # Pass app as parent to ensure QObject is created with proper Qt context
                state.capture_service = ContinuousCaptureService(
                    matcher=state.matcher,
                    capture_func=capture_screenshot,
                    collectibles_func=get_collectibles,
                    target_fps=SERVER.CAPTURE_FPS,
                    parent=app
                )
                state.game_capture = game_capture
        else:
            state.capture_service = None

        state.is_initialized = True

        print("\nSystem initialized:")
        print(f"- Collectibles: {len(state.collectibles)}")
        print(f"- Map features: {len(state.matcher.base_matcher.kp_map)}")
        print(f"- Continuous capture: {'enabled' if state.capture_service else 'disabled'}")

        return state

    except Exception as e:
        print(f"\nInitialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main application entry point"""
    import signal
    import traceback

    # Singleton check: Only allow one instance using Windows named mutex
    try:
        import win32event
        import win32api
        import winerror

        # Create or open a named mutex (system-wide)
        mutex_name = "Global\\RDOOverlayMutex_{7F8C9D3E-4B2A-11EF-8C7D-0242AC120002}"
        mutex = win32event.CreateMutex(None, False, mutex_name)

        # Check if mutex already exists
        last_error = win32api.GetLastError()
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            print("\n[ERROR] Another instance of RDO Overlay is already running!")
            print("Please close the existing instance before starting a new one.\n")
            win32api.CloseHandle(mutex)
            sys.exit(1)

        # Keep mutex handle for lifetime of app (will auto-close on exit)
        # Store in variable to prevent garbage collection
        global _singleton_mutex
        _singleton_mutex = mutex

    except ImportError:
        print("[WARN] pywin32 not available - singleton check disabled")
    except Exception as e:
        print(f"[WARN] Singleton check failed: {e}")

    # CRITICAL: Set Qt environment variables BEFORE creating QApplication
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_SCALE_FACTOR'] = '1'

    # Enable threaded rendering for better performance
    os.environ['QSG_RENDER_LOOP'] = 'threaded'  # Use threaded render loop
    os.environ['QSG_INFO'] = '1'  # Enable scene graph debug info

    # CRITICAL: Configure OpenGL surface format BEFORE creating QApplication
    # This MUST be done before QGuiApplication is instantiated!
    from PySide6.QtGui import QSurfaceFormat
    format = QSurfaceFormat.defaultFormat()
    format.setSwapInterval(0)  # 0 = disable VSync, 1 = enable (default)
    format.setAlphaBufferSize(8)  # Enable alpha channel for transparent window rendering
    QSurfaceFormat.setDefaultFormat(format)
    print("[Main] OpenGL surface configured with alpha buffer for Scene Graph transparency")

    # Create Qt application (after surface format is configured)
    app = QGuiApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    try:
        # Initialize backend (pass app for QObject-based services)
        state = initialize_system(app)
        if state is None:
            print("\nFailed to initialize system. Exiting.")
            sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL ERROR] Exception during initialization:")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)

    # Start Flask API server in background thread
    print("Starting Flask API server...")
    from api.routes import create_app
    import threading

    flask_app, _ = create_app(state)

    def run_flask():
        flask_app.run(
            host=SERVER.HOST,
            port=SERVER.PORT,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"Flask API available at http://{SERVER.HOST}:{SERVER.PORT}")
    print(f"  - GET  /status - System health check")
    print(f"  - GET  /stats  - Performance statistics (last 10 minutes)")
    print(f"  - POST /start-test-collection - Start test data collection")
    print(f"  - POST /stop-test-collection - Stop test collection")

    # NOTE: Continuous capture will be started AFTER renderer is initialized (see below)

    # Register custom QML types
    qmlRegisterType(CollectibleRendererSceneGraph, "RDOOverlay", 1, 0, "CollectibleRendererSceneGraph")
    qmlRegisterType(CollectibleRendererPainted, "RDOOverlay", 1, 0, "CollectibleRendererPainted")

    # Create QML engine
    engine = QQmlApplicationEngine()

    # Create backend and expose to QML (pass app as parent for proper cleanup)
    backend = OverlayBackend(state, parent=app)
    backend.set_state(state)

    # Store backend reference in state for API access
    state.backend = backend

    # Create click-through manager (will be initialized after QML loads)
    click_through_manager = ClickThroughManager(parent=app)

    # Make backend and click-through manager available globally to QML
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("clickThroughManager", click_through_manager)

    # Connect continuous capture to backend
    if state.capture_service:
        # Direct connection - viewport is already a dict
        state.capture_service.viewport_updated.connect(backend.update_viewport)
        backend.update_status("Tracking", "#22c55e")

    # Start click observer for tracker interaction and panning detection
    def handle_click_observer_event(event, data):
        """Route click observer events to appropriate backend handlers"""
        if event == 'mouse-clicked':
            backend.handle_mouse_click(data['x'], data['y'], data['button'])
        elif event == 'mouse-button-state':
            backend.handle_mouse_button_state(data['left_down'], data['right_down'])

    click_observer = ClickObserver(emit_callback=handle_click_observer_event)
    click_observer.start()

    # Add QML import paths
    qml_dir = Path(__file__).parent / "qml"
    engine.addImportPath(str(qml_dir.parent))  # Parent dir for RDOOverlay module
    engine.addImportPath(str(qml_dir))  # qml dir for theme module

    # Setup global hotkeys (need window handle for QShortcut)
    # We'll get the window after QML loads

    try:
        # Connect to QML warnings for debugging
        engine.warnings.connect(lambda warnings: [print(f"[QML Warning] {w.toString()}") for w in warnings])

        # Load main QML file
        qml_file = qml_dir / "Overlay.qml"
        engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not engine.rootObjects():
            print("ERROR: Failed to load QML file!")
            print("Check QML warnings above for details")
            sys.exit(1)

        print("QML overlay launched successfully!")

        # Initialize click-through manager with the QML window
        root_window = engine.rootObjects()[0]
        click_through_manager.setWindow(root_window)
        click_through_manager.clickThroughChanged.connect(
            lambda enabled: print(f"[Overlay] Click-through: {'ENABLED' if enabled else 'DISABLED'}")
        )
        click_through_manager.start()
        print(f"[Main] Click-through manager initialized")

        # Trigger initial region update from QML now that manager is ready
        # Call QML function to update interactive regions
        root_window.updateInteractiveRegions()

        # Get reference to Painted renderer (GPU-accelerated QPainter) and store in backend
        painted_renderer = root_window.findChild(CollectibleRendererPainted, "spritesSceneGraph")
        if painted_renderer:
            backend.gl_renderer = painted_renderer
            print("[Main] QPainter renderer connected (GPU-accelerated)")
            backend._rebuild_collectibles_cache()

            # Start continuous capture AFTER renderer is fully initialized
            if state.capture_service:
                state.capture_service.start()
                print(f"[Main] Continuous capture started ({state.capture_service.target_fps} fps)")
        else:
            print("[ERROR] Could not find Painted renderer with objectName 'spritesSceneGraph'")
            print("[ERROR] Application cannot continue without renderer")
            app.exit(1)
            return

        # Setup global hotkeys using Windows RegisterHotKey API
        print("[Hotkeys] Registering system-wide hotkeys...")

        hotkey_manager = GlobalHotkeyManager(app)

        # Connect signals to backend actions
        hotkey_manager.f5Pressed.connect(backend.toggle_tracker)
        hotkey_manager.f6Pressed.connect(backend.refresh_data)
        # F7 removed - opacity is now fixed (panel opaque, collected items dimmed)
        hotkey_manager.f8Pressed.connect(backend.toggle_visibility)
        hotkey_manager.f9Pressed.connect(backend.force_alignment)
        hotkey_manager.ctrlQPressed.connect(app.quit)
        hotkey_manager.ctrlShiftCPressed.connect(backend.clear_collected)

        print("[Hotkeys] F5=Tracker | F6=Refresh | F8=Toggle | F9=Align | Ctrl+Q=Quit | Ctrl+Shift+C=Clear")
        print("[Hotkeys] Using system-wide hotkeys (work even when window is click-through)")

    except Exception as e:
        print(f"\n[FATAL ERROR] Exception during QML loading:")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(1)
    print("Press Ctrl+C to stop\n")

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\nShutting down...")
        if state.capture_service:
            state.capture_service.stop()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)

    # Allow Ctrl+C to work
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    try:
        sys.exit(app.exec())
    finally:
        print("\nShutting down...")
        if state.capture_service:
            print("Stopping continuous capture...")
            state.capture_service.stop()
        if 'click_observer' in locals():
            print("Stopping click observer...")
            click_observer.stop()


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise  # Re-raise sys.exit() calls
    except Exception as e:
        print(f"\n[UNCAUGHT EXCEPTION in main]")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
