"""
Scale prediction based on quick feature analysis.
Predicts optimal starting scale for cascade matcher.
"""

import cv2
import numpy as np
from typing import Tuple
from dataclasses import dataclass

@dataclass
class ScalePrediction:
    """Prediction result with confidence."""
    recommended_scales: list  # Ordered list of scales to try
    confidence: float
    feature_metrics: dict

class ScalePredictor:
    """Predicts optimal matching scale from screenshot features."""

    def __init__(self):
        # Calibrated thresholds from testing
        self.feature_density_thresholds = {
            'very_low': 0.0002,   # < this = extreme zoom out
            'low': 0.0005,         # < this = moderate zoom out
            'normal': 0.001        # >= this = normal/zoomed in
        }

        # Response strength thresholds
        self.response_thresholds = {
            'weak': 0.003,         # Blurry/low detail
            'normal': 0.006        # Sharp/high detail
        }

    def predict_scale(self, screenshot: np.ndarray, max_analysis_ms: int = 10) -> ScalePrediction:
        """
        Quick feature analysis to predict optimal matching scale.

        Args:
            screenshot: Grayscale screenshot (1920x864)
            max_analysis_ms: Maximum time to spend on analysis

        Returns:
            ScalePrediction with recommended scale order
        """
        # Sample center region (more stable than edges)
        h, w = screenshot.shape
        roi = screenshot[h//4:3*h//4, w//4:3*w//4]

        # Fast AKAZE with limited features for speed
        akaze = cv2.AKAZE_create(
            descriptor_type=cv2.AKAZE_DESCRIPTOR_MLDB,
            descriptor_size=0,
            descriptor_channels=3,
            threshold=0.0008,  # Lower threshold for more features
            nOctaves=3,        # Fewer octaves for speed
            nOctaveLayers=2    # Fewer layers for speed
        )

        # Detect features (target: 5ms)
        keypoints = akaze.detect(roi, None)

        # Calculate metrics
        roi_pixels = roi.shape[0] * roi.shape[1]
        feature_density = len(keypoints) / roi_pixels

        # Response strength (indicates feature quality)
        if keypoints:
            responses = [kp.response for kp in keypoints]
            mean_response = np.mean(responses)
            response_std = np.std(responses)

            # Size distribution (larger features = zoomed out)
            sizes = [kp.size for kp in keypoints]
            mean_size = np.mean(sizes)
        else:
            mean_response = 0
            response_std = 0
            mean_size = 0

        # Gradient magnitude as additional signal
        grad_x = cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(roi, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        grad_energy = np.mean(grad_mag)

        # Decision logic based on multiple signals
        confidence = 0.0

        if feature_density < self.feature_density_thresholds['very_low']:
            # Extreme zoom out - skip 25%, try 50% first
            recommended_scales = [0.5, 1.0, 0.25]
            confidence = 0.85
            scale_reason = "very_low_density"

        elif feature_density < self.feature_density_thresholds['low'] and mean_size > 20:
            # Moderate zoom out with large features
            recommended_scales = [0.5, 0.25, 1.0]
            confidence = 0.7
            scale_reason = "low_density_large_features"

        elif grad_energy < 5.0:
            # Low texture detail (often zoomed out areas)
            recommended_scales = [0.5, 0.25, 1.0]
            confidence = 0.6
            scale_reason = "low_gradient_energy"

        else:
            # Normal case - use standard cascade
            recommended_scales = [0.25, 0.5, 1.0]
            confidence = 0.5
            scale_reason = "normal"

        return ScalePrediction(
            recommended_scales=recommended_scales,
            confidence=confidence,
            feature_metrics={
                'feature_density': feature_density,
                'feature_count': len(keypoints),
                'mean_response': mean_response,
                'mean_size': mean_size,
                'grad_energy': grad_energy,
                'scale_reason': scale_reason
            }
        )

    def calibrate_thresholds(self, training_data: list) -> None:
        """
        Calibrate thresholds using labeled training data.

        Args:
            training_data: List of (screenshot, known_viewport_size) tuples
        """
        # TODO: Implement threshold calibration from ground truth
        # This would analyze feature metrics vs known viewport sizes
        # to find optimal decision boundaries
        pass