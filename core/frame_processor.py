"""
Frame processing: capture, deduplication, and preprocessing.
Extracted from ContinuousCaptureService for single responsibility.
"""

import hashlib
from typing import Callable, Optional, Tuple
import numpy as np


class FrameProcessor:
    """
    Handles screenshot capture and basic frame processing.

    Responsibilities:
    - Capture wrapper (calls capture_func)
    - Frame deduplication via hash (optional)
    - Map visibility detection (optional)
    - Error handling for capture failures

    Thread safety: Not thread-safe (designed for single capture thread).
    """

    def __init__(
        self,
        capture_func: Callable,
        enable_deduplication: bool = False,
        enable_map_detection: bool = False
    ):
        """
        Initialize frame processor.

        Args:
            capture_func: Function that captures screenshot.
                         Should return (screenshot, error) tuple.
            enable_deduplication: Enable hash-based frame deduplication
            enable_map_detection: Enable map visibility check before matching
        """
        self.capture_func = capture_func
        self.enable_deduplication = enable_deduplication
        self.enable_map_detection = enable_map_detection

        # Frame deduplication state
        self.previous_frame_hash: Optional[str] = None
        self.cached_result: Optional[dict] = None

        # Statistics
        self.total_frames = 0
        self.duplicate_frames = 0
        self.map_not_visible_frames = 0
        self.capture_errors = 0

    def capture_and_preprocess(self) -> Tuple[Optional[np.ndarray], bool, Optional[str]]:
        """
        Capture screenshot and check for duplicates/map visibility.

        Returns:
            Tuple of (screenshot, is_duplicate, error_message):
                - screenshot: numpy array or None if error
                - is_duplicate: True if frame is duplicate of previous
                - error_message: Error string or None if success
        """
        self.total_frames += 1

        # Capture screenshot
        try:
            screenshot, error = self.capture_func()

            if error or screenshot is None:
                self.capture_errors += 1
                return None, False, error or "Capture returned None"

        except Exception as e:
            self.capture_errors += 1
            return None, False, f"Capture exception: {e}"

        # Frame deduplication (currently disabled by default)
        # MD5 hash can match on similar frames even when viewport has moved slightly
        # With motion prediction, matching is fast enough (~10-20ms) to run every frame
        is_duplicate = False
        if self.enable_deduplication:
            frame_hash = self._compute_hash(screenshot)
            if frame_hash == self.previous_frame_hash and self.cached_result is not None:
                self.duplicate_frames += 1
                is_duplicate = True
            self.previous_frame_hash = frame_hash

        # Map detection (currently disabled by default)
        # Map detector was too strict, causing low success rate
        if self.enable_map_detection and not is_duplicate:
            if not self.is_map_visible(screenshot):
                self.map_not_visible_frames += 1
                return None, False, "Map not visible"

        return screenshot, is_duplicate, None

    def is_map_visible(self, screenshot: np.ndarray) -> bool:
        """
        Check if RDO map is visible in screenshot.

        Args:
            screenshot: numpy array of screenshot

        Returns:
            True if map is visible
        """
        from core.map_detector import is_map_visible
        return is_map_visible(screenshot)

    def cache_result(self, result: dict):
        """
        Cache result for duplicate frame optimization.

        Args:
            result: Match result dict to cache
        """
        self.cached_result = result.copy() if result else None

    def get_cached_result(self) -> Optional[dict]:
        """
        Get cached result for duplicate frame.

        Returns:
            Cached result or None
        """
        return self.cached_result.copy() if self.cached_result else None

    def get_stats(self) -> dict:
        """
        Get frame processing statistics.

        Returns:
            Dict with:
                - total_frames: Total frames processed
                - duplicate_frames: Frames skipped due to deduplication
                - map_not_visible_frames: Frames skipped (map not visible)
                - capture_errors: Failed captures
                - deduplication_enabled: Whether deduplication is enabled
                - map_detection_enabled: Whether map detection is enabled
        """
        return {
            'total_frames': self.total_frames,
            'duplicate_frames': self.duplicate_frames,
            'map_not_visible_frames': self.map_not_visible_frames,
            'capture_errors': self.capture_errors,
            'deduplication_enabled': self.enable_deduplication,
            'map_detection_enabled': self.enable_map_detection,
            'duplicate_rate': (
                self.duplicate_frames / self.total_frames
                if self.total_frames > 0 else 0
            )
        }

    def reset_cache(self):
        """Reset deduplication cache."""
        self.previous_frame_hash = None
        self.cached_result = None

    def _compute_hash(self, screenshot: np.ndarray) -> str:
        """
        Compute perceptual hash for frame deduplication.

        Args:
            screenshot: numpy array of screenshot

        Returns:
            MD5 hash hex string
        """
        return hashlib.md5(screenshot.tobytes()).hexdigest()
