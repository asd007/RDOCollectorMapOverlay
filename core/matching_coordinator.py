"""
Matching coordination: cascade matcher orchestration with ROI tracking.
Extracted from ContinuousCaptureService for single responsibility.
"""

import time
import numpy as np
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from matching.viewport_tracker import ViewportKalmanTracker, Viewport


class MatchingCoordinator:
    """
    Coordinates cascade matcher with ROI tracking and fallback logic.

    Responsibilities:
    - Orchestrate cascade matcher with timeout
    - ViewportKalmanTracker integration
    - Motion prediction and extrapolation
    - Match result processing
    - Statistics tracking

    Thread safety: Not thread-safe (designed for single capture thread).
    """

    def __init__(
        self,
        matcher,
        frame_interval: float = 0.2,
        match_timeout: float = 6.0
    ):
        """
        Initialize matching coordinator.

        Args:
            matcher: CascadeScaleMatcher instance
            frame_interval: Time between frames in seconds (for tracker dt)
            match_timeout: Maximum time to wait for match (seconds)
        """
        self.matcher = matcher
        self.match_timeout = match_timeout

        # ROI tracking
        self.tracker = ViewportKalmanTracker(dt=frame_interval)
        self.previous_viewport: Optional[Viewport] = None

        # Motion extrapolation
        self.measured_render_lag_ms = 15.0  # Adaptive lag from frontend

        # Statistics
        self.total_matches = 0
        self.successful_matches = 0
        self.failed_matches = 0
        self.timeout_matches = 0
        self.motion_only_frames = 0
        self.akaze_frames = 0

        # Detailed AKAZE cascade level tracking
        self.akaze_cascade_levels = {}  # {level_name: count}

    def update_frame_interval(self, frame_interval: float):
        """
        Update frame interval for motion tracking.

        Args:
            frame_interval: New frame interval in seconds
        """
        if hasattr(self.tracker, 'dt'):
            self.tracker.dt = frame_interval

    def update_render_lag(self, lag_ms: float):
        """
        Update measured render lag for adaptive extrapolation.

        Args:
            lag_ms: Measured lag from frontend (milliseconds)
        """
        self.measured_render_lag_ms = lag_ms

    def match(self, screenshot: np.ndarray) -> Optional[Dict]:
        """
        Match screenshot to map using cascade matcher with timeout.

        Returns:
            Match result dict with:
                - success: bool
                - map_x, map_y, map_w, map_h: Viewport bounds in detection space
                - confidence: Match quality (0.0-1.0)
                - inliers: Number of RANSAC inliers
                - cascade_info: Dict with cascade metadata
                - match_time_ms: Time taken to match
                - None if match failed or timed out
        """
        self.total_matches += 1

        # Execute matcher with timeout
        match_start = time.time()

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.matcher.match, screenshot)
                result = future.result(timeout=self.match_timeout)

            match_time_ms = (time.time() - match_start) * 1000

        except FuturesTimeoutError:
            match_time_ms = (time.time() - match_start) * 1000
            print(f"[MatchingCoordinator] Matcher timed out after {self.match_timeout}s")
            self.timeout_matches += 1
            self.failed_matches += 1
            return None

        except Exception as e:
            match_time_ms = (time.time() - match_start) * 1000
            print(f"[MatchingCoordinator] Matcher exception: {e}")
            self.failed_matches += 1
            return None

        # Process result
        if not result or not result.get('success'):
            self.failed_matches += 1
            return None

        self.successful_matches += 1

        # Add timing to result
        result['match_time_ms'] = match_time_ms

        # Track motion-only vs AKAZE frames using match_type
        match_type = result.get('match_type', 'akaze')  # Default to 'akaze' if missing

        if match_type == 'motion_only':
            self.motion_only_frames += 1
        else:  # 'akaze' or any other AKAZE-based type
            self.akaze_frames += 1

            # Track which cascade level was used for AKAZE matches
            cascade_info = result.get('cascade_info', {})
            final_level = cascade_info.get('final_level')
            if final_level:
                self.akaze_cascade_levels[final_level] = self.akaze_cascade_levels.get(final_level, 0) + 1

        # Create viewport from result
        viewport = Viewport(
            x=result['map_x'],
            y=result['map_y'],
            width=result['map_w'],
            height=result['map_h'],
            confidence=result['confidence'],
            timestamp=time.time()
        )

        # Update tracker with new viewport
        self.tracker.update(viewport)
        self.previous_viewport = viewport

        return result

    def get_predicted_viewport(self, current_viewport: Viewport) -> Dict:
        """
        Predict future viewport position for smoother rendering.

        Uses motion extrapolation based on measured render lag.

        Args:
            current_viewport: Current matched viewport

        Returns:
            Dict with predicted viewport:
                - x, y: Predicted position
                - width, height: Viewport size
                - is_predicted: True if prediction was applied
                - prediction_ms: Lag used for prediction
        """
        try:
            prediction = self.tracker.predict()

            if prediction:
                pred_vp = prediction['predicted_viewport']
                # Convert center + size to x,y + size
                predicted_x = pred_vp['cx'] - pred_vp['width'] / 2
                predicted_y = pred_vp['cy'] - pred_vp['height'] / 2

                return {
                    'x': predicted_x,
                    'y': predicted_y,
                    'width': pred_vp['width'],
                    'height': pred_vp['height'],
                    'is_predicted': True,
                    'prediction_ms': self.measured_render_lag_ms
                }

        except Exception as e:
            print(f"[MatchingCoordinator] Prediction error: {e}")

        # Fallback to current viewport
        return {
            'x': current_viewport.x,
            'y': current_viewport.y,
            'width': current_viewport.width,
            'height': current_viewport.height,
            'is_predicted': False,
            'prediction_ms': 0
        }

    def get_motion_stats(self) -> Optional[Dict]:
        """
        Get motion prediction statistics from last match.

        Returns:
            Dict with motion stats or None if no motion data
        """
        # Get latest prediction data from tracker
        try:
            prediction = self.tracker.predict()
            if prediction:
                return {
                    'has_motion_data': True,
                    'velocity_x': prediction.get('velocity_x', 0),
                    'velocity_y': prediction.get('velocity_y', 0),
                    'prediction_confidence': prediction.get('confidence', 0)
                }
        except:
            pass

        return None

    def get_stats(self) -> Dict:
        """
        Get matching statistics.

        Returns:
            Dict with:
                - total_matches: Total match attempts
                - successful_matches: Successful matches
                - failed_matches: Failed matches
                - timeout_matches: Matches that timed out
                - success_rate: Percentage of successful matches
                - motion_only_frames: Frames using pure motion tracking
                - akaze_frames: Frames using AKAZE matching
                - motion_only_ratio: Percentage of motion-only frames
                - akaze_cascade_levels: Distribution of cascade levels used for AKAZE matches
                  (e.g., {'Fast (25%)': 180, 'Medium (50%)': 70})
        """
        success_rate = (
            self.successful_matches / self.total_matches * 100
            if self.total_matches > 0 else 0
        )

        total_tracked = self.motion_only_frames + self.akaze_frames
        motion_only_ratio = (
            self.motion_only_frames / total_tracked * 100
            if total_tracked > 0 else 0
        )

        return {
            'total_matches': self.total_matches,
            'successful_matches': self.successful_matches,
            'failed_matches': self.failed_matches,
            'timeout_matches': self.timeout_matches,
            'success_rate': success_rate,
            'motion_only_frames': self.motion_only_frames,
            'akaze_frames': self.akaze_frames,
            'motion_only_ratio': motion_only_ratio,
            'akaze_cascade_levels': dict(self.akaze_cascade_levels)  # Copy dict for stats
        }

    def reset_tracker(self):
        """Reset motion tracker (e.g., after teleport or zoom change)."""
        self.tracker = ViewportKalmanTracker(dt=self.tracker.dt if hasattr(self.tracker, 'dt') else 0.2)
        self.previous_viewport = None
