#!/usr/bin/env python3
"""
RDO Map Overlay - Main Application
Pixel-perfect collectible tracking overlay for Red Dead Online
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import SERVER, MAP_DIMENSIONS, SCREENSHOT
from core import CoordinateTransform, MapLoader, CollectiblesLoader
from core.continuous_capture import ContinuousCaptureService
from core.image_preprocessing import preprocess_for_matching
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching import SimpleMatcher
from api import OverlayState, create_app
import cv2

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
            if title and 'red dead redemption' in title.lower():
                windows.append(title)
    win32gui.EnumWindows(enum_handler, None)
    return windows[0] if windows else None


def initialize_system():
    """Initialize the overlay system"""
    print("RDO Map Overlay - Initializing...")

    state = OverlayState()

    try:
        # Initialize coordinate transform
        print("Initializing coordinate system...")
        state.coord_transform = CoordinateTransform()

        # Load map and preprocess with optimized resize-first order
        print("Loading map with optimized preprocessing (resize in grayscale)...")
        from config.paths import CachePaths
        hq_source = CachePaths.find_hq_map_source()
        if not hq_source:
            print("ERROR: Failed to find HQ map!")
            return None

        # Load as color, will convert to grayscale in preprocessing
        hq_map = cv2.imread(str(hq_source))
        h, w = hq_map.shape[:2]
        print(f"HQ map loaded: {w}x{h}")

        # Apply optimized preprocessing: resize in grayscale BEFORE posterization
        from core.image_preprocessing import preprocess_with_resize
        detection_map = preprocess_with_resize(hq_map, scale=MAP_DIMENSIONS.DETECTION_SCALE)
        print(f"Detection map preprocessed: {detection_map.shape[1]}x{detection_map.shape[0]}")

        # Cache for future use
        state.full_map = detection_map  # Store detection-scale map directly

        # Initialize Cascade Scale Matcher
        print("Initializing Cascade Scale Matcher...")

        # Create base matcher (BFMatcher is faster than FLANN for our use case)
        base_matcher = SimpleMatcher(
            max_features=0,  # Keep all features (101k)
            ratio_test_threshold=0.75,
            min_inliers=5,
            min_inlier_ratio=0.5,
            ransac_threshold=5.0,
            use_spatial_distribution=True,
            spatial_grid_size=50,
            max_screenshot_features=300,
            use_flann=False,  # BFMatcher is faster for binary descriptors
            use_gpu=True      # GPU acceleration for coarse matching (if available)
        )
        base_matcher.compute_reference_features(detection_map)

        # Create cascade with 3 levels (25% -> 50% -> 70% fallback)
        cascade_levels = [
            ScaleConfig(
                scale=0.25,
                max_features=100,
                min_confidence=0.50,
                min_inliers=6,
                min_matches=12,
                name="Fast (25%)"
            ),
            ScaleConfig(
                scale=0.5,
                max_features=150,
                min_confidence=0.45,
                min_inliers=5,
                min_matches=10,
                name="Reliable (50%)"
            ),
            ScaleConfig(
                scale=0.7,
                max_features=210,
                min_confidence=0.0,
                min_inliers=5,
                min_matches=8,
                name="Optimized (70%)"
            )
        ]

        state.matcher = CascadeScaleMatcher(base_matcher, cascade_levels, use_scale_prediction=False, verbose=False)

        # Load collectibles
        print("Loading collectibles...")
        collectibles = CollectiblesLoader.load(state.coord_transform)
        state.set_collectibles(collectibles)

        # Initialize continuous capture service if available
        if CAPTURE_AVAILABLE and SERVER.CONTINUOUS_CAPTURE:
            print("Initializing continuous capture...")

            # Find RDR2 window
            window_title = _find_rdr2_window()
            if not window_title:
                print("ERROR: RDR2 window not found!")
                state.capture_service = None
            else:
                # Create persistent capture session (like OBS)
                # This runs continuously and updates latest_frame in background
                import threading

                latest_frame = None
                frame_lock = threading.Lock()
                capture_active = True

                game_capture = WindowsCapture(window_name=window_title)

                @game_capture.event
                def on_frame_arrived(frame, capture_control):
                    nonlocal latest_frame
                    # Store latest frame (runs continuously, ~60fps from game)
                    with frame_lock:
                        latest_frame = frame.frame_buffer.copy()

                @game_capture.event
                def on_closed():
                    nonlocal capture_active
                    capture_active = False
                    print("Game capture closed")

                # Start capture ONCE - keeps running continuously like OBS
                print(f"Starting persistent capture for: {window_title}")
                game_capture.start_free_threaded()

                def capture_screenshot():
                    """Get latest frame from persistent capture (instant!)."""
                    try:
                        with frame_lock:
                            if latest_frame is None:
                                return None, "No frame captured yet"

                            # Convert BGRA to BGR
                            img = cv2.cvtColor(latest_frame, cv2.COLOR_BGRA2BGR)
                            return img, None

                    except Exception as e:
                        return None, f"Capture error: {e}"

                def get_collectibles(viewport):
                    """Get visible collectibles for viewport."""
                    return state.get_visible_collectibles({
                        'map_x': viewport.x,
                        'map_y': viewport.y,
                        'map_w': viewport.width,
                        'map_h': viewport.height
                    })

                # Pass socketio=None for now, will be set after create_app
                state.capture_service = ContinuousCaptureService(
                    matcher=state.matcher,
                    capture_func=capture_screenshot,
                    collectibles_func=get_collectibles,
                    target_fps=SERVER.CAPTURE_FPS,
                    socketio=None  # Will be set after create_app
                )
                state.game_capture = game_capture  # Store for cleanup
        else:
            state.capture_service = None
            if not CAPTURE_AVAILABLE:
                print("Continuous capture unavailable (missing windows-capture)")
            else:
                print("Continuous capture disabled in config")

        state.is_initialized = True

        print("\nSystem initialized:")
        print(f"- Collectibles: {len(state.collectibles)}")
        print(f"- Map features: {len(state.matcher.base_matcher.kp_map)}")
        cascade_scales = " -> ".join([f"{int(l.scale*100)}%" for l in cascade_levels])
        print(f"- Matcher: CascadeScaleMatcher ({cascade_scales})")
        print(f"- Continuous capture: {'enabled' if state.capture_service else 'disabled'}")

        return state
        
    except Exception as e:
        print(f"\nInitialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main application entry point"""
    state = initialize_system()

    if state is None:
        print("\nFailed to initialize system. Exiting.")
        sys.exit(1)

    # Start continuous capture service if available
    if state.capture_service:
        state.capture_service.start()
        print(f"Continuous capture started ({state.capture_service.target_fps} fps)")

    # Create Flask app with WebSocket support
    app, socketio = create_app(state)

    # Set socketio on capture service for push updates
    if state.capture_service:
        state.capture_service.socketio = socketio

    # Start server
    print(f"Server starting on http://{SERVER.HOST}:{SERVER.PORT}")
    print("Press Ctrl+C to stop\n")

    try:
        # Disable Flask request logging for performance
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        # Use socketio.run() instead of app.run() for WebSocket support
        socketio.run(
            app,
            host=SERVER.HOST,
            port=SERVER.PORT,
            debug=False,  # Disable debug mode
            allow_unsafe_werkzeug=True  # Suppress werkzeug warning
        )
    finally:
        # Stop capture service on shutdown
        if state.capture_service:
            print("\nStopping continuous capture...")
            state.capture_service.stop()


if __name__ == '__main__':
    main()
