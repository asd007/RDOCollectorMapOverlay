"""
Kalman filter-based viewport tracking for ROI optimization.
Predicts next viewport position/size based on motion history.
"""

import numpy as np
from typing import Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class Viewport:
    """Viewport position and size in detection space."""
    x: float
    y: float
    width: float
    height: float
    confidence: float
    timestamp: float

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def scale(self) -> float:
        """Relative scale (width as proxy)."""
        return self.width


class ViewportKalmanTracker:
    """
    Kalman filter for smooth viewport tracking with adaptive ROI prediction.

    State vector: [cx, cy, width, height, vx, vy, scale_velocity]
    """

    def __init__(self, dt: float = 0.2):
        """
        Initialize Kalman filter.

        Args:
            dt: Time step between frames (default 0.2s = 5fps)
        """
        self.dt = dt
        self.initialized = False

        # State: [cx, cy, width, height, vx, vy, vscale]
        self.x = np.zeros(7)  # State estimate
        self.P = np.eye(7) * 1000  # Covariance (high initial uncertainty)

        # State transition matrix (constant velocity model)
        self.F = np.array([
            [1, 0, 0, 0, dt, 0, 0],   # cx = cx + vx*dt
            [0, 1, 0, 0, 0, dt, 0],   # cy = cy + vy*dt
            [0, 0, 1, 0, 0, 0, dt],   # width with scale velocity
            [0, 0, 0, 1, 0, 0, dt],   # height with scale velocity
            [0, 0, 0, 0, 1, 0, 0],    # vx constant
            [0, 0, 0, 0, 0, 1, 0],    # vy constant
            [0, 0, 0, 0, 0, 0, 1]     # vscale constant
        ])

        # Measurement matrix (observe position and size)
        self.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ])

        # Process noise (higher for velocities = allows faster changes)
        self.Q = np.diag([10, 10, 5, 5, 50, 50, 10])

        # Measurement noise (position less certain than size)
        self.R = np.diag([25, 25, 10, 10])

    def predict(self) -> Dict:
        """
        Predict next viewport state.

        Returns:
            Dict with predicted viewport and ROI bounds
        """
        if not self.initialized:
            return None

        # Prediction step
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        cx, cy, w, h = self.x[:4]
        vx, vy = self.x[4:6]

        # Compute velocity magnitude for adaptive margin
        velocity_mag = np.sqrt(vx**2 + vy**2)

        # Adaptive margin based on velocity and uncertainty
        # Base margin: 1.2x (20% expansion)
        # Velocity factor: up to +0.4 for fast motion (>300px/s)
        # Uncertainty factor: up to +0.4 for high covariance
        base_margin = 1.2
        velocity_factor = min(0.4, velocity_mag / 500)
        uncertainty = np.trace(self.P[:4, :4])  # Sum of position/size variances
        uncertainty_factor = min(0.4, uncertainty / 10000)

        margin = base_margin + velocity_factor + uncertainty_factor

        # ROI bounds
        roi_w = w * margin
        roi_h = h * margin
        roi_x = cx - roi_w / 2
        roi_y = cy - roi_h / 2

        return {
            'predicted_viewport': {
                'cx': cx,
                'cy': cy,
                'width': w,
                'height': h
            },
            'roi': {
                'x': max(0, roi_x),
                'y': max(0, roi_y),
                'width': roi_w,
                'height': roi_h
            },
            'margin_factor': margin,
            'velocity': {'vx': vx, 'vy': vy, 'magnitude': velocity_mag},
            'uncertainty': uncertainty
        }

    def update(self, viewport: Viewport) -> None:
        """
        Update filter with new viewport measurement.

        Args:
            viewport: Measured viewport from matching
        """
        cx, cy = viewport.center
        measurement = np.array([cx, cy, viewport.width, viewport.height])

        if not self.initialized:
            # Initialize state with first measurement
            self.x[:4] = measurement
            self.x[4:] = 0  # Zero initial velocity
            self.initialized = True
            return

        # Update step
        y = measurement - (self.H @ self.x)  # Innovation
        S = self.H @ self.P @ self.H.T + self.R  # Innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Kalman gain

        self.x = self.x + K @ y
        self.P = (np.eye(7) - K @ self.H) @ self.P

    def reset(self) -> None:
        """Reset tracker (e.g., after teleport detection)."""
        self.initialized = False
        self.x = np.zeros(7)
        self.P = np.eye(7) * 1000
