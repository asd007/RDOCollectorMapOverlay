"""
Viewport monitoring: drift tracking and pan tracking for coordinate accuracy.
Extracted from ContinuousCaptureService for single responsibility.
"""

import time
import random
import numpy as np
from collections import deque
from typing import Optional, Dict, List
from matching.viewport_tracker import Viewport


class ViewportMonitor:
    """
    Monitors viewport accuracy through drift and pan tracking.

    Responsibilities:
    - Drift tracking: Monitor one collectible to detect coordinate errors
    - Pan tracking: Monitor viewport movement speed/acceleration
    - Coordinate accuracy statistics

    Thread safety: Not thread-safe (designed for single capture thread).
    """

    def __init__(self, history_size: int = 100):
        """
        Initialize viewport monitor.

        Args:
            history_size: Maximum number of samples to keep in history
        """
        self.history_size = history_size

        # Drift tracking - monitor one collectible to detect coordinate errors
        self.drift_tracking_collectible: Optional[Dict] = None
        self.drift_history = deque(maxlen=history_size)

        # Pan tracking - monitor viewport movement speed/acceleration
        self.pan_history = deque(maxlen=history_size)
        self.last_viewport_time: Optional[float] = None

    def update_drift_tracking(
        self,
        frame_number: int,
        viewport: Viewport,
        collectibles: List[Dict],
        match_result: Dict,
        akaze_used: bool
    ):
        """
        Update drift tracking with current frame data.

        Drift tracking picks ONE visible collectible after AKAZE calibration
        and monitors its screen position over time. Variance in position indicates
        coordinate drift or accuracy issues.

        Args:
            frame_number: Current frame number
            viewport: Current viewport
            collectibles: Visible collectibles with screen positions
            match_result: Match result dict
            akaze_used: Whether AKAZE matching was used this frame
        """
        # Select drift tracking collectible (after first AKAZE frame)
        if self.drift_tracking_collectible is None and akaze_used and collectibles:
            # Pick random visible collectible for tracking
            random_col = random.choice(collectibles)
            self.drift_tracking_collectible = {
                'name': random_col.get('name', random_col.get('n', 'Unknown')),
                'map_x': random_col['map_x'],  # Detection space
                'map_y': random_col['map_y'],
                'type': random_col.get('type', random_col.get('t', 'unknown'))
            }
            print(
                f"[Drift Tracking] Selected visible collectible after AKAZE: "
                f"{self.drift_tracking_collectible['name']} ({self.drift_tracking_collectible['type']}) "
                f"at map ({self.drift_tracking_collectible['map_x']:.1f}, {self.drift_tracking_collectible['map_y']:.1f})"
            )

        # Track drift: Record screen position ONLY when our tracked collectible is visible
        if self.drift_tracking_collectible:
            # Find our tracked collectible in visible collectibles
            tracked = None
            for col in collectibles:
                if (abs(col['map_x'] - self.drift_tracking_collectible['map_x']) < 1 and
                        abs(col['map_y'] - self.drift_tracking_collectible['map_y']) < 1):
                    tracked = col
                    break

            if tracked:
                self.drift_history.append({
                    'frame': frame_number,
                    'screen_x': tracked['x'],
                    'screen_y': tracked['y'],
                    'viewport_x': viewport.x,
                    'viewport_y': viewport.y,
                    'confidence': match_result['confidence']
                })

    def update_pan_tracking(
        self,
        frame_number: int,
        motion_prediction: Optional[Dict]
    ):
        """
        Update pan tracking with motion data.

        Pan tracking monitors viewport movement using phase correlation offsets.
        Records speed (pixels/sec) and acceleration (pixels/sec^2).

        Args:
            frame_number: Current frame number
            motion_prediction: Motion prediction dict from match result with:
                - offset_px: (dx, dy) in screenshot pixels
                - phase_confidence: Phase correlation confidence
        """
        current_time = time.time()

        if motion_prediction and self.last_viewport_time is not None:
            dt = current_time - self.last_viewport_time

            # Sanity check on time delta
            if 0 < dt < 0.5:
                # Get movement in screenshot pixels (direct from phase correlation)
                dx_screenshot, dy_screenshot = motion_prediction['offset_px']

                # Screenshot pixels = screen pixels (assuming game runs at native resolution)
                dx_screen = dx_screenshot
                dy_screen = dy_screenshot

                # Speed in screen pixels/sec
                speed = np.sqrt(dx_screen**2 + dy_screen**2) / dt

                # Calculate acceleration if we have previous speed
                acceleration = 0
                if self.pan_history:
                    last_speed = self.pan_history[-1]['speed']
                    acceleration = (speed - last_speed) / dt  # screen px/sec^2

                self.pan_history.append({
                    'frame': frame_number,
                    'timestamp': current_time,
                    'dx': dx_screen,  # Screen pixels (from phase correlation)
                    'dy': dy_screen,  # Screen pixels (from phase correlation)
                    'speed': speed,  # Screen pixels/sec
                    'acceleration': acceleration,  # Screen pixels/sec^2
                    'dt': dt,
                    'phase_confidence': motion_prediction['phase_confidence']
                })

        self.last_viewport_time = current_time

    def get_drift_stats(self) -> Optional[Dict]:
        """
        Get drift tracking statistics.

        Returns:
            Dict with drift stats:
                - collectible_name: Name of tracked collectible
                - map_x, map_y: Position in detection space
                - screen_x_variance: Variance of screen X position
                - screen_y_variance: Variance of screen Y position
                - screen_x_range: Range of screen X positions
                - screen_y_range: Range of screen Y positions
                - samples: Number of samples
                - recent_positions: Last 10 samples
            Or None if no drift data
        """
        if not self.drift_history or len(self.drift_history) < 2:
            return None

        # Calculate screen position variance (should be stable if no drift)
        screen_xs = [d['screen_x'] for d in self.drift_history]
        screen_ys = [d['screen_y'] for d in self.drift_history]

        return {
            'collectible_name': self.drift_tracking_collectible['name'] if self.drift_tracking_collectible else 'Unknown',
            'map_x': float(self.drift_tracking_collectible['map_x']) if self.drift_tracking_collectible else 0,
            'map_y': float(self.drift_tracking_collectible['map_y']) if self.drift_tracking_collectible else 0,
            'screen_x_variance': float(np.var(screen_xs)),
            'screen_y_variance': float(np.var(screen_ys)),
            'screen_x_range': float(np.max(screen_xs) - np.min(screen_xs)),
            'screen_y_range': float(np.max(screen_ys) - np.min(screen_ys)),
            'samples': len(self.drift_history),
            'recent_positions': list(self.drift_history)[-10:]  # Last 10 samples
        }

    def get_pan_stats(self) -> Optional[Dict]:
        """
        Get pan movement statistics.

        Returns:
            Dict with pan stats:
                - samples: Number of samples
                - speed: Dict with mean/median/max/min/p95 (screen pixels/sec)
                - acceleration: Dict with mean/median/max/min (screen pixels/sec^2)
                - recent_movements: Last 10 movements
            Or None if no pan data
        """
        if not self.pan_history or len(self.pan_history) < 2:
            return None

        speeds = [p['speed'] for p in self.pan_history]
        accelerations = [p['acceleration'] for p in self.pan_history if p['acceleration'] != 0]

        return {
            'samples': len(self.pan_history),
            'speed': {
                'mean': float(np.mean(speeds)),
                'median': float(np.median(speeds)),
                'max': float(np.max(speeds)),
                'min': float(np.min(speeds)),
                'p95': float(np.percentile(speeds, 95))
            },
            'acceleration': {
                'mean': float(np.mean(accelerations)) if accelerations else 0,
                'median': float(np.median(accelerations)) if accelerations else 0,
                'max': float(np.max(accelerations)) if accelerations else 0,
                'min': float(np.min(accelerations)) if accelerations else 0
            },
            'recent_movements': list(self.pan_history)[-10:]  # Last 10 movements
        }

    def reset(self):
        """Reset all tracking data."""
        self.drift_tracking_collectible = None
        self.drift_history.clear()
        self.pan_history.clear()
        self.last_viewport_time = None
