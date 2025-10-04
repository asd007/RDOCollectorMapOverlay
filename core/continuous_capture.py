"""
Continuous screenshot capture and matching service.
Runs in background thread, maintains latest match state.
"""

import time
import threading
import numpy as np
import hashlib
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from collections import deque

from matching.viewport_tracker import ViewportKalmanTracker, Viewport
from core.map_detector import is_map_visible


@dataclass
class FallbackReason:
    """Why we fell back to full search."""
    FIRST_FRAME = "first_frame"
    ROI_MISS = "roi_miss"
    ZOOM_CHANGE = "zoom_change"
    TELEPORT = "teleport"
    LOW_CONFIDENCE = "low_confidence"
    PERIODIC = "periodic_correction"


class FallbackDetector:
    """
    Detect when ROI tracking should fallback to full search.
    We don't know viewport size beforehand - we infer it from match results.
    """

    def __init__(self):
        self.frames_since_full_search = 0
        self.confidence_history = deque(maxlen=3)
        self.periodic_interval = 10  # Full search every 10 frames (~2s at 5fps)

    def should_fallback(
        self,
        current_match: Optional[Dict],
        previous_viewport: Optional[Viewport],
        roi_info: Optional[Dict]
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if we should abandon ROI and do full search.

        Args:
            current_match: Result from ROI search (None if failed)
            previous_viewport: Last known viewport
            roi_info: ROI prediction info

        Returns:
            (should_fallback, reason)
        """
        self.frames_since_full_search += 1

        # First frame or no previous viewport
        if previous_viewport is None:
            return True, FallbackReason.FIRST_FRAME

        # ROI search failed entirely
        if current_match is None:
            return True, FallbackReason.ROI_MISS

        # Match succeeded but confidence is low
        confidence = current_match.get('confidence', 0)
        self.confidence_history.append(confidence)

        if len(self.confidence_history) == 3:
            avg_confidence = np.mean(self.confidence_history)
            if avg_confidence < 0.65:
                self.confidence_history.clear()
                return True, FallbackReason.LOW_CONFIDENCE

        # Detect zoom change (viewport size changed significantly)
        current_w = current_match.get('map_w', 0)
        previous_w = previous_viewport.width

        if current_w > 0 and previous_w > 0:
            scale_ratio = current_w / previous_w
            # 40% change = likely zoom in/out
            if scale_ratio > 1.4 or scale_ratio < 0.71:
                return True, FallbackReason.ZOOM_CHANGE

        # Detect teleport (viewport jumped too far)
        current_cx = current_match.get('map_x', 0) + current_match.get('map_w', 0) / 2
        current_cy = current_match.get('map_y', 0) + current_match.get('map_h', 0) / 2
        previous_cx, previous_cy = previous_viewport.center

        distance = np.sqrt((current_cx - previous_cx)**2 + (current_cy - previous_cy)**2)
        viewport_diagonal = np.sqrt(previous_viewport.width**2 + previous_viewport.height**2)

        # Jumped more than 1.5x viewport size = likely fast travel
        if distance > viewport_diagonal * 1.5:
            return True, FallbackReason.TELEPORT

        # Periodic full search to correct drift
        if self.frames_since_full_search >= self.periodic_interval:
            self.frames_since_full_search = 0
            return True, FallbackReason.PERIODIC

        return False, None

    def reset(self):
        """Reset after successful full search."""
        self.frames_since_full_search = 0
        self.confidence_history.clear()


class ContinuousCaptureService:
    """
    Background service for continuous screenshot capture and matching.
    Maintains latest match state for frontend polling and WebSocket push.
    """

    def __init__(self, matcher, capture_func, collectibles_func, target_fps=5, socketio=None):
        """
        Initialize continuous capture service.

        Args:
            matcher: CascadeScaleMatcher instance
            capture_func: Function that captures and preprocesses screenshot
            collectibles_func: Function(viewport) that returns visible collectibles
            target_fps: Target capture rate (default 5fps)
            socketio: SocketIO instance for push updates (optional)
        """
        self.matcher = matcher
        self.capture_func = capture_func
        self.collectibles_func = collectibles_func
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.socketio = socketio

        # State
        self.running = False
        self.thread = None
        self.latest_result = None
        self.result_lock = threading.Lock()

        # Frame deduplication
        self.previous_frame_hash = None
        self.cached_result = None

        # ROI tracking
        self.tracker = ViewportKalmanTracker(dt=self.frame_interval)
        self.fallback_detector = FallbackDetector()
        self.previous_viewport = None

        # Test data collection (only capture outliers)
        self.test_collector = None
        self.collect_test_data = False
        self.expected_times = {
            'Fast (25%)': 50,      # Expected ~50ms for 25% scale (target)
            'Reliable (50%)': 100, # Expected ~100ms for 50% scale (target, currently 152ms)
            'Optimized (70% fallback)': 130  # Expected ~130ms for 70% scale (target)
        }
        self.deviation_threshold = 1.5  # Capture if >50% slower than expected

        # Metrics
        self.stats = {
            'total_frames': 0,
            'roi_frames': 0,
            'full_search_frames': 0,
            'no_map_detected': 0,
            'duplicate_frames': 0,  # Frames skipped due to identical content
            'fallback_reasons': {},
            'match_times': deque(maxlen=100),
            'capture_times': deque(maxlen=100),
            'overlay_times': deque(maxlen=100),
            'total_times': deque(maxlen=100),
            'cascade_levels_used': deque(maxlen=100),
            'confidences': deque(maxlen=100),
            'inliers': deque(maxlen=100),
            'map_not_visible_frames': 0,
            'map_detection_times': deque(maxlen=100),
            'exceptions': deque(maxlen=10)  # Track last 10 exceptions
        }

        # Profiling (disabled console output, stats still collected)
        self.enable_profiling = False
        self.profile_interval = 50  # Print stats every N frames

    def start(self):
        """Start continuous capture in background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop continuous capture."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def enable_test_collection(self, output_dir: str = "tests/data", max_per_zoom: int = 3):
        """
        Enable automatic test data collection for outlier frames.

        Args:
            output_dir: Directory to save test data
            max_per_zoom: Maximum samples to collect per zoom level (default: 3)
        """
        # Import only when needed to avoid production dependency on test code
        from tests.test_data_collector import TestDataCollector
        self.test_collector = TestDataCollector(output_dir, max_per_zoom=max_per_zoom)
        self.collect_test_data = True

    def disable_test_collection(self):
        """Disable test data collection."""
        self.collect_test_data = False
        if self.test_collector:
            # Export manifest
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

    def _capture_loop(self):
        """Main capture loop (runs in background thread)."""
        next_capture_time = time.time()

        while self.running:
            current_time = time.time()

            if current_time >= next_capture_time:
                try:
                    self._process_frame()
                except Exception as e:
                    # Track exceptions but don't print (available via /profiling-stats)
                    import traceback
                    self.stats['exceptions'].append({
                        'timestamp': time.time(),
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    })
                    self.stats['no_map_detected'] += 1

                next_capture_time += self.frame_interval

            # Sleep to avoid busy waiting
            time.sleep(0.01)

    def _process_frame(self):
        """Capture and process one frame."""
        frame_start = time.time()
        self.stats['total_frames'] += 1

        # Capture screenshot
        capture_start = time.time()
        try:
            screenshot, error = self.capture_func()
            capture_time = (time.time() - capture_start) * 1000

            if error:
                self._set_result({
                    'success': False,
                    'error': error,
                    'collectibles': []
                })
                self.stats['no_map_detected'] += 1
                return
        except Exception as e:
            self._set_result({
                'success': False,
                'error': f"Capture failed: {e}",
                'collectibles': []
            })
            self.stats['no_map_detected'] += 1
            return

        # Frame deduplication: Skip matching if frame is identical to previous
        frame_hash = hashlib.md5(screenshot.tobytes()).hexdigest()
        if frame_hash == self.previous_frame_hash and self.cached_result is not None:
            # Identical frame - return cached result (skip expensive matching)
            self.stats['duplicate_frames'] += 1
            self._set_result(self.cached_result)
            return

        self.previous_frame_hash = frame_hash

        # Map detection DISABLED - always try matching
        # (Map detector was too strict, causing low success rate)
        map_detect_time = 0

        # Pass RAW screenshot to cascade matcher
        # Cascade matcher will handle: grayscale  ->  resize  ->  preprocess per level
        match_start = time.time()
        result = self.matcher.match(screenshot)  # Raw screenshot (BGR)
        match_time = (time.time() - match_start) * 1000

        # Process result
        if result and result.get('success'):
            # Only track stats for successful matches
            self.stats['full_search_frames'] += 1
            match_type = 'cascade'

            self.stats['capture_times'].append(capture_time)
            self.stats['match_times'].append(match_time)
            # Track cascade info
            cascade_info = result.get('cascade_info', {})
            cascade_level = cascade_info.get('final_level', 'unknown')
            self.stats['cascade_levels_used'].append(cascade_level)
            self.stats['confidences'].append(result['confidence'])
            self.stats['inliers'].append(result['inliers'])

            # Create viewport from result
            viewport = Viewport(
                x=result['map_x'],
                y=result['map_y'],
                width=result['map_w'],
                height=result['map_h'],
                confidence=result['confidence'],
                timestamp=time.time()
            )

            # Get visible collectibles
            overlay_start = time.time()
            collectibles = self.collectibles_func(viewport)
            overlay_time = (time.time() - overlay_start) * 1000
            self.stats['overlay_times'].append(overlay_time)

            # Total time
            total_time = (time.time() - frame_start) * 1000
            self.stats['total_times'].append(total_time)

            # Test data collection: Save outlier frames for optimization
            if self.collect_test_data and self.test_collector:
                expected_time = self.expected_times.get(cascade_level, 100)
                if match_time > expected_time * self.deviation_threshold:
                    # This frame took significantly longer than expected - save it
                    timing_data = {
                        'capture_ms': capture_time,
                        'match_ms': match_time,
                        'overlay_ms': overlay_time,
                        'total_ms': total_time
                    }
                    try:
                        self.test_collector.save_test_case(
                            screenshot=screenshot,
                            match_result=result,
                            timing=timing_data,
                            cascade_level=cascade_level
                        )
                    except Exception as e:
                        # Don't let test collection errors break the main loop
                        pass

            # Set result
            result_data = {
                'success': True,
                'collectibles': collectibles,
                'viewport': {
                    'x': viewport.x,
                    'y': viewport.y,
                    'width': viewport.width,
                    'height': viewport.height,
                    'center': viewport.center
                },
                'confidence': result['confidence'],
                'match_type': match_type,
                'timing': {
                    'capture_ms': capture_time,
                    'map_detection_ms': map_detect_time,
                    'match_ms': match_time,
                    'overlay_ms': overlay_time,
                    'total_ms': total_time
                },
                'cascade_level': cascade_level,
                'map_visible': True
            }

            # Cache result for frame deduplication (without stats to avoid stale data)
            self.cached_result = {k: v for k, v in result_data.items() if k != 'timing'}

            self._set_result(result_data)

            # Print profiling info
            if self.enable_profiling and self.stats['total_frames'] % self.profile_interval == 0:
                self._print_profiling_stats()

        else:
            # Match failed - don't track timing stats for failures
            failed_result = {
                'success': False,
                'error': result.get('error', 'Match failed') if result else 'Matcher returned None',
                'collectibles': []
            }

            # Cache failed result for deduplication
            self.cached_result = failed_result

            self._set_result(failed_result)
            self.stats['no_map_detected'] += 1

    def _match_in_roi(self, screenshot, roi) -> Optional[Dict]:
        """
        Match within predicted ROI.

        Args:
            screenshot: Preprocessed screenshot
            roi: Dict with x, y, width, height

        Returns:
            Match result or None
        """
        # Extract ROI from detection map (matcher's reference features)
        # This is a simplified version - actual implementation would need
        # to constrain AKAZE search to ROI bounds
        # For now, we just do full match (ROI optimization is future work)
        return self.matcher.match(screenshot)

    def _set_result(self, result: Dict):
        """Thread-safe result update and push via WebSocket."""
        # Add stats
        result['stats'] = self._get_stats()

        with self.result_lock:
            self.latest_result = result

        # Push update to frontend via WebSocket (if available)
        if self.socketio:
            try:
                self.socketio.emit('match_update', result)
            except Exception:
                # Silently ignore WebSocket errors (e.g., no clients connected)
                pass

    def _record_fallback(self, reason: str):
        """Record fallback reason in stats."""
        if reason not in self.stats['fallback_reasons']:
            self.stats['fallback_reasons'][reason] = 0
        self.stats['fallback_reasons'][reason] += 1

    def _print_profiling_stats(self):
        """Print profiling statistics to console (ONLY successful matches)."""
        if not self.stats['match_times']:
            return

        capture_times = list(self.stats['capture_times'])
        match_times = list(self.stats['match_times'])
        overlay_times = list(self.stats['overlay_times'])
        total_times = list(self.stats['total_times'])
        confidences = list(self.stats['confidences'])
        inliers = list(self.stats['inliers'])
        map_detection_times = list(self.stats['map_detection_times'])

        successful_matches = len(match_times)
        success_rate = (successful_matches / max(1, self.stats['total_frames'])) * 100
        map_not_visible = self.stats['map_not_visible_frames']

        # Count cascade level usage
        cascade_counts = {}
        for level in self.stats['cascade_levels_used']:
            cascade_counts[level] = cascade_counts.get(level, 0) + 1

        print("\n" + "="*70)
        print(f"PROFILING STATS - SUCCESSFUL MATCHES ONLY (Frame {self.stats['total_frames']})")
        print("="*70)
        print(f"Total frames: {self.stats['total_frames']}")
        print(f"  Successful matches: {successful_matches} ({success_rate:.1f}%)")
        print(f"  Map not visible: {map_not_visible} ({map_not_visible/max(1,self.stats['total_frames'])*100:.1f}%)")
        print(f"  Failed: {self.stats['no_map_detected']}")

        if total_times:
            print(f"\nFRONTEND FPS (what user experiences on successful matches):")
            print(f"  Mean:   {np.mean(total_times):.1f}ms = {1000/np.mean(total_times):.1f} fps")
            print(f"  Median: {np.median(total_times):.1f}ms = {1000/np.median(total_times):.1f} fps")
            print(f"  P95:    {np.percentile(total_times, 95):.1f}ms = {1000/np.percentile(total_times, 95):.1f} fps")

        print(f"\nTiming Breakdown (last {successful_matches} successful matches):")
        if capture_times:
            print(f"  Capture:       {np.mean(capture_times):.1f}ms (median {np.median(capture_times):.1f}ms)")
        if map_detection_times:
            print(f"  Map Detection: {np.mean(map_detection_times):.1f}ms (median {np.median(map_detection_times):.1f}ms)")
        if match_times:
            print(f"  Matching:      {np.mean(match_times):.1f}ms (median {np.median(match_times):.1f}ms)")
        if overlay_times:
            print(f"  Overlay:       {np.mean(overlay_times):.1f}ms (median {np.median(overlay_times):.1f}ms)")

        if confidences:
            print(f"\nMatch Quality:")
            print(f"  Confidence: {np.mean(confidences):.2%} (median {np.median(confidences):.2%})")
            print(f"  Inliers:    {np.mean(inliers):.0f} (median {np.median(inliers):.0f})")

        if cascade_counts:
            print(f"\nCascade Level Usage:")
            for level, count in sorted(cascade_counts.items()):
                pct = (count / successful_matches) * 100
                print(f"  {level}: {count} ({pct:.1f}%)")

        print("="*70 + "\n")

    def _get_stats(self) -> Dict:
        """Get current performance stats."""
        match_times = list(self.stats['match_times'])
        capture_times = list(self.stats['capture_times'])
        overlay_times = list(self.stats['overlay_times'])
        total_times = list(self.stats['total_times'])

        success_rate = ((self.stats['total_frames'] - self.stats['no_map_detected']) / max(1, self.stats['total_frames'])) * 100

        return {
            'total_frames': self.stats['total_frames'],
            'success_rate': success_rate,
            'capture_time_mean_ms': np.mean(capture_times) if capture_times else 0,
            'match_time_mean_ms': np.mean(match_times) if match_times else 0,
            'match_time_median_ms': np.median(match_times) if match_times else 0,
            'match_time_p95_ms': np.percentile(match_times, 95) if match_times else 0,
            'overlay_time_mean_ms': np.mean(overlay_times) if overlay_times else 0,
            'total_time_mean_ms': np.mean(total_times) if total_times else 0,
            'total_time_median_ms': np.median(total_times) if total_times else 0,
            'frontend_fps_mean': 1000 / np.mean(total_times) if total_times else 0,
            'frontend_fps_median': 1000 / np.median(total_times) if total_times else 0
        }
