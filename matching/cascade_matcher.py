"""Fast cascade matching algorithm - optimized for speed"""

import cv2
import numpy as np
import time
from typing import Dict, Optional, Tuple
from config import MAP_DIMENSIONS


class CascadeMatcher:
    """Fast cascade matcher - prioritizes speed while maintaining accuracy"""
    
    def __init__(self):
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self.last_position = None
        self.last_scale_used = None
    
    def match(self, game_view: np.ndarray, pyramids: Dict) -> Dict:
        """Fast cascade matching - target <100ms"""
        start_time = time.time()
        
        # Convert to grayscale
        if len(game_view.shape) == 3:
            game_gray = cv2.cvtColor(game_view, cv2.COLOR_BGR2GRAY)
        else:
            game_gray = game_view
        
        h, w = game_gray.shape
        
        # OPTIMIZATION 1: If we have a good last match, try that scale first
        if self.last_scale_used and self.last_position and self.last_position.get('confidence', 0) > 0.7:
            try:
                quick_result = self._quick_match_at_scale(
                    game_gray, pyramids[self.last_scale_used], self.last_scale_used
                )
                if quick_result and quick_result['confidence'] > 0.7:
                    # Good enough - use it!
                    final = self._convert_to_detection_space(quick_result)
                    final['total_time_ms'] = (time.time() - start_time) * 1000
                    self.last_position = final
                    return final
            except:
                pass  # Fall through to full cascade
        
        # OPTIMIZATION 2: Try only 2-3 scales based on viewport estimate
        scales_to_try = self._select_scales_smart(pyramids.keys())
        
        best_result = None
        best_confidence = 0
        
        for map_scale in scales_to_try:
            try:
                result = self._quick_match_at_scale(
                    game_gray, pyramids[map_scale], map_scale
                )
                
                if result and result['confidence'] > best_confidence:
                    best_confidence = result['confidence']
                    best_result = result
                    self.last_scale_used = map_scale
                    
                    # OPTIMIZATION 3: Early exit if good enough
                    if result['confidence'] > 0.8:
                        break
            except:
                continue
        
        if best_result is None:
            raise Exception("Matching failed")
        
        final_result = self._convert_to_detection_space(best_result)
        final_result['total_time_ms'] = (time.time() - start_time) * 1000
        self.last_position = final_result
        
        return final_result
    
    def _quick_match_at_scale(self, game_gray: np.ndarray, 
                             pyramid: Dict, map_scale: float) -> Optional[Dict]:
        """Quick single-scale matching without multiple game scales"""
        h, w = game_gray.shape
        
        # OPTIMIZATION: Use single optimal game scale
        # For 1920x1080 game at different zoom levels:
        # - If map_scale is 0.5, game is probably zoomed in, use game_scale=1.0
        # - If map_scale is 0.125, game is probably zoomed out, use game_scale=0.5
        if map_scale >= 0.25:
            game_scale = 1.0  # Don't downscale for fine pyramid levels
        else:
            game_scale = 0.5  # Downscale for coarse pyramid levels
        
        # Scale game
        game_w = int(w * game_scale)
        game_h = int(h * game_scale)
        
        if game_w < 100 or game_h < 100:
            return None
        
        game_scaled = cv2.resize(game_gray, (game_w, game_h), interpolation=cv2.INTER_AREA)
        
        # Extract features - REDUCED COUNTS FOR SPEED
        detector = cv2.AKAZE_create()
        detector.setMaxPoints(300)  # Fixed low count for speed
        
        game_kp, game_des = detector.detectAndCompute(game_scaled, None)
        
        if game_des is None or len(game_kp) < 10:
            return None
        
        # Get map features - use ROI if we have last position
        if self.last_position and self.last_position.get('confidence', 0) > 0.5:
            map_kp, map_des, roi_offset = self._get_roi_features_fast(
                pyramid, self.last_position, map_scale
            )
        else:
            map_kp = pyramid['keypoints']
            map_des = pyramid['descriptors']
            roi_offset = (0, 0)
        
        # Match features
        matches = self.matcher.knnMatch(game_des, map_des, k=2)
        
        # Quick ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)
        
        if len(good_matches) < 6:
            return None
        
        # Get points
        game_pts = np.float32([game_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        map_pts = np.float32([map_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Add ROI offset
        map_pts[:, 0, 0] += roi_offset[0]
        map_pts[:, 0, 1] += roi_offset[1]
        
        # Compute homography
        M, mask = cv2.findHomography(game_pts, map_pts, cv2.RANSAC, 5.0)
        
        if M is None:
            return None
        
        inliers = int(np.sum(mask))
        if inliers < 5:
            return None
        
        # Transform corners
        corners = np.float32([
            [0, 0], [game_w, 0],
            [game_w, game_h], [0, game_h]
        ]).reshape(-1, 1, 2)
        
        map_corners = cv2.perspectiveTransform(corners, M)
        x_coords = map_corners[:, 0, 0]
        y_coords = map_corners[:, 0, 1]
        
        return {
            'map_x': float(np.min(x_coords)),
            'map_y': float(np.min(y_coords)),
            'map_w': float(np.max(x_coords) - np.min(x_coords)),
            'map_h': float(np.max(y_coords) - np.min(y_coords)),
            'map_scale': map_scale,
            'game_scale': game_scale,
            'screen_w': w,
            'screen_h': h,
            'confidence': inliers / len(good_matches),
            'inliers': inliers
        }
    
    def _select_scales_smart(self, available_scales) -> list:
        """Select 2-3 scales to try based on context"""
        scales = sorted(available_scales)
        
        if self.last_position:
            # Based on last match, pick nearby scales
            if self.last_scale_used == 0.5:
                return [0.5, 0.25]  # Try fine first
            elif self.last_scale_used == 0.25:
                return [0.25, 0.5, 0.125]  # Try medium and neighbors
            else:
                return [0.125, 0.25]  # Try coarse first
        else:
            # No history - try medium first (usually works)
            return [0.25, 0.125, 0.5]  # Order by likelihood
    
    def _get_roi_features_fast(self, pyramid: Dict, last_pos: Dict, 
                               map_scale: float) -> Tuple:
        """Fast ROI extraction"""
        # Convert last position to this scale
        scale_factor = map_scale / MAP_DIMENSIONS.DETECTION_SCALE
        center_x = last_pos.get('map_x', 0) * scale_factor + last_pos.get('map_w', 100) * scale_factor / 2
        center_y = last_pos.get('map_y', 0) * scale_factor + last_pos.get('map_h', 100) * scale_factor / 2
        
        # Simple fixed-size ROI
        radius = 200  # Fixed radius in scaled space
        
        roi_x1 = max(0, int(center_x - radius))
        roi_y1 = max(0, int(center_y - radius))
        roi_x2 = min(pyramid['shape'][1], int(center_x + radius))
        roi_y2 = min(pyramid['shape'][0], int(center_y + radius))
        
        # Quick feature filtering
        roi_kp = []
        roi_indices = []
        
        for i, kp in enumerate(pyramid['keypoints']):
            if roi_x1 <= kp.pt[0] < roi_x2 and roi_y1 <= kp.pt[1] < roi_y2:
                adjusted_kp = cv2.KeyPoint(
                    x=kp.pt[0] - roi_x1,
                    y=kp.pt[1] - roi_y1,
                    size=kp.size,
                    angle=kp.angle,
                    response=kp.response,
                    octave=kp.octave,
                    class_id=kp.class_id
                )
                roi_kp.append(adjusted_kp)
                roi_indices.append(i)
        
        if len(roi_indices) > 50:  # Enough features in ROI
            return roi_kp, pyramid['descriptors'][roi_indices], (roi_x1, roi_y1)
        else:
            # Fall back to full pyramid
            return pyramid['keypoints'], pyramid['descriptors'], (0, 0)
    
    def _convert_to_detection_space(self, result: Dict) -> Dict:
        """Convert to detection space coordinates"""
        scale_to_detection = MAP_DIMENSIONS.DETECTION_SCALE / result['map_scale']
        
        return {
            'map_x': int(result['map_x'] * scale_to_detection),
            'map_y': int(result['map_y'] * scale_to_detection),
            'map_w': int(result['map_w'] * scale_to_detection),
            'map_h': int(result['map_h'] * scale_to_detection),
            'screen_w': result['screen_w'],
            'screen_h': result['screen_h'],
            'confidence': result['confidence'],
            'inliers': result['inliers']
        }