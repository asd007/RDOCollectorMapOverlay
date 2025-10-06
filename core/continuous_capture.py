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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from PySide6.QtCore import QObject, Signal

from matching.viewport_tracker import ViewportKalmanTracker, Viewport
from core.map_detector import is_map_visible
from core.metrics import MetricsTracker


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


class ContinuousCaptureService(QObject):
    """
    Background service for continuous screenshot capture and matching.
    Maintains latest match state for frontend polling and WebSocket push.
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

        self.matcher = matcher
        self.capture_func = capture_func
        self.collectibles_func = collectibles_func
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps

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

        # Latest viewport for PySide6 overlay
        # Lock-free: Use signal for updates, simple read for polling fallback
        self._last_viewport = None

        # Adaptive FPS control
        self.adaptive_fps_enabled = True
        self.min_fps = 5  # Minimum FPS when system is slow
        self.max_fps = None  # No maximum - let system find its limit
        self.processing_times = deque(maxlen=10)  # Track recent processing times (smaller window = faster adaptation)
        self.fps_adaptation_interval = 3  # Recalculate target FPS every N frames (more aggressive)
        self.frames_since_fps_update = 0

        # Test data collection (only capture outliers)
        self.test_collector = None
        self.collect_test_data = False
        self.expected_times = {
            'Fast (25%)': 50,      # Expected ~50ms for 25% scale (target)
            'Reliable (50%)': 100, # Expected ~100ms for 50% scale (target, currently 152ms)
            'Optimized (70% fallback)': 130  # Expected ~130ms for 70% scale (target)
        }
        self.deviation_threshold = 1.5  # Capture if >50% slower than expected

        # Cycle change detection
        self.last_cycle_check = time.time()
        self.cycle_check_interval = 300  # Check every 5 minutes
        self.state = None  # Reference to OverlayState (for reloading collectibles)

        # Metrics
        self.stats = {
            'total_frames': 0,
            'roi_frames': 0,
            'full_search_frames': 0,
            'no_map_detected': 0,
            'duplicate_frames': 0,  # Frames skipped due to identical content
            'skipped_frames': 0,  # Frames skipped due to timing (late)
            'fallback_reasons': {},
            'match_times': deque(maxlen=100),
            'capture_times': deque(maxlen=100),
            'overlay_times': deque(maxlen=100),
            'total_times': deque(maxlen=100),
            'frame_intervals': deque(maxlen=100),  # Time between frames (for FPS calculation)
            'cascade_levels_used': deque(maxlen=100),
            'confidences': deque(maxlen=100),
            'inliers': deque(maxlen=100),
            'map_not_visible_frames': 0,
            'map_detection_times': deque(maxlen=100),
            'exceptions': deque(maxlen=10),  # Track last 10 exceptions
            'motion_only_frames': 0,  # Frames using pure motion tracking
            'akaze_frames': 0  # Frames using AKAZE matching
        }

        # FPS tracking
        self.last_frame_time = None
        self.fps_window_start = time.time()
        self.fps_window_frames = 0

        # Modern metrics tracker (replaces manual stats dict for API endpoints)
        self.metrics = MetricsTracker(window_seconds=600)  # 10 minutes

        # Profiling (disabled console spam - use /profiling-stats endpoint instead)
        self.enable_profiling = False
        self.profile_interval = 100  # Print stats every N frames

        # Drift tracking - monitor one collectible to detect coordinate errors
        self.drift_tracking_collectible = None  # Will be randomly selected
        self.drift_history = deque(maxlen=100)  # Track screen position over time

        # Pan tracking - monitor viewport movement speed/acceleration
        self.pan_history = deque(maxlen=100)  # Track viewport position over time
        self.last_viewport_pos = None
        self.last_viewport_time = None

    def _adapt_fps(self):
        """
        Adapt target FPS based on recent processing times.

        Aggressive strategy:
        - If utilization < 60%: increase FPS by 50% (fast ramp-up)
        - If utilization 60-75%: increase FPS by 20% (fine-tuning)
        - If utilization 75-85%: stay at current FPS (sweet spot)
        - If utilization > 85%: decrease FPS by 30% (avoid overload)
        - No maximum FPS - let system find its natural limit
        """
        if len(self.processing_times) < 3:
            return  # Need at least 3 samples

        # Calculate P90 processing time (less conservative than P95)
        p90_time = np.percentile(list(self.processing_times), 90)

        # Current frame budget
        current_budget = self.frame_interval

        # Calculate utilization
        utilization = p90_time / current_budget

        old_fps = self.target_fps

        if utilization < 0.6:
            # System can go much faster - aggressive increase
            new_fps = self.target_fps * 1.5
        elif utilization < 0.75:
            # System has headroom - moderate increase
            new_fps = self.target_fps * 1.2
        elif utilization > 0.85:
            # System struggling - back off
            new_fps = max(self.target_fps * 0.7, self.min_fps)
        else:
            # Sweet spot (75-85% utilization) - no change
            new_fps = self.target_fps

        # Apply minimum FPS constraint only
        new_fps = max(new_fps, self.min_fps)

        if abs(new_fps - old_fps) > 0.5:  # Only update if significant change
            self.target_fps = new_fps
            self.frame_interval = 1.0 / new_fps

            # Update tracker dt for motion prediction
            if hasattr(self.tracker, 'dt'):
                self.tracker.dt = self.frame_interval

    @property
    def last_viewport(self):
        """Lock-free getter for latest viewport (atomic read with GIL)"""
        return self._last_viewport

    def start(self):
        """Start continuous capture in background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def update_render_lag(self, lag_ms: float, drop_rate: float = 0.0):
        """
        Update measured render lag from frontend for adaptive extrapolation.
        Called by frontend every second with actual measured lag.

        Also adapts backend FPS based on frontend capacity.

        Args:
            lag_ms: Render lag in milliseconds (P90)
            drop_rate: Fraction of frames dropped (0.0-1.0)
        """
        self.measured_render_lag_ms = lag_ms

        # Adaptive backend pacing based on frame drops
        # Target: 10-20% frame drop rate (backend runs faster, frontend has fresh data)
        # Too many drops (>30%): Backend too fast, slow down
        # Too few drops (<5%): Backend too slow, speed up
        if drop_rate > 0.3:
            # Too many drops - backend is overwhelming frontend
            current_interval = self.frame_interval
            new_interval = current_interval * 1.2  # Slow down by 20%
            new_fps = 1.0 / new_interval

            if new_fps >= self.min_fps:
                self.frame_interval = new_interval
                print(f"[Adaptive Backend] Drop rate {drop_rate*100:.0f}% too high - reducing to {new_fps:.1f} FPS")
        elif drop_rate < 0.05 and lag_ms < 30.0:
            # Very few drops and frontend is fast - backend could go faster
            current_interval = self.frame_interval
            new_interval = current_interval * 0.9  # Speed up by 10%
            new_fps = 1.0 / new_interval

            # Only speed up if we have processing headroom
            if self.processing_times:
                avg_processing = sum(self.processing_times) / len(self.processing_times)
                if avg_processing / 1000.0 < new_interval * 0.7:  # Using <70% of budget
                    self.frame_interval = new_interval
                    print(f"[Adaptive Backend] Drop rate {drop_rate*100:.0f}% low, frontend fast - increasing to {new_fps:.1f} FPS")

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
        """Main capture loop with adaptive FPS and intelligent frame skipping."""
        next_capture_time = time.time()

        while self.running:
            current_time = time.time()

            # Check for cycle changes every 5 minutes
            if current_time - self.last_cycle_check >= self.cycle_check_interval:
                self._check_and_reload_cycles()
                self.last_cycle_check = current_time

            if current_time >= next_capture_time:
                frame_start = current_time

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

                # Measure actual processing time
                processing_time = time.time() - frame_start
                self.processing_times.append(processing_time)

                # Adaptive FPS: Adjust target based on recent processing times
                if self.adaptive_fps_enabled:
                    self.frames_since_fps_update += 1
                    if self.frames_since_fps_update >= self.fps_adaptation_interval:
                        self._adapt_fps()
                        self.frames_since_fps_update = 0

                # Intelligent frame skipping: If we're behind schedule, skip to current time
                # This prevents accumulating lag when processing can't keep up
                ideal_next_time = next_capture_time + self.frame_interval
                time_until_next = ideal_next_time - time.time()

                if time_until_next < -self.frame_interval:
                    # We're more than one frame behind - skip ahead to current time
                    frames_behind = int(abs(time_until_next) / self.frame_interval)
                    self.stats['skipped_frames'] += frames_behind
                    next_capture_time = time.time()  # Reset to now
                else:
                    # Normal case: schedule next frame
                    next_capture_time = ideal_next_time

            # Sleep to avoid busy waiting (but wake up frequently to check)
            time.sleep(0.001)  # 1ms sleep instead of 10ms for faster response

    def _process_frame(self):
        """Capture and process one frame."""
        frame_start = time.time()
        self.stats['total_frames'] += 1

        # Track frame intervals for FPS calculation
        if self.last_frame_time is not None:
            frame_interval = (frame_start - self.last_frame_time) * 1000
            self.stats['frame_intervals'].append(frame_interval)

            # Detect skipped frames (interval > 1.5x expected)
            expected_interval = self.frame_interval * 1000
            if frame_interval > expected_interval * 1.5:
                self.stats['skipped_frames'] += 1

        self.last_frame_time = frame_start
        self.fps_window_frames += 1

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

        # Frame deduplication DISABLED - causes lag during smooth panning
        # MD5 hash can match on similar frames even when viewport has moved slightly
        # With motion prediction, matching is fast enough (~10-20ms) to run every frame
        #
        # frame_hash = hashlib.md5(screenshot.tobytes()).hexdigest()
        # if frame_hash == self.previous_frame_hash and self.cached_result is not None:
        #     self.stats['duplicate_frames'] += 1
        #     self._set_result(self.cached_result)
        #     return
        # self.previous_frame_hash = frame_hash

        # Map detection DISABLED - always try matching
        # (Map detector was too strict, causing low success rate)
        map_detect_time = 0

        # Pass RAW screenshot to cascade matcher with timeout
        # Cascade matcher will handle: grayscale  ->  resize  ->  preprocess per level
        match_start = time.time()

        # Timeout matcher to 6 seconds max (prevents hanging on failed searches)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.matcher.match, screenshot)
                result = future.result(timeout=6.0)  # 6 second timeout
            match_time = (time.time() - match_start) * 1000
        except FuturesTimeoutError:
            match_time = (time.time() - match_start) * 1000
            result = None

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

            # Track motion prediction stats
            if 'prediction_times' not in self.stats:
                self.stats['prediction_times'] = deque(maxlen=100)
                self.stats['prediction_used_count'] = 0
                self.stats['roi_used_count'] = 0

            if cascade_info.get('prediction_used'):
                self.stats['prediction_used_count'] += 1
            if cascade_info.get('roi_used'):
                self.stats['roi_used_count'] += 1
            if cascade_info.get('prediction_ms'):
                self.stats['prediction_times'].append(cascade_info['prediction_ms'])

            # Track motion-only vs AKAZE frames
            if cascade_info.get('akaze_bypassed'):
                self.stats['motion_only_frames'] += 1
            else:
                self.stats['akaze_frames'] += 1

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

            # Pan tracking: Use raw screenshot pixel offset from phase correlation
            # offset_px is movement in screenshot pixels (actual game window resolution)
            # This is the most accurate measurement - direct from phase correlation
            current_time = time.time()
            cascade_info = result.get('cascade_info', {})
            motion_pred = cascade_info.get('motion_prediction')

            if motion_pred and self.last_viewport_time is not None:
                dt = current_time - self.last_viewport_time
                if dt > 0 and dt < 0.5:  # Sanity check
                    # Get movement in screenshot pixels (direct from phase correlation)
                    dx_screenshot, dy_screenshot = motion_pred['offset_px']

                    # Screenshot pixels = screen pixels (assuming game runs at native resolution)
                    # If game window is 1920x1080, these are already screen pixels
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
                        'frame': self.stats['total_frames'],
                        'timestamp': current_time,
                        'dx': dx_screen,  # Screen pixels (from phase correlation)
                        'dy': dy_screen,  # Screen pixels (from phase correlation)
                        'speed': speed,   # Screen pixels/sec
                        'acceleration': acceleration,  # Screen pixels/sec^2
                        'dt': dt,
                        'phase_confidence': motion_pred['phase_confidence']
                    })

            self.last_viewport_time = current_time

            # Motion extrapolation: Predict where viewport will be when rendered
            # Use adaptive lag measurement from frontend (updated every second)
            render_lag_ms = getattr(self, 'measured_render_lag_ms', 15.0)
            try:
                prediction = self.tracker.predict()
                if prediction:
                    pred_vp = prediction['predicted_viewport']
                    # Convert center + size to x,y + size
                    predicted_x = pred_vp['cx'] - pred_vp['width'] / 2
                    predicted_y = pred_vp['cy'] - pred_vp['height'] / 2
                else:
                    # No prediction available - use current viewport
                    predicted_x = viewport.x
                    predicted_y = viewport.y
                    pred_vp = {'width': viewport.width, 'height': viewport.height}
            except Exception as e:
                print(f"ERROR in predict_future(): {e}")
                import traceback
                traceback.print_exc()
                # Fallback to current viewport
                predicted_x = viewport.x
                predicted_y = viewport.y
                pred_vp = {'width': viewport.width, 'height': viewport.height}

            # Store predicted viewport for PySide6 overlay (smoother panning)
            viewport_dict = {
                'x': predicted_x,
                'y': predicted_y,
                'width': pred_vp['width'],
                'height': pred_vp['height'],
                'is_predicted': True,
                'prediction_ms': render_lag_ms
            }

            # Get visible collectibles (computed on capture thread to avoid blocking UI)
            overlay_start = time.time()
            collectibles = self.collectibles_func(viewport)
            overlay_time = (time.time() - overlay_start) * 1000
            self.stats['overlay_times'].append(overlay_time)

            # Lock-free atomic write (Python dict assignment is atomic with GIL)
            self._last_viewport = viewport_dict

            # Emit signal on every successful match
            # Frontend renders at its own rate (60 FPS timer), just uses latest data
            self.viewport_updated.emit(viewport_dict, collectibles)

            # Drift tracking: Pick ONE random collectible that's VISIBLE after initial AKAZE calibration
            # This ensures we immediately start tracking after first frame
            cascade_info = result.get('cascade_info', {})
            akaze_used = not cascade_info.get('akaze_bypassed', False)

            if self.drift_tracking_collectible is None and akaze_used and collectibles:
                import random
                # Pick from currently visible collectibles (after AKAZE calibration)
                random_col = random.choice(collectibles)
                self.drift_tracking_collectible = {
                    'name': random_col.get('name', random_col.get('n', 'Unknown')),
                    'map_x': random_col['map_x'],  # Detection space
                    'map_y': random_col['map_y'],
                    'type': random_col.get('type', random_col.get('t', 'unknown'))
                }
                print(f"[Drift Tracking] Selected visible collectible after AKAZE: {self.drift_tracking_collectible['name']} ({self.drift_tracking_collectible['type']}) at map ({self.drift_tracking_collectible['map_x']:.1f}, {self.drift_tracking_collectible['map_y']:.1f})")

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
                        'frame': self.stats['total_frames'],
                        'screen_x': tracked['x'],
                        'screen_y': tracked['y'],
                        'viewport_x': viewport.x,
                        'viewport_y': viewport.y,
                        'confidence': result['confidence']
                    })

            # Total time
            total_time = (time.time() - frame_start) * 1000
            self.stats['total_times'].append(total_time)

            # Record to modern metrics tracker
            frame_type = 'motion' if cascade_info.get('akaze_bypassed') else 'akaze'
            motion_offset = motion_pred.get('offset_px', (0, 0)) if motion_pred else (0, 0)
            motion_speed = motion_pred.get('speed_px_s', 0) if motion_pred else 0

            self.metrics.record_frame(
                capture_ms=capture_time,
                match_ms=match_time,
                overlay_ms=overlay_time,
                total_ms=total_time,
                confidence=result['confidence'],
                inliers=result['inliers'],
                frame_type=frame_type,
                viewport_width=viewport.width,
                viewport_height=viewport.height,
                cascade_level=cascade_level,
                motion_offset_px=motion_offset,
                motion_speed_px_s=motion_speed
            )

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
            # Record failed frame in metrics
            total_time = (time.time() - frame_start) * 1000
            self.metrics.record_frame(
                capture_ms=capture_time,
                match_ms=match_time,
                overlay_ms=0,
                total_ms=total_time,
                confidence=0,
                inliers=0,
                frame_type='failed'
            )

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
        """Thread-safe result update."""
        # Add stats
        result['stats'] = self._get_stats()

        with self.result_lock:
            self.latest_result = result

    def _check_and_reload_cycles(self):
        """Check if daily cycle changed and reload collectibles if needed."""
        try:
            from core.collectibles_loader import CollectiblesLoader

            if CollectiblesLoader.check_cycle_changed():
                print("[Cycle Change] Detected cycle change - reloading collectibles...")

                if self.state:
                    # Reload collectibles
                    collectibles = CollectiblesLoader.load(self.state.coord_transform)
                    self.state.set_collectibles(collectibles)
                    print(f"[Cycle Change] Reloaded {len(collectibles)} collectibles")
                else:
                    print("[Cycle Change] Warning: state not set, cannot reload collectibles")
        except Exception as e:
            print(f"[Cycle Change] Error checking/reloading: {e}")

    def _record_fallback(self, reason: str):
        """Record fallback reason in stats."""
        if reason not in self.stats['fallback_reasons']:
            self.stats['fallback_reasons'][reason] = 0
        self.stats['fallback_reasons'][reason] += 1

    def _get_stats(self) -> Dict:
        """Get comprehensive performance stats for API endpoint."""
        match_times = list(self.stats['match_times'])
        capture_times = list(self.stats['capture_times'])
        overlay_times = list(self.stats['overlay_times'])
        total_times = list(self.stats['total_times'])
        frame_intervals = list(self.stats['frame_intervals'])
        confidences = list(self.stats['confidences'])
        inliers = list(self.stats['inliers'])

        successful_matches = len(match_times)
        success_rate = (successful_matches / max(1, self.stats['total_frames'])) * 100

        # FPS calculations
        actual_fps = 0
        actual_fps_min = 0
        actual_fps_max = 0
        actual_fps_median = 0
        if frame_intervals:
            mean_interval = np.mean(frame_intervals)
            median_interval = np.median(frame_intervals)
            min_interval = np.min(frame_intervals)
            max_interval = np.max(frame_intervals)
            actual_fps = 1000 / mean_interval if mean_interval > 0 else 0
            actual_fps_median = 1000 / median_interval if median_interval > 0 else 0
            actual_fps_max = 1000 / min_interval if min_interval > 0 else 0
            actual_fps_min = 1000 / max_interval if max_interval > 0 else 0

        # Window FPS
        window_duration = time.time() - self.fps_window_start
        window_fps = self.fps_window_frames / window_duration if window_duration > 0 else 0

        # Latency stats
        latency_stats = {}
        if total_times:
            min_latency = np.min(total_times)
            max_latency = np.max(total_times)
            latency_stats = {
                'mean_ms': float(np.mean(total_times)),
                'median_ms': float(np.median(total_times)),
                'p95_ms': float(np.percentile(total_times, 95)),
                'best_ms': float(min_latency),
                'worst_ms': float(max_latency),
                'fps_mean': float(1000 / np.mean(total_times)),
                'fps_median': float(1000 / np.median(total_times)),
                'fps_best': float(1000 / min_latency),
                'fps_worst': float(1000 / max_latency)
            }

        # Drift analysis
        drift_stats = None
        if self.drift_history and len(self.drift_history) > 1:
            # Calculate screen position variance (should be stable if no drift)
            screen_xs = [d['screen_x'] for d in self.drift_history]
            screen_ys = [d['screen_y'] for d in self.drift_history]
            drift_stats = {
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

        # Adaptive FPS stats
        adaptive_stats = {}
        if self.adaptive_fps_enabled and self.processing_times:
            p95_processing = np.percentile(list(self.processing_times), 95) * 1000  # ms
            mean_processing = np.mean(list(self.processing_times)) * 1000  # ms
            utilization = (np.mean(list(self.processing_times)) / self.frame_interval) * 100
            adaptive_stats = {
                'enabled': True,
                'current_target_fps': float(self.target_fps),
                'min_fps': float(self.min_fps),
                'max_fps': self.max_fps,  # None = unlimited
                'p95_processing_ms': float(p95_processing),
                'mean_processing_ms': float(mean_processing),
                'utilization_pct': float(utilization),
                'frames_until_next_adapt': self.fps_adaptation_interval - self.frames_since_fps_update,
                'adaptation_interval': self.fps_adaptation_interval
            }

        return {
            'target_fps': self.target_fps,
            'adaptive_fps': adaptive_stats,
            'backend_fps': {
                'mean': float(actual_fps),
                'median': float(actual_fps_median),
                'min': float(actual_fps_min),
                'max': float(actual_fps_max),
                'window': float(window_fps),
                'window_duration_s': float(window_duration)
            },
            'frames': {
                'total': self.stats['total_frames'],
                'successful': successful_matches,
                'success_rate': float(success_rate),
                'motion_only': self.stats['motion_only_frames'],
                'motion_only_pct': float(self.stats['motion_only_frames'] / max(1, successful_matches) * 100),
                'akaze': self.stats['akaze_frames'],
                'akaze_pct': float(self.stats['akaze_frames'] / max(1, successful_matches) * 100),
                'duplicates': self.stats['duplicate_frames'],
                'skipped': self.stats['skipped_frames'],
                'failed': self.stats['no_map_detected']
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
            'pan_tracking': self._get_pan_stats()
        }

    def _get_pan_stats(self) -> Dict:
        """Calculate pan movement statistics."""
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
