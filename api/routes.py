"""Flask API routes"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import numpy as np
import cv2
import time
from config import SERVER, SCREENSHOT
from api.state import OverlayState

# Check for screenshot capability
try:
    from windows_capture import WindowsCapture
    import win32gui
    SCREENSHOT_AVAILABLE = True
    GAME_CAPTURE = None  # Will be initialized on first capture
except ImportError:
    SCREENSHOT_AVAILABLE = False
    GAME_CAPTURE = None
    print("Warning: windows-capture not available - screenshot functionality disabled")


def find_rdr2_window():
    """Find RDR2 window by title"""
    windows = []

    def enum_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.lower() == 'red dead redemption 2':
                windows.append(title)

    win32gui.EnumWindows(enum_handler, None)
    return windows[0] if windows else None


def create_app(state: OverlayState):
    """Create Flask application with routes and WebSocket support"""
    app = Flask(__name__)

    if SERVER.CORS_ENABLED:
        CORS(app)

    # Initialize SocketIO for push updates with performance tuning
    socketio = SocketIO(
        app,
        cors_allowed_origins="*" if SERVER.CORS_ENABLED else None,
        async_mode='threading',  # Use threading for async operations
        ping_interval=25000,     # Reduce ping overhead (25s instead of 5s default)
        ping_timeout=60000,      # Allow longer timeout
        engineio_logger=False,   # Disable debug logging
        logger=False,            # Disable SocketIO logging for performance
        max_http_buffer_size=1024*1024  # 1MB buffer for large payloads
    )

    # Store socketio reference in state for continuous capture to emit events
    state.socketio = socketio

    # WebSocket connection handler - send initial state
    @socketio.on('connect')
    def handle_connect():
        """Send initial window state when client connects"""
        print(f"[WebSocket] Client connected")
        print(f"[WebSocket] state.game_focus_manager = {state.game_focus_manager}")
        if state.game_focus_manager:
            is_active = state.game_focus_manager.get_rdr2_state()
            print(f"[WebSocket] RDR2 state: {is_active}")
            emit('window-focus-changed', {
                'is_rdr2_active': is_active
            })
            print(f"[WebSocket] [OK] Sent initial RDR2 state: {is_active}")
        else:
            print(f"[WebSocket] [ERROR] ERROR: game_focus_manager is None, cannot send initial state!")
    
    @app.route('/status', methods=['GET'])
    def get_status():
        """Get system status"""
        # Handle both CascadeScaleMatcher and SimpleMatcher
        features = 0
        if state.matcher:
            if hasattr(state.matcher, 'base_matcher'):
                # CascadeScaleMatcher
                features = len(state.matcher.base_matcher.kp_map) if state.matcher.base_matcher.kp_map is not None else 0
            elif hasattr(state.matcher, 'kp_map'):
                # SimpleMatcher
                features = len(state.matcher.kp_map) if state.matcher.kp_map is not None else 0

        return jsonify({
            'ready': state.is_initialized,
            'matcher_ready': state.matcher is not None,
            'collectibles_loaded': len(state.collectibles),
            'screenshot_available': SCREENSHOT_AVAILABLE,
            'method': 'cascade_scale_matcher',
            'features': features
        })
    
    @app.route('/align-with-screenshot', methods=['POST'])
    def align_with_screenshot():
        """Capture screenshot and perform alignment"""
        # Sanity checks
        if not SCREENSHOT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Screenshot capability not available (mss package missing)'}), 400

        if not state.is_initialized:
            return jsonify({'success': False, 'error': 'System not initialized'}), 500

        if state.matcher is None:
            return jsonify({'success': False, 'error': 'Matcher not initialized'}), 500

        # Sanity check for reference features (handle both CascadeScaleMatcher and SimpleMatcher)
        if hasattr(state.matcher, 'base_matcher'):
            # CascadeScaleMatcher
            if state.matcher.base_matcher.kp_map is None:
                return jsonify({'success': False, 'error': 'Reference features not computed'}), 500
        elif hasattr(state.matcher, 'kp_map'):
            # SimpleMatcher
            if state.matcher.kp_map is None:
                return jsonify({'success': False, 'error': 'Reference features not computed'}), 500
        else:
            return jsonify({'success': False, 'error': 'Unknown matcher type'}), 500

        request_start = time.time()
        
        try:
            # Capture screenshot using Windows Graphics Capture
            screenshot_start = time.time()

            # Find RDR2 window
            window_title = find_rdr2_window()
            if not window_title:
                return jsonify({'success': False, 'error': 'RDR2 window not found'}), 404

            # Use persistent capture if available (much faster)
            if hasattr(state, 'game_capture') and state.game_capture:
                # Reuse persistent capture from continuous service
                img, error = state.capture_service.capture_func()
                if error:
                    return jsonify({'success': False, 'error': error}), 500
            else:
                # Fallback: one-time capture (slower, for manual alignment)
                captured_frame = None
                capture_error = None

                # Event-based capture
                import threading
                frame_event = threading.Event()
                capture = WindowsCapture(window_name=window_title)

                @capture.event
                def on_frame_arrived(frame, capture_control):
                    nonlocal captured_frame
                    captured_frame = frame.frame_buffer.copy()
                    capture_control.stop()
                    frame_event.set()

                @capture.event
                def on_closed():
                    frame_event.set()

                try:
                    capture.start_free_threaded()
                    frame_arrived = frame_event.wait(timeout=0.1)

                    if not frame_arrived or captured_frame is None:
                        return jsonify({'success': False, 'error': 'Timeout waiting for frame'}), 500

                except Exception as e:
                    capture_error = str(e)

                if capture_error:
                    return jsonify({'success': False, 'error': f'Capture failed: {capture_error}'}), 500

                # Convert BGRA to BGR
                img = cv2.cvtColor(captured_frame, cv2.COLOR_BGRA2BGR)

            screenshot_time = (time.time() - screenshot_start) * 1000

            # Perform matching with RAW image
            # Cascade matcher will handle: grayscale  ->  resize  ->  preprocess per level
            matching_start = time.time()
            result = state.matcher.match(img)  # Raw BGR image
            matching_time = (time.time() - matching_start) * 1000

            # Check if match succeeded
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': f"Matching failed: {result.get('error', 'Unknown error')}",
                    'timing': {'matching_ms': round(matching_time, 1)}
                }), 500

            total_time = (time.time() - request_start) * 1000

            # Prepare response (viewport-only, no collectibles)
            cascade_info = result.get('cascade_info', {})
            cascade_level = cascade_info.get('final_level', 'N/A')
            levels_tried = len(cascade_info.get('levels_tried', []))

            response = {
                'success': True,
                'viewport': result.get('viewport', {}),
                'timing': {
                    'screenshot_ms': round(screenshot_time, 1),
                    'matching_ms': round(matching_time, 1),
                    'total_ms': round(total_time, 1)
                },
                'quality': {
                    'confidence': f"{result['confidence']*100:.1f}%",
                    'inliers': result['inliers']
                }
            }

            # Add cascade info if available
            if cascade_info:
                response['cascade'] = {
                    'level_used': cascade_level,
                    'levels_tried': levels_tried,
                    'roi_used': cascade_info.get('roi_used', False),
                    'prediction_used': cascade_info.get('prediction_used', False)
                }

                # Add motion prediction details if available
                motion_pred = cascade_info.get('motion_prediction')
                if motion_pred:
                    response['cascade']['motion_prediction'] = motion_pred

            return jsonify(response)

        except Exception as e:
            # Silent error handling
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/reset-tracking', methods=['POST'])
    def reset_tracking():
        """Reset cascade matcher tracking state"""
        if state.matcher and hasattr(state.matcher, 'last_viewport'):
            state.matcher.last_viewport = None
            state.matcher.last_confidence = 0.0
            state.matcher.last_screenshot = None
        return jsonify({'success': True})
    
    @app.route('/refresh-data', methods=['POST'])
    def refresh_data():
        """Refresh collectibles data"""
        try:
            from core import CollectiblesLoader
            collectibles = CollectiblesLoader.load(state.coord_transform)
            state.set_collectibles(collectibles)
            return jsonify({'success': True, 'collectibles': len(collectibles)})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/collectibles', methods=['GET'])
    def get_collectibles():
        """
        Get ALL collectibles with map coordinates for client-side rendering.
        Frontend fetches this once and transforms positions based on viewport.

        Returns:
            {
                success: bool,
                collectibles: [
                    {
                        map_x: float,  // Detection space coordinates
                        map_y: float,
                        t: str,        // type (shortened)
                        n: str,        // name (shortened)
                        h: str,        // help text (optional)
                        v: str         // video link (optional)
                    }
                ],
                count: int
            }
        """
        try:
            # Return all collectibles with map coordinates
            collectibles_data = []
            for col in state.collectibles:
                item = {
                    'map_x': col.x,  # Detection space X (x/y are already detection coords)
                    'map_y': col.y,  # Detection space Y
                    't': col.type,   # Type
                    'n': col.name    # Name
                }

                # Optional fields
                if col.help:
                    item['h'] = col.help
                if col.video:
                    item['v'] = col.video

                collectibles_data.append(item)

            return jsonify({
                'success': True,
                'collectibles': collectibles_data,
                'count': len(collectibles_data)
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/get-latest-match', methods=['GET'])
    def get_latest_match():
        """
        Get latest match result from continuous capture service.
        Frontend polls this endpoint instead of requesting screenshots.

        Returns:
            {
                success: bool,
                collectibles: List (empty if map not open or none in view),
                error: str (if success=false),
                viewport: Dict (if success),
                stats: Dict (performance metrics)
            }
        """
        if not state.capture_service:
            return jsonify({
                'success': False,
                'error': 'Continuous capture not available',
                'collectibles': []
            })

        result = state.capture_service.get_latest_result()

        if result is None:
            # No results yet (service just started)
            return jsonify({
                'success': False,
                'error': 'No capture data yet',
                'collectibles': []
            })

        # Return result as-is (already formatted correctly)
        return jsonify(result)

    @app.route('/start-test-collection', methods=['POST'])
    def start_test_collection():
        """Start collecting test data for slow frames."""
        if not state.capture_service:
            return jsonify({
                'success': False,
                'error': 'Continuous capture not available'
            }), 503

        output_dir = request.json.get('output_dir', 'tests/test_data') if request.json else 'tests/test_data'
        max_per_zoom = request.json.get('max_per_zoom', 3) if request.json else 3

        state.capture_service.enable_test_collection(output_dir, max_per_zoom=max_per_zoom)

        return jsonify({
            'success': True,
            'message': f'Test collection enabled - will save up to {max_per_zoom} samples per zoom level',
            'output_dir': output_dir,
            'max_per_zoom': max_per_zoom,
            'expected_times': state.capture_service.expected_times,
            'deviation_threshold': state.capture_service.deviation_threshold
        })

    @app.route('/stop-test-collection', methods=['POST'])
    def stop_test_collection():
        """Stop test collection and export manifest."""
        if not state.capture_service:
            return jsonify({
                'success': False,
                'error': 'Continuous capture not available'
            }), 503

        stats = state.capture_service.disable_test_collection()

        return jsonify({
            'success': True,
            'message': 'Test collection stopped and manifest exported',
            'stats': stats
        })

    @app.route('/test-collection-stats', methods=['GET'])
    def get_test_collection_stats():
        """Get test collection statistics."""
        if not state.capture_service or not state.capture_service.test_collector:
            return jsonify({
                'success': False,
                'error': 'Test collection not active'
            }), 404

        stats = state.capture_service.test_collector.get_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'collecting': state.capture_service.collect_test_data
        })

    @app.route('/profiling-stats', methods=['GET'])
    def get_profiling_stats():
        """
        Get comprehensive profiling statistics from continuous capture.

        Returns performance metrics including:
        - Backend FPS (actual capture rate, target vs achieved)
        - Frame breakdown (motion-only vs AKAZE, skipped, failed)
        - Latency stats (mean, median, P95, best, worst)
        - Drift tracking (position consistency of one collectible)
        - Pan tracking (speed, acceleration, movement classification)
        - Match quality (confidence, inliers)
        - Timing breakdown
        """
        if not state.capture_service:
            return jsonify({
                'error': 'Continuous capture not available'
            }), 503

        # Use the new comprehensive stats method
        return jsonify(state.capture_service._get_stats())

    return app, socketio
