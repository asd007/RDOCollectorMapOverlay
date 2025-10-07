"""
Continuous screenshot capture and matching service.
Orchestrates capture, matching, and viewport updates using focused components.

Thread: Background thread via CaptureLoop
Signals: viewport_updated (emitted to Qt main thread)
"""

import time
import threading
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass
from collections import deque

from PySide6.QtCore import QObject, Signal

from matching.viewport_tracker import Viewport
from core.capture.capture_loop import CaptureLoop
from core.capture.frame_processor import FrameProcessor
from core.matching.matching_coordinator import MatchingCoordinator
from core.monitoring.viewport_monitor import ViewportMonitor
from core.collectibles.cycle_manager import CycleManager
from core.monitoring.performance_monitor import PerformanceMonitor


# Legacy classes kept for backward compatibility
@dataclass
class FallbackReason:
    """Why we fell back to full search (legacy, unused in refactored version)."""
    FIRST_FRAME = "first_frame"
    ROI_MISS = "roi_miss"
    ZOOM_CHANGE = "zoom_change"
    TELEPORT = "teleport"
    LOW_CONFIDENCE = "low_confidence"
    PERIODIC = "periodic_correction"


class FallbackDetector:
    """
    Legacy fallback detector (kept for compatibility).
    Motion tracking is now handled by MatchingCoordinator.
    """
    def __init__(self):
        self.frames_since_full_search = 0
        self.confidence_history = deque(maxlen=3)
        self.periodic_interval = 10

    def should_fallback(self, current_match, previous_viewport, roi_info):
        return False, None  # Unused in refactored version

    def reset(self):
        self.frames_since_full_search = 0
        self.confidence_history.clear()


class ContinuousCaptureService(QObject):
    """
    Background service for continuous screenshot capture and matching.

    Delegates to focused components:
    - CaptureLoop: Thread management, timing, adaptive FPS
    - FrameProcessor: Capture, deduplication, preprocessing
    - MatchingCoordinator: Matcher orchestration, motion tracking
    - ViewportMonitor: Drift/pan tracking, accuracy stats
    - CycleManager: Periodic cycle detection and reload
    - PerformanceMonitor: Metrics aggregation

    Public API (maintained for backward compatibility):
    - start() / stop(): Control capture loop
    - viewport_updated signal: Emits (viewport dict, collectibles list)
    - get_latest_result(): Thread-safe result access
    - get_statistics(): Aggregated performance stats
    """

    # Qt signals for event-driven updates
    viewport_updated = Signal(object, object)  # Emits (viewport dict, collectibles list)

    def __init__(self, matcher, capture_func, collectibles_func, target_fps=5, parent=None):
        """
        Initialize continuous capture service.

        Args:
            matcher: CascadeScaleMatcher instance
            capture_func: Function that captures and preprocesses screenshot
            collectibles_func: Function(viewport) that returns visible collectibles
            target_fps: Initial target capture rate (default 5fps, will adapt)
            parent: QObject parent (required for proper Qt signal/slot functionality)
        """
        super().__init__(parent)

        # Core dependencies
        self.matcher = matcher
        self.capture_func = capture_func
        self.collectibles_func = collectibles_func

        # === COMPONENT DELEGATION ===
        # Extract responsibilities into focused components

        self.capture_loop = CaptureLoop(
            target_fps=target_fps,
            min_fps=5,
            max_fps=None,
            adaptive_fps_enabled=True
        )

        self.frame_processor = FrameProcessor(
            capture_func=capture_func,
            enable_deduplication=False,  # Disabled: causes lag during panning
            enable_map_detection=False   # Disabled: too strict
        )

        self.matching_coordinator = MatchingCoordinator(
            matcher=matcher,
            frame_interval=1.0 / target_fps,
            match_timeout=6.0
        )

        self.viewport_monitor = ViewportMonitor(
            history_size=100
        )

        self.cycle_manager = CycleManager(
            check_interval=300.0  # 5 minutes
        )

        self.performance_monitor = PerformanceMonitor(
            window_seconds=600  # 10 minutes
        )

        # === STATE ===

        # Thread-safe result sharing
        self.latest_result: Optional[Dict] = None
        self.result_lock = threading.Lock()

        # Lock-free viewport for PySide6 overlay (atomic with GIL)
        self._last_viewport: Optional[Dict] = None

        # Reference to ApplicationState for cycle reloading
        self.state = None

        # Legacy compatibility attributes
        self.tracker = self.matching_coordinator.tracker
        self.fallback_detector = FallbackDetector()  # Unused
        self.previous_viewport = None

        # Test data collection (optional)
        self.test_collector = None
        self.collect_test_data = False
        self.expected_times = {
            'Fast (25%)': 50,
            'Reliable (50%)': 100,
            'Optimized (70% fallback)': 130
        }
        self.deviation_threshold = 1.5

        # Legacy stats (for backward compatibility)
        self.stats = {
            'total_frames': 0,
            'roi_frames': 0,
            'full_search_frames': 0,
            'no_map_detected': 0,
            'duplicate_frames': 0,
            'skipped_frames': 0,
            'fallback_reasons': {},
            'match_times': deque(maxlen=100),
            'capture_times': deque(maxlen=100),
            'overlay_times': deque(maxlen=100),
            'total_times': deque(maxlen=100),
            'frame_intervals': deque(maxlen=100),
            'cascade_levels_used': deque(maxlen=100),
            'confidences': deque(maxlen=100),
            'inliers': deque(maxlen=100),
            'map_not_visible_frames': 0,
            'map_detection_times': deque(maxlen=100),
            'exceptions': deque(maxlen=10),
            'motion_only_frames': 0,
            'akaze_frames': 0
        }

        # FPS window tracking
        self.last_frame_time: Optional[float] = None
        self.fps_window_start = time.time()
        self.fps_window_frames = 0

        # Adaptive FPS (delegated to CaptureLoop but kept for compatibility)
        self.adaptive_fps_enabled = True
        self.min_fps = 5
        self.max_fps = None
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.processing_times = deque(maxlen=10)
        self.frames_since_fps_update = 0
        self.fps_adaptation_interval = 3

        # Profiling
        self.enable_profiling = False
        self.profile_interval = 100

    @property
    def running(self) -> bool:
        """Check if capture loop is running."""
        return self.capture_loop.running

    @property
    def last_viewport(self):
        """Lock-free getter for latest viewport (atomic read with GIL)."""
        return self._last_viewport

    def start(self):
        """Start continuous capture in background thread."""
        self.capture_loop.start(self._process_frame)

    def stop(self):
        """Stop continuous capture."""
        self.capture_loop.stop()

    def update_render_lag(self, lag_ms: float, drop_rate: float = 0.0):
        """
        Update measured render lag from frontend for adaptive extrapolation.

        Args:
            lag_ms: Measured lag from frontend (milliseconds)
            drop_rate: Frame drop rate (0.0-1.0)
        """
        self.matching_coordinator.update_render_lag(lag_ms)

        # Legacy: Adaptive backend FPS based on frontend capacity (kept for compatibility)
        if drop_rate > 0.15:  # >15% drops
            # Slow down backend to give frontend time to catch up
            new_fps = max(self.target_fps * 0.8, self.min_fps)
            if new_fps != self.target_fps:
                self.target_fps = new_fps
                self.frame_interval = 1.0 / new_fps
                self.matching_coordinator.update_frame_interval(self.frame_interval)

    def enable_test_collection(self, output_dir: str = "tests/data", max_per_zoom: int = 3):
        """
        Enable automatic test data collection for outlier frames.

        Args:
            output_dir: Directory to save test data
            max_per_zoom: Maximum samples to collect per zoom level
        """
        from tests.test_data_collector import TestDataCollector
        self.test_collector = TestDataCollector(output_dir, max_per_zoom=max_per_zoom)
        self.collect_test_data = True

    def disable_test_collection(self):
        """Disable test data collection."""
        self.collect_test_data = False
        if self.test_collector:
            self.test_collector.export_test_manifest()
        return self.test_collector.get_stats() if self.test_collector else None

    def get_latest_result(self) -> Optional[Dict]:
        """
        Get latest match result (thread-safe).

        Returns:
            Dict with:
                - success: bool
                - collectibles: List (empty if none in view)
                - viewport: Dict (if success)
                - error: str (if not success)
                - stats: Dict (performance metrics)
        """
        with self.result_lock:
            return self.latest_result.copy() if self.latest_result else None

    def _process_frame(self) -> float:
        """
        Process one frame (called by CaptureLoop).

        Returns:
            Processing time in seconds
        """
        frame_start = time.time()
        self.stats['total_frames'] += 1

        # DEBUG: Log first few frames
        if self.stats['total_frames'] <= 3:
            print(f"[CaptureService] Processing frame {self.stats['total_frames']}")

        # Track frame intervals for FPS calculation
        if self.last_frame_time is not None:
            frame_interval = (frame_start - self.last_frame_time) * 1000
            self.stats['frame_intervals'].append(frame_interval)

        self.last_frame_time = frame_start
        self.fps_window_frames += 1

        # === 1. CAPTURE & PREPROCESS ===
        capture_start = time.time()
        screenshot, is_duplicate, error = self.frame_processor.capture_and_preprocess()
        capture_time = (time.time() - capture_start) * 1000

        if error or screenshot is None:
            if self.stats['no_map_detected'] == 0:  # Log first error
                print(f"[CaptureService] Capture failed: {error or 'No screenshot'}")
            self.stats['no_map_detected'] += 1
            self._set_result({
                'success': False,
                'error': error or 'Capture failed',
                'collectibles': []
            })
            return 0.001

        if is_duplicate:
            self.stats['duplicate_frames'] += 1
            cached = self.frame_processor.get_cached_result()
            if cached:
                self._set_result(cached)
            return 0.001

        # === 2. MATCH ===
        match_result = self.matching_coordinator.match(screenshot)

        if not match_result or not match_result.get('success'):
            if self.stats['akaze_frames'] == 0:  # Log first match failure
                print(f"[CaptureService] Match failed: {match_result}")
            self.stats['no_map_detected'] += 1
            self._set_result({
                'success': False,
                'error': 'Match failed',
                'collectibles': []
            })
            return (time.time() - frame_start)

        # === 3. PROCESS MATCH RESULT ===
        self.stats['full_search_frames'] += 1
        self.stats['capture_times'].append(capture_time)
        self.stats['match_times'].append(match_result['match_time_ms'])

        # Track cascade info
        cascade_info = match_result.get('cascade_info', {})
        self.stats['cascade_levels_used'].append(cascade_info.get('final_level', 'unknown'))
        self.stats['confidences'].append(match_result['confidence'])
        self.stats['inliers'].append(match_result['inliers'])

        # Track motion stats using match_type
        match_type = match_result.get('match_type', 'akaze')
        if match_type == 'motion_only':
            self.stats['motion_only_frames'] += 1
        else:
            self.stats['akaze_frames'] += 1

        # Create viewport
        viewport = Viewport(
            x=match_result['map_x'],
            y=match_result['map_y'],
            width=match_result['map_w'],
            height=match_result['map_h'],
            confidence=match_result['confidence'],
            timestamp=time.time()
        )

        # === 4. GET PREDICTED VIEWPORT ===
        viewport_dict = self.matching_coordinator.get_predicted_viewport(viewport)

        # === 5. GET VISIBLE COLLECTIBLES ===
        overlay_start = time.time()
        collectibles = self.collectibles_func(viewport)
        overlay_time = (time.time() - overlay_start) * 1000
        self.stats['overlay_times'].append(overlay_time)

        # === 6. UPDATE MONITORING ===
        motion_pred = cascade_info.get('motion_prediction')
        akaze_used = match_type != 'motion_only'  # Use match_type instead of akaze_bypassed

        self.viewport_monitor.update_drift_tracking(
            frame_number=self.stats['total_frames'],
            viewport=viewport,
            collectibles=collectibles,
            match_result=match_result,
            akaze_used=akaze_used
        )

        self.viewport_monitor.update_pan_tracking(
            frame_number=self.stats['total_frames'],
            motion_prediction=motion_pred
        )

        # === 7. EMIT SIGNAL TO QT ===
        self._last_viewport = viewport_dict

        # DEBUG: Log first few successful viewport updates
        if self.stats['akaze_frames'] <= 3:
            print(f"[CaptureService] Viewport update {self.stats['akaze_frames']}: x={viewport.x:.1f}, y={viewport.y:.1f}, confidence={viewport.confidence:.2f}, collectibles={len(collectibles)}")

        self.viewport_updated.emit(viewport_dict, collectibles)

        # === 8. CHECK CYCLE RELOAD ===
        if self.cycle_manager.should_check_now():
            self.cycle_manager.check_and_reload(self.state)

        # === 9. RECORD PERFORMANCE ===
        total_time = (time.time() - frame_start) * 1000
        self.stats['total_times'].append(total_time)

        frame_type = 'motion' if match_type == 'motion_only' else 'akaze'
        motion_offset = motion_pred.get('offset_px', (0, 0)) if motion_pred else (0, 0)

        self.performance_monitor.record_frame(
            capture_ms=capture_time,
            match_ms=match_result['match_time_ms'],
            overlay_ms=overlay_time,
            total_ms=total_time,
            confidence=match_result['confidence'],
            inliers=match_result['inliers'],
            frame_type=frame_type,
            motion_offset_px=motion_offset,
            cascade_level=cascade_info.get('final_level', 'unknown')
        )

        # === 10. TEST DATA COLLECTION (OPTIONAL) ===
        if self.collect_test_data and self.test_collector:
            try:
                self.test_collector.maybe_collect(
                    screenshot=screenshot,
                    match_result=match_result,
                    viewport=viewport,
                    collectibles=collectibles,
                    expected_times=self.expected_times,
                    deviation_threshold=self.deviation_threshold
                )
            except Exception as e:
                print(f"[TestCollection] Error: {e}")

        # Update cached result for deduplication
        result = {
            'success': True,
            'viewport': viewport_dict,
            'collectibles': collectibles,
            'confidence': match_result['confidence']
        }
        self.frame_processor.cache_result(result)
        self._set_result(result)

        # Reset FPS window periodically
        if time.time() - self.fps_window_start >= 5.0:
            self.fps_window_start = time.time()
            self.fps_window_frames = 0

        return (time.time() - frame_start)

    def _set_result(self, result: Dict):
        """Thread-safe result update."""
        result['stats'] = self.get_statistics()
        with self.result_lock:
            self.latest_result = result

    def get_statistics(self) -> Dict:
        """
        Get aggregated performance statistics from all components.

        Returns:
            Dict with comprehensive stats from all components
        """
        # Aggregate stats from components
        capture_loop_stats = self.capture_loop.get_fps_stats()
        frame_proc_stats = self.frame_processor.get_stats()
        matching_stats = self.matching_coordinator.get_stats()
        drift_stats = self.viewport_monitor.get_drift_stats()
        pan_stats = self.viewport_monitor.get_pan_stats()
        cycle_stats = self.cycle_manager.get_stats()
        perf_stats = self.performance_monitor.get_stats()

        # Legacy stats calculation (for backward compatibility)
        total_times = list(self.stats['total_times'])
        match_times = list(self.stats['match_times'])
        capture_times = list(self.stats['capture_times'])
        overlay_times = list(self.stats['overlay_times'])
        confidences = list(self.stats['confidences'])
        inliers = list(self.stats['inliers'])

        latency_stats = None
        if total_times:
            latency_stats = {
                'mean_ms': float(np.mean(total_times)),
                'median_ms': float(np.median(total_times)),
                'p95_ms': float(np.percentile(total_times, 95)),
                'best_ms': float(np.min(total_times)),
                'worst_ms': float(np.max(total_times)),
                'fps_mean': float(1000 / np.mean(total_times)),
                'fps_median': float(1000 / np.median(total_times))
            }

        return {
            'backend_fps': capture_loop_stats['actual_fps'],
            'target_fps': capture_loop_stats['target_fps'],
            'adaptive_fps': {
                'enabled': True,
                'current_target_fps': capture_loop_stats['target_fps'],
                'utilization_pct': capture_loop_stats['utilization'] * 100,
                'min_fps': self.min_fps,
                'max_fps': self.max_fps
            },
            'frames': {
                'total': self.stats['total_frames'],
                'successful': self.stats['full_search_frames'],
                'failed': self.stats['no_map_detected'],
                'duplicate': self.stats['duplicate_frames'],
                'skipped': capture_loop_stats['skipped_frames'],
                'success_rate': (
                    self.stats['full_search_frames'] / self.stats['total_frames'] * 100
                    if self.stats['total_frames'] > 0 else 0
                )
            },
            'motion_tracking': {
                'motion_only_frames': self.stats['motion_only_frames'],
                'akaze_frames': self.stats['akaze_frames'],
                'motion_only_ratio': matching_stats['motion_only_ratio']
            },
            'latency': latency_stats,
            'timing_breakdown': {
                'capture_mean_ms': float(np.mean(capture_times)) if capture_times else 0,
                'match_mean_ms': float(np.mean(match_times)) if match_times else 0,
                'match_median_ms': float(np.median(match_times)) if match_times else 0,
                'match_p95_ms': float(np.percentile(match_times, 95)) if match_times else 0,
                'overlay_mean_ms': float(np.mean(overlay_times)) if overlay_times else 0
            },
            'quality': {
                'confidence_mean': float(np.mean(confidences)) if confidences else 0,
                'confidence_median': float(np.median(confidences)) if confidences else 0,
                'inliers_mean': float(np.mean(inliers)) if inliers else 0,
                'inliers_median': float(np.median(inliers)) if inliers else 0
            },
            'drift_tracking': drift_stats,
            'pan_tracking': pan_stats,
            'cycle_management': cycle_stats,
            'component_stats': {
                'capture_loop': capture_loop_stats,
                'frame_processor': frame_proc_stats,
                'matching_coordinator': matching_stats
            },
            'performance_monitor': perf_stats
        }
