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

    # Initialize SocketIO for push updates
    socketio = SocketIO(app, cors_allowed_origins="*" if SERVER.CORS_ENABLED else None)

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

            # Get visible collectibles
            overlay_start = time.time()
            collectibles = state.get_visible_collectibles(result)
            overlay_time = (time.time() - overlay_start) * 1000
            
            total_time = (time.time() - request_start) * 1000

            # Prepare response (no logging for performance)
            cascade_info = result.get('cascade_info', {})
            cascade_level = cascade_info.get('final_level', 'N/A')
            levels_tried = len(cascade_info.get('levels_tried', []))

            response = {
                'success': True,
                'collectibles': collectibles,
                'timing': {
                    'screenshot_ms': round(screenshot_time, 1),
                    'matching_ms': round(matching_time, 1),
                    'overlay_ms': round(overlay_time, 1),
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
                    'levels_tried': levels_tried
                }

            return jsonify(response)

        except Exception as e:
            # Silent error handling
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/reset-tracking', methods=['POST'])
    def reset_tracking():
        """Reset tracking state (currently no-op as tracking removed)"""
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
        Get detailed profiling statistics from continuous capture.
        ONLY includes stats from successful matches (failures excluded).

        Returns performance metrics including:
        - Frontend FPS (what user experiences on successful matches)
        - Timing breakdown (capture, matching, overlay)
        - Match quality (confidence, inliers)
        - Cascade level usage
        """
        if not state.capture_service:
            return jsonify({
                'error': 'Continuous capture not available'
            }), 503

        stats = state.capture_service.stats

        # Build comprehensive stats response (only successful matches)
        capture_times = list(stats['capture_times'])
        match_times = list(stats['match_times'])
        overlay_times = list(stats['overlay_times'])
        total_times = list(stats['total_times'])
        confidences = list(stats['confidences'])
        inliers = list(stats['inliers'])

        successful_matches = len(match_times)
        success_rate = (successful_matches / max(1, stats['total_frames'])) * 100

        # Count cascade level usage
        cascade_counts = {}
        for level in stats['cascade_levels_used']:
            cascade_counts[level] = cascade_counts.get(level, 0) + 1

        # Get exception stats
        exceptions = list(stats['exceptions']) if 'exceptions' in stats else []
        exception_count = len(exceptions)

        duplicate_frames = stats.get('duplicate_frames', 0)
        duplicate_rate = (duplicate_frames / max(1, stats['total_frames'])) * 100

        response = {
            'note': 'Stats include ONLY successful matches (failures excluded)',
            'total_frames': stats['total_frames'],
            'successful_matches': successful_matches,
            'no_map_detected': stats['no_map_detected'],
            'duplicate_frames': duplicate_frames,
            'duplicate_rate': duplicate_rate,
            'success_rate': success_rate,
            'frontend_fps': {
                'mean': 1000 / np.mean(total_times) if total_times else 0,
                'median': 1000 / np.median(total_times) if total_times else 0,
                'p95': 1000 / np.percentile(total_times, 95) if total_times else 0
            },
            'timing_ms': {
                'capture_mean': np.mean(capture_times) if capture_times else 0,
                'capture_median': np.median(capture_times) if capture_times else 0,
                'match_mean': np.mean(match_times) if match_times else 0,
                'match_median': np.median(match_times) if match_times else 0,
                'overlay_mean': np.mean(overlay_times) if overlay_times else 0,
                'total_mean': np.mean(total_times) if total_times else 0,
                'total_median': np.median(total_times) if total_times else 0,
                'total_p95': np.percentile(total_times, 95) if total_times else 0
            },
            'match_quality': {
                'confidence_mean': float(np.mean(confidences)) if confidences else 0,
                'confidence_median': float(np.median(confidences)) if confidences else 0,
                'inliers_mean': float(np.mean(inliers)) if inliers else 0,
                'inliers_median': float(np.median(inliers)) if inliers else 0
            },
            'cascade_levels': cascade_counts,
            'exceptions': {
                'count': exception_count,
                'recent': exceptions  # Last 10 exceptions with timestamps and tracebacks
            }
        }

        return jsonify(response)

    return app, socketio
