"""Flask API routes - minimal version for Qt/QML overlay"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from config import SERVER
from api.state import OverlayState


def create_app(state: OverlayState):
    """
    Create Flask application with minimal routes.

    Qt/QML overlay uses direct Python calls via OverlayBackend,
    so most Electron routes are not needed.
    """
    app = Flask(__name__)

    if SERVER.CORS_ENABLED:
        CORS(app)

    @app.route('/status', methods=['GET'])
    def get_status():
        """
        System health check.

        Returns:
            ready: bool - System initialization complete
            matcher_ready: bool - Cascade matcher initialized
            collectibles_loaded: int - Number of collectibles loaded
            capture_ready: bool - Continuous capture running
        """
        return jsonify({
            'ready': state.is_initialized,
            'matcher_ready': state.matcher is not None,
            'collectibles_loaded': len(state.collectibles),
            'capture_ready': state.capture_service is not None and state.capture_service.running
        })

    @app.route('/stats', methods=['GET'])
    def get_stats():
        """
        Get comprehensive performance statistics from last 10 minutes.

        Returns:
            session: Session-wide metrics (uptime, total frames, FPS)
            window: Time-windowed metrics (frames in window, FPS)
            fps_breakdown: Capture/Processing/Rendering FPS breakdown
            frame_breakdown: Motion/AKAZE/skipped/failed counts and percentages
            timing: Mean/median/P95/P99/min/max for capture/matching/overlay/total
            quality: Confidence and inlier statistics
            cascade_levels: Scale usage distribution
            movement: Phase correlation movement statistics
        """
        if not state.capture_service:
            return jsonify({
                'error': 'Continuous capture not available'
            }), 503

        # Get base stats from metrics tracker
        stats = state.capture_service.metrics.get_statistics()

        # Add backend stats if available
        if hasattr(state, 'backend') and state.backend:
            stats['backend'] = state.backend.get_backend_stats()
        else:
            stats['backend'] = {'error': 'Backend not initialized'}

        # Add FPS breakdown (capture + processing pipeline)
        # Capture FPS = 1000 / mean(capture_ms)
        # Processing FPS = 1000 / mean(match_ms)
        # Overall FPS = 1000 / mean(total_ms)
        timing = stats.get('timing', {})
        capture_mean = timing.get('capture', {}).get('mean', 0)
        match_mean = timing.get('matching', {}).get('mean', 0)
        total_mean = timing.get('total', {}).get('mean', 0)

        # Get rendering FPS from backend (updated by CollectibleCanvas)
        rendering_fps = 0
        if hasattr(state, 'backend') and state.backend:
            rendering_fps = state.backend.get_render_fps()

        stats['fps_breakdown'] = {
            'capture_fps': round(1000 / capture_mean, 1) if capture_mean > 0 else 0,
            'processing_fps': round(1000 / match_mean, 1) if match_mean > 0 else 0,
            'overall_fps': round(1000 / total_mean, 1) if total_mean > 0 else 0,
            'rendering_fps': round(rendering_fps, 1)
        }

        return jsonify(stats)

    # Test data collection endpoints (development only)
    @app.route('/start-test-collection', methods=['POST'])
    def start_test_collection():
        """Start collecting test data for slow frames (development only)."""
        if not state.capture_service:
            return jsonify({
                'success': False,
                'error': 'Continuous capture not available'
            }), 503

        output_dir = request.json.get('output_dir', 'tests/data') if request.json else 'tests/data'
        max_per_zoom = request.json.get('max_per_zoom', 3) if request.json else 3

        state.capture_service.enable_test_collection(output_dir, max_per_zoom=max_per_zoom)

        return jsonify({
            'success': True,
            'message': f'Test collection enabled - will save up to {max_per_zoom} samples per zoom level',
            'output_dir': output_dir,
            'max_per_zoom': max_per_zoom
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

    @app.route('/test-viewport', methods=['POST'])
    def set_test_viewport():
        """Set a synthetic viewport for testing (development only)."""
        if not hasattr(state, 'backend') or not state.backend:
            return jsonify({
                'success': False,
                'error': 'Backend not initialized'
            }), 503

        # Default viewport: center of map
        viewport = {
            'x': request.json.get('x', 5000) if request.json else 5000,
            'y': request.json.get('y', 4000) if request.json else 4000,
            'width': request.json.get('width', 2000) if request.json else 2000,
            'height': request.json.get('height', 1500) if request.json else 1500
        }

        state.backend.update_viewport(viewport)

        return jsonify({
            'success': True,
            'viewport': viewport,
            'message': 'Test viewport set successfully'
        })

    @app.route('/debug-viewport', methods=['GET'])
    def debug_viewport():
        """Get current viewport state for debugging."""
        if not hasattr(state, 'backend') or not state.backend:
            return jsonify({
                'success': False,
                'error': 'Backend not initialized'
            }), 503

        viewport = state.backend._viewport
        visible_count = len(state.backend._visible_collectibles)

        return jsonify({
            'success': True,
            'viewport': viewport,
            'visible_collectibles': visible_count,
            'has_viewport': viewport is not None
        })

    @app.route('/debug-capture', methods=['GET'])
    def debug_capture():
        """Check if capture is receiving frames."""
        if not state.capture_service:
            return jsonify({
                'success': False,
                'error': 'Capture service not available'
            }), 503

        # Try to capture one frame
        screenshot, error = state.capture_service.capture_func()

        return jsonify({
            'success': True,
            'has_frame': screenshot is not None,
            'error': error,
            'frame_shape': screenshot.shape if screenshot is not None else None
        })

    @app.route('/manual-align', methods=['POST'])
    def manual_align():
        """Manually trigger one alignment using MSS screenshot."""
        import mss
        import numpy as np

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            img = img[:, :, :3]  # Remove alpha channel (BGRA -> BGR)

        # Run matcher
        result = state.matcher.match(img)

        if result and result.get('success'):
            viewport = result['viewport']
            # Update backend with viewport
            if hasattr(state, 'backend') and state.backend:
                state.backend.update_viewport({
                    'x': viewport.x,
                    'y': viewport.y,
                    'width': viewport.width,
                    'height': viewport.height
                })

            return jsonify({
                'success': True,
                'viewport': {
                    'x': viewport.x,
                    'y': viewport.y,
                    'width': viewport.width,
                    'height': viewport.height
                },
                'confidence': result.get('confidence'),
                'inliers': result.get('inliers')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Match failed')
            })

    return app, None  # No SocketIO needed for Qt/QML
