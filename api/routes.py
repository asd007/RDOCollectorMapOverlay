"""Flask API routes"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import numpy as np
import cv2
import time
from config import SERVER, SCREENSHOT
from api.state import OverlayState

# Check for screenshot capability
try:
    import mss
    SCREENSHOT_AVAILABLE = True
except ImportError:
    SCREENSHOT_AVAILABLE = False
    print("Warning: mss not available - screenshot functionality disabled")


def create_app(state: OverlayState):
    """Create Flask application with routes"""
    app = Flask(__name__)
    
    if SERVER.CORS_ENABLED:
        CORS(app)
    
    @app.route('/status', methods=['GET'])
    def get_status():
        """Get system status"""
        return jsonify({
            'ready': state.is_initialized,
            'tracking': state.cascade_matcher is not None,
            'collectibles_loaded': len(state.collectibles),
            'screenshot_available': SCREENSHOT_AVAILABLE,
            'method': 'cascade_pixel_perfect'
        })
    
    @app.route('/align-with-screenshot', methods=['POST'])
    def align_with_screenshot():
        """Capture screenshot and perform alignment"""
        if not SCREENSHOT_AVAILABLE:
            return jsonify({'success': False, 'error': 'Screenshot not available'}), 400
        
        if not state.is_initialized:
            return jsonify({'success': False, 'error': 'System not initialized'}), 500
        
        request_start = time.time()
        
        try:
            # Capture screenshot
            screenshot_start = time.time()
            with mss.mss() as sct:
                monitor = sct.monitors[SCREENSHOT.MONITOR_INDEX]
                # Crop to avoid UI
                monitor_cropped = {
                    'left': monitor['left'],
                    'top': monitor['top'],
                    'width': monitor['width'],
                    'height': int(monitor['height'] * SCREENSHOT.CROP_TOP_PERCENTAGE)
                }
                screenshot = sct.grab(monitor_cropped)
                img = np.array(screenshot)
                
                # Convert color if needed
                if img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            screenshot_time = (time.time() - screenshot_start) * 1000
            
            # Perform matching
            matching_start = time.time()
            viewport = state.cascade_matcher.match(img, state.pyramids)
            matching_time = (time.time() - matching_start) * 1000
            
            # Get visible collectibles
            overlay_start = time.time()
            collectibles = state.get_visible_collectibles(viewport)
            overlay_time = (time.time() - overlay_start) * 1000
            
            total_time = (time.time() - request_start) * 1000
            
            # Log performance
            print(f"Alignment: screenshot={screenshot_time:.1f}ms, "
                  f"matching={matching_time:.1f}ms, overlay={overlay_time:.1f}ms, "
                  f"total={total_time:.1f}ms, confidence={viewport['confidence']:.2%}")
            
            return jsonify({
                'success': True,
                'collectibles': collectibles,
                'timing': {
                    'screenshot_ms': round(screenshot_time, 1),
                    'matching_ms': round(matching_time, 1),
                    'overlay_ms': round(overlay_time, 1),
                    'total_ms': round(total_time, 1)
                },
                'quality': {
                    'confidence': f"{viewport['confidence']*100:.1f}%",
                    'inliers': viewport['inliers']
                }
            })
            
        except Exception as e:
            print(f"Alignment failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/reset-tracking', methods=['POST'])
    def reset_tracking():
        """Reset tracking state"""
        if state.cascade_matcher:
            state.cascade_matcher.last_position = None
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
    
    return app
