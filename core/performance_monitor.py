"""
Performance monitoring and metrics aggregation.
Thread ownership: Capture background thread.
"""

from core.metrics import MetricsTracker
from typing import Dict


class PerformanceMonitor:
    """
    Aggregates performance metrics from capture/match operations.
    Thread-safe: Can be read from Flask HTTP thread via get_stats().

    This is a thin wrapper around MetricsTracker that provides a cleaner
    interface focused on the overlay's specific monitoring needs.
    """

    def __init__(self, window_seconds: int = 600):
        """
        Initialize performance monitor.

        Args:
            window_seconds: Time window for metrics (default: 600s = 10 minutes)
        """
        self._metrics = MetricsTracker(window_seconds=window_seconds)

    def record_frame(
        self,
        capture_ms: float,
        match_ms: float,
        overlay_ms: float,
        total_ms: float,
        confidence: float,
        inliers: int,
        frame_type: str,
        viewport_width: float = 0,
        viewport_height: float = 0,
        cascade_level: str = 'unknown',
        motion_offset_px: tuple = (0, 0),
        motion_speed_px_s: float = 0
    ):
        """
        Record frame metrics.
        Thread: Capture background thread.

        Args:
            capture_ms: Screenshot capture time in milliseconds
            match_ms: Feature matching time in milliseconds
            overlay_ms: Collectible filtering time in milliseconds
            total_ms: Total frame processing time in milliseconds
            confidence: Match confidence score (0.0-1.0)
            inliers: Number of RANSAC inliers
            frame_type: 'motion', 'akaze', 'skipped', or 'failed'
            viewport_width: Viewport width in detection space
            viewport_height: Viewport height in detection space
            cascade_level: Scale used ('0.125', '0.25', '0.5', etc.)
            motion_offset_px: Phase correlation offset (dx, dy) in pixels
            motion_speed_px_s: Movement speed in pixels/second
        """
        self._metrics.record_frame(
            capture_ms=capture_ms,
            match_ms=match_ms,
            overlay_ms=overlay_ms,
            total_ms=total_ms,
            confidence=confidence,
            inliers=inliers,
            frame_type=frame_type,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            cascade_level=cascade_level,
            motion_offset_px=motion_offset_px,
            motion_speed_px_s=motion_speed_px_s
        )

    def get_stats(self) -> Dict:
        """
        Get aggregated statistics.
        Thread: Any thread (thread-safe via internal lock).

        Returns:
            Comprehensive stats dict for /stats endpoint including:
            - Session info (uptime, total frames, FPS)
            - Window info (frames in window, FPS)
            - Frame breakdown (motion/akaze/skipped/failed)
            - Timing stats (mean/median/P95/P99 for each stage)
            - Match quality (confidence, inliers)
            - Cascade matcher usage
            - Movement statistics
        """
        return self._metrics.get_statistics()

    def reset(self):
        """
        Clear all metrics and reset session counters.
        Thread: Any thread (thread-safe).
        """
        self._metrics.reset()
