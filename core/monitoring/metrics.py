"""
Time-series metrics tracker for RDO overlay performance monitoring.

Stores the last 10 minutes of metrics and provides statistical analysis:
- Frame timing (capture, matching, overlay, total)
- Match quality (confidence, inliers)
- FPS tracking
- Frame breakdown (motion-only, AKAZE, skipped, failed)
- Percentile calculations (P50, P95, P99)
"""

import time
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Deque
from threading import Lock


@dataclass
class FrameMetrics:
    """Metrics for a single frame."""
    timestamp: float
    capture_ms: float
    match_ms: float
    overlay_ms: float
    total_ms: float
    confidence: float
    inliers: int
    frame_type: str  # 'motion', 'akaze', 'skipped', 'failed'
    viewport_width: float
    viewport_height: float
    cascade_level: str = 'unknown'  # Scale used (e.g., '0.125', '0.25', '0.5')
    motion_offset_px: tuple = (0, 0)  # Phase correlation offset in pixels
    motion_speed_px_s: float = 0  # Movement speed in pixels/second


class MetricsTracker:
    """
    Thread-safe time-series metrics tracker.
    Stores last 10 minutes of frame metrics with O(1) insertion and efficient statistics.
    """

    def __init__(self, window_seconds: int = 600):
        """
        Args:
            window_seconds: Time window to keep metrics (default: 600s = 10 minutes)
        """
        self.window_seconds = window_seconds
        self.frames: Deque[FrameMetrics] = deque()
        self.lock = Lock()

        # Session-wide counters (not time-windowed)
        self.session_start = time.time()
        self.total_frames = 0
        self.total_motion_frames = 0
        self.total_akaze_frames = 0
        self.total_skipped_frames = 0
        self.total_failed_frames = 0

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
        """Record metrics for a single frame."""
        with self.lock:
            # Add new frame
            frame = FrameMetrics(
                timestamp=time.time(),
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
            self.frames.append(frame)

            # Update session counters
            self.total_frames += 1
            if frame_type == 'motion':
                self.total_motion_frames += 1
            elif frame_type == 'akaze':
                self.total_akaze_frames += 1
            elif frame_type == 'skipped':
                self.total_skipped_frames += 1
            elif frame_type == 'failed':
                self.total_failed_frames += 1

            # Cleanup old frames (outside time window)
            cutoff_time = time.time() - self.window_seconds
            while self.frames and self.frames[0].timestamp < cutoff_time:
                self.frames.popleft()

    def get_statistics(self) -> Dict:
        """
        Compute comprehensive statistics from time-windowed data.

        Returns:
            Dictionary with rendered statistics including:
            - Session info (uptime, total frames)
            - Frame breakdown (motion/akaze/skipped/failed counts and percentages)
            - Timing stats (mean, median, P95, P99 for each stage)
            - FPS metrics
            - Match quality metrics
        """
        with self.lock:
            if not self.frames:
                return self._empty_stats()

            # Extract arrays for vectorized operations
            capture_times = np.array([f.capture_ms for f in self.frames])
            match_times = np.array([f.match_ms for f in self.frames])
            overlay_times = np.array([f.overlay_ms for f in self.frames])
            total_times = np.array([f.total_ms for f in self.frames])
            confidences = np.array([f.confidence for f in self.frames])
            inliers = np.array([f.inliers for f in self.frames])

            # Frame type counts (windowed)
            windowed_frames = list(self.frames)
            motion_count = sum(1 for f in windowed_frames if f.frame_type == 'motion')
            akaze_count = sum(1 for f in windowed_frames if f.frame_type == 'akaze')
            skipped_count = sum(1 for f in windowed_frames if f.frame_type == 'skipped')
            failed_count = sum(1 for f in windowed_frames if f.frame_type == 'failed')
            windowed_total = len(windowed_frames)

            # FPS calculation
            time_span = windowed_frames[-1].timestamp - windowed_frames[0].timestamp
            windowed_fps = windowed_total / time_span if time_span > 0 else 0

            # Session FPS
            session_duration = time.time() - self.session_start
            session_fps = self.total_frames / session_duration if session_duration > 0 else 0

            return {
                # Session info
                'session': {
                    'uptime_seconds': round(session_duration, 1),
                    'total_frames': self.total_frames,
                    'fps': round(session_fps, 2)
                },

                # Window info
                'window': {
                    'seconds': self.window_seconds,
                    'frames': windowed_total,
                    'fps': round(windowed_fps, 2)
                },

                # Frame breakdown (windowed)
                'frame_breakdown': {
                    'motion': {
                        'count': motion_count,
                        'percentage': round(motion_count / windowed_total * 100, 1) if windowed_total > 0 else 0
                    },
                    'akaze': {
                        'count': akaze_count,
                        'percentage': round(akaze_count / windowed_total * 100, 1) if windowed_total > 0 else 0
                    },
                    'skipped': {
                        'count': skipped_count,
                        'percentage': round(skipped_count / windowed_total * 100, 1) if windowed_total > 0 else 0
                    },
                    'failed': {
                        'count': failed_count,
                        'percentage': round(failed_count / windowed_total * 100, 1) if windowed_total > 0 else 0
                    }
                },

                # Timing statistics (all in milliseconds)
                'timing': {
                    'capture': self._compute_timing_stats(capture_times),
                    'matching': self._compute_timing_stats(match_times),
                    'overlay': self._compute_timing_stats(overlay_times),
                    'total': self._compute_timing_stats(total_times)
                },

                # Match quality
                'quality': {
                    'confidence': {
                        'mean': round(float(np.mean(confidences)), 3),
                        'median': round(float(np.median(confidences)), 3),
                        'p95': round(float(np.percentile(confidences, 95)), 3),
                        'min': round(float(np.min(confidences)), 3),
                        'max': round(float(np.max(confidences)), 3)
                    },
                    'inliers': {
                        'mean': round(float(np.mean(inliers)), 1),
                        'median': int(np.median(inliers)),
                        'p95': int(np.percentile(inliers, 95)),
                        'min': int(np.min(inliers)),
                        'max': int(np.max(inliers))
                    }
                },

                # Cascade matcher levels used
                'cascade_levels': self._compute_cascade_stats(windowed_frames),

                # Phase correlation movement
                'movement': self._compute_movement_stats(windowed_frames)
            }

    def _compute_timing_stats(self, times: np.ndarray) -> Dict:
        """Compute timing statistics from array of milliseconds."""
        if len(times) == 0:
            return {
                'mean': 0,
                'median': 0,
                'p95': 0,
                'p99': 0,
                'min': 0,
                'max': 0
            }

        return {
            'mean': round(float(np.mean(times)), 2),
            'median': round(float(np.median(times)), 2),
            'p95': round(float(np.percentile(times, 95)), 2),
            'p99': round(float(np.percentile(times, 99)), 2),
            'min': round(float(np.min(times)), 2),
            'max': round(float(np.max(times)), 2)
        }

    def _empty_stats(self) -> Dict:
        """Return empty statistics structure."""
        session_duration = time.time() - self.session_start
        return {
            'session': {
                'uptime_seconds': round(session_duration, 1),
                'total_frames': self.total_frames,
                'fps': 0
            },
            'window': {
                'seconds': self.window_seconds,
                'frames': 0,
                'fps': 0
            },
            'frame_breakdown': {
                'motion': {'count': 0, 'percentage': 0},
                'akaze': {'count': 0, 'percentage': 0},
                'skipped': {'count': 0, 'percentage': 0},
                'failed': {'count': 0, 'percentage': 0}
            },
            'timing': {
                'capture': self._compute_timing_stats(np.array([])),
                'matching': self._compute_timing_stats(np.array([])),
                'overlay': self._compute_timing_stats(np.array([])),
                'total': self._compute_timing_stats(np.array([]))
            },
            'quality': {
                'confidence': {'mean': 0, 'median': 0, 'p95': 0, 'min': 0, 'max': 0},
                'inliers': {'mean': 0, 'median': 0, 'p95': 0, 'min': 0, 'max': 0}
            }
        }

    def _compute_cascade_stats(self, frames: List[FrameMetrics]) -> Dict:
        """Compute statistics about cascade matcher scale usage."""
        if not frames:
            return {}

        level_counts = {}
        for f in frames:
            level = f.cascade_level
            level_counts[level] = level_counts.get(level, 0) + 1

        total = len(frames)
        return {
            level: {
                'count': count,
                'percentage': round(count / total * 100, 1)
            }
            for level, count in sorted(level_counts.items())
        }

    def _compute_movement_stats(self, frames: List[FrameMetrics]) -> Dict:
        """Compute statistics about phase correlation movement."""
        if not frames:
            return {
                'speed_px_s': {'mean': 0, 'median': 0, 'p95': 0, 'max': 0},
                'total_frames_with_movement': 0
            }

        speeds = np.array([f.motion_speed_px_s for f in frames if f.motion_speed_px_s > 0])

        if len(speeds) == 0:
            return {
                'speed_px_s': {'mean': 0, 'median': 0, 'p95': 0, 'max': 0},
                'total_frames_with_movement': 0
            }

        return {
            'speed_px_s': {
                'mean': round(float(np.mean(speeds)), 1),
                'median': round(float(np.median(speeds)), 1),
                'p95': round(float(np.percentile(speeds, 95)), 1),
                'max': round(float(np.max(speeds)), 1)
            },
            'total_frames_with_movement': len(speeds)
        }

    def reset(self):
        """Clear all metrics and reset session counters."""
        with self.lock:
            self.frames.clear()
            self.session_start = time.time()
            self.total_frames = 0
            self.total_motion_frames = 0
            self.total_akaze_frames = 0
            self.total_skipped_frames = 0
            self.total_failed_frames = 0
