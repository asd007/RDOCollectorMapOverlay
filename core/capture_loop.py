"""
Capture loop with adaptive FPS and intelligent frame scheduling.
Thread management and timing logic extracted from ContinuousCaptureService.
"""

import time
import threading
import numpy as np
from collections import deque
from typing import Callable, Optional


class CaptureLoop:
    """
    Manages the main capture loop timing and thread lifecycle.

    Responsibilities:
    - Thread management (start/stop/wait)
    - Frame timing and scheduling
    - Adaptive FPS control based on processing times
    - FPS statistics tracking

    Thread safety: Creates and manages its own background thread.
    """

    def __init__(
        self,
        target_fps: float = 5.0,
        min_fps: float = 5.0,
        max_fps: Optional[float] = None,
        adaptive_fps_enabled: bool = True
    ):
        """
        Initialize capture loop.

        Args:
            target_fps: Initial target capture rate (default 5fps)
            min_fps: Minimum FPS when system is slow (default 5fps)
            max_fps: Maximum FPS cap (default None = no cap)
            adaptive_fps_enabled: Enable automatic FPS adjustment (default True)
        """
        self.target_fps = target_fps
        self.min_fps = min_fps
        self.max_fps = max_fps
        self.adaptive_fps_enabled = adaptive_fps_enabled

        self.frame_interval = 1.0 / target_fps

        # Thread control
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Adaptive FPS control
        self.processing_times = deque(maxlen=10)  # Track recent processing times (ms)
        self.fps_adaptation_interval = 3  # Recalculate target FPS every N frames
        self.frames_since_fps_update = 0

        # Statistics
        self.skipped_frames = 0
        self.total_frames = 0
        self.last_frame_time: Optional[float] = None
        self.fps_window_start = time.time()
        self.fps_window_frames = 0

    def start(self, process_frame_callback: Callable[[], float]):
        """
        Start capture loop in background thread.

        Args:
            process_frame_callback: Function to call for each frame.
                                  Should return processing time in seconds.
        """
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._loop,
            args=(process_frame_callback,),
            daemon=True
        )
        self.thread.start()

    def stop(self):
        """Stop capture loop and wait for thread to finish."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None

    def wait(self):
        """Wait for thread to finish (if running)."""
        if self.thread and self.thread.is_alive():
            self.thread.join()

    def adapt_fps(self, processing_time_s: float):
        """
        Adjust target FPS based on processing time.

        Adaptive strategy:
        - If utilization < 60%: increase FPS by 50% (fast ramp-up)
        - If utilization 60-75%: increase FPS by 20% (fine-tuning)
        - If utilization 75-85%: stay at current FPS (sweet spot)
        - If utilization > 85%: decrease FPS by 30% (avoid overload)

        Args:
            processing_time_s: Time taken to process last frame (seconds)
        """
        self.processing_times.append(processing_time_s)

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

        # Apply FPS constraints
        new_fps = max(new_fps, self.min_fps)
        if self.max_fps is not None:
            new_fps = min(new_fps, self.max_fps)

        # Only update if significant change
        if abs(new_fps - old_fps) > 0.5:
            self.target_fps = new_fps
            self.frame_interval = 1.0 / new_fps

    def get_fps_stats(self) -> dict:
        """
        Get FPS statistics.

        Returns:
            Dict with:
                - target_fps: Current target FPS
                - actual_fps: Measured FPS from last window
                - utilization: Processing time / frame budget
                - skipped_frames: Total frames skipped due to lag
        """
        # Calculate actual FPS from window
        window_duration = time.time() - self.fps_window_start
        actual_fps = self.fps_window_frames / window_duration if window_duration > 0 else 0

        # Calculate utilization
        utilization = 0.0
        if self.processing_times:
            avg_processing = sum(self.processing_times) / len(self.processing_times)
            utilization = avg_processing / self.frame_interval

        return {
            'target_fps': self.target_fps,
            'actual_fps': actual_fps,
            'utilization': utilization,
            'skipped_frames': self.skipped_frames,
            'total_frames': self.total_frames
        }

    def _loop(self, process_frame_callback: Callable[[], float]):
        """
        Main capture loop (runs in background thread).

        Features:
        - Adaptive FPS based on processing times
        - Intelligent frame skipping when behind schedule
        - Precise timing for consistent frame rate

        Args:
            process_frame_callback: Function to call for each frame.
                                  Should return processing time in seconds.
        """
        next_capture_time = time.time()

        while self.running:
            current_time = time.time()

            # Check if it's time to process next frame
            if current_time >= next_capture_time:
                frame_start = current_time

                # Process frame and measure time
                try:
                    processing_time = process_frame_callback()
                except Exception as e:
                    # Let callback handle exceptions, continue loop
                    print(f"[CaptureLoop] Frame processing error: {e}")
                    processing_time = 0.001  # Small default

                self.total_frames += 1
                self.fps_window_frames += 1

                # Adaptive FPS adjustment
                if self.adaptive_fps_enabled:
                    self.frames_since_fps_update += 1
                    if self.frames_since_fps_update >= self.fps_adaptation_interval:
                        self.adapt_fps(processing_time)
                        self.frames_since_fps_update = 0

                # Intelligent frame skipping
                # If we're behind schedule, skip to current time to prevent lag accumulation
                ideal_next_time = next_capture_time + self.frame_interval
                time_until_next = ideal_next_time - time.time()

                if time_until_next < -self.frame_interval:
                    # We're more than one frame behind - skip ahead
                    frames_behind = int(abs(time_until_next) / self.frame_interval)
                    self.skipped_frames += frames_behind
                    next_capture_time = time.time()  # Reset to now
                else:
                    # Normal case: schedule next frame
                    next_capture_time = ideal_next_time

                # Reset FPS window every 5 seconds for accurate measurement
                if time.time() - self.fps_window_start >= 5.0:
                    self.fps_window_start = time.time()
                    self.fps_window_frames = 0

                self.last_frame_time = frame_start

            # Sleep briefly to avoid busy-waiting
            # Use shorter sleep for responsiveness
            time.sleep(0.001)
