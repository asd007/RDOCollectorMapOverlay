"""
Unit tests for CaptureLoop component.
"""

import pytest
import time
from unittest.mock import Mock
from core.capture_loop import CaptureLoop


class TestCaptureLoopInitialization:
    """Test CaptureLoop initialization."""

    def test_default_initialization(self):
        loop = CaptureLoop()
        assert loop.target_fps == 5.0
        assert loop.min_fps == 5.0
        assert loop.max_fps is None
        assert loop.adaptive_fps_enabled is True
        assert loop.running is False
        assert loop.thread is None

    def test_custom_initialization(self):
        loop = CaptureLoop(target_fps=10.0, min_fps=3.0, max_fps=15.0, adaptive_fps_enabled=False)
        assert loop.target_fps == 10.0
        assert loop.min_fps == 3.0
        assert loop.max_fps == 15.0
        assert loop.adaptive_fps_enabled is False


class TestCaptureLoopFPSAdaptation:
    """Test adaptive FPS control."""

    def test_adapt_fps_low_utilization(self):
        """Test FPS increases when utilization is low."""
        loop = CaptureLoop(target_fps=5.0)
        initial_fps = loop.target_fps

        # Simulate low processing times (<60% utilization)
        for _ in range(5):
            loop.adapt_fps(0.05)  # 50ms processing, 200ms budget = 25% utilization

        # FPS should increase
        assert loop.target_fps > initial_fps

    def test_adapt_fps_high_utilization(self):
        """Test FPS decreases when utilization is high."""
        loop = CaptureLoop(target_fps=5.0)
        initial_fps = loop.target_fps

        # Simulate high processing times (>85% utilization)
        for _ in range(5):
            loop.adapt_fps(0.18)  # 180ms processing, 200ms budget = 90% utilization

        # FPS should decrease
        assert loop.target_fps < initial_fps

    def test_adapt_fps_respects_min_fps(self):
        """Test FPS doesn't go below min_fps."""
        loop = CaptureLoop(target_fps=5.0, min_fps=3.0)

        # Simulate very high processing times
        for _ in range(10):
            loop.adapt_fps(0.5)  # 500ms processing

        # FPS should not go below min
        assert loop.target_fps >= loop.min_fps

    def test_adapt_fps_respects_max_fps(self):
        """Test FPS doesn't exceed max_fps."""
        loop = CaptureLoop(target_fps=5.0, max_fps=10.0)

        # Simulate very low processing times
        for _ in range(10):
            loop.adapt_fps(0.01)  # 10ms processing

        # FPS should not exceed max
        assert loop.target_fps <= loop.max_fps

    def test_adapt_fps_disabled(self):
        """Test FPS doesn't change when adaptation is disabled."""
        loop = CaptureLoop(target_fps=5.0, adaptive_fps_enabled=False)
        initial_fps = loop.target_fps

        # Processing times shouldn't affect FPS
        loop.adapt_fps(0.01)
        loop.adapt_fps(0.5)

        assert loop.target_fps == initial_fps


class TestCaptureLoopThreadControl:
    """Test thread lifecycle management."""

    def test_start_stop(self):
        """Test starting and stopping the capture loop."""
        loop = CaptureLoop(target_fps=50.0)  # High FPS for faster test
        frame_count = [0]

        def process_frame():
            frame_count[0] += 1
            return 0.001  # 1ms processing

        loop.start(process_frame)
        assert loop.running is True
        assert loop.thread is not None

        # Let it run briefly
        time.sleep(0.1)

        loop.stop()
        assert loop.running is False

        # Should have processed some frames
        assert frame_count[0] > 0

    def test_multiple_start_calls(self):
        """Test that multiple start() calls don't create multiple threads."""
        loop = CaptureLoop()

        def process_frame():
            return 0.001

        loop.start(process_frame)
        first_thread = loop.thread

        loop.start(process_frame)  # Should be ignored
        second_thread = loop.thread

        assert first_thread is second_thread

        loop.stop()


class TestCaptureLoopStatistics:
    """Test FPS statistics tracking."""

    def test_get_fps_stats(self):
        """Test FPS statistics calculation."""
        loop = CaptureLoop(target_fps=10.0)

        # Simulate some processing
        loop.adapt_fps(0.05)
        loop.adapt_fps(0.06)
        loop.adapt_fps(0.055)

        stats = loop.get_fps_stats()

        assert 'target_fps' in stats
        assert 'actual_fps' in stats
        assert 'utilization' in stats
        assert 'skipped_frames' in stats
        assert 'total_frames' in stats

        assert stats['target_fps'] == loop.target_fps
        assert stats['utilization'] >= 0.0
        assert stats['skipped_frames'] >= 0

    def test_frame_counting(self):
        """Test that frames are counted correctly."""
        loop = CaptureLoop(target_fps=50.0)
        frame_count = [0]

        def process_frame():
            frame_count[0] += 1
            time.sleep(0.005)  # Small delay
            return 0.005

        loop.start(process_frame)
        time.sleep(0.15)  # Run for 150ms
        loop.stop()

        stats = loop.get_fps_stats()
        # Should have processed roughly (150ms / 20ms) = ~7 frames at 50 FPS
        assert stats['total_frames'] > 0
        assert stats['total_frames'] == frame_count[0]


class TestCaptureLoopTiming:
    """Test frame timing and scheduling."""

    def test_frame_interval_calculation(self):
        """Test that frame interval is calculated correctly."""
        loop = CaptureLoop(target_fps=5.0)
        assert loop.frame_interval == pytest.approx(0.2, rel=0.01)

        loop = CaptureLoop(target_fps=10.0)
        assert loop.frame_interval == pytest.approx(0.1, rel=0.01)

    def test_frame_interval_updates_with_fps(self):
        """Test that frame interval updates when FPS changes."""
        loop = CaptureLoop(target_fps=5.0)
        initial_interval = loop.frame_interval

        # Simulate low utilization to increase FPS
        for _ in range(5):
            loop.adapt_fps(0.02)

        # Frame interval should decrease (faster frames)
        assert loop.frame_interval < initial_interval
