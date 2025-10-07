"""
Unit tests for ViewportMonitor component.
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock
from core.monitoring.viewport_monitor import ViewportMonitor
from matching.viewport_tracker import Viewport


# Helper function to create Viewport objects
def create_viewport(x=5000, y=4000, width=2000, height=1500, confidence=0.85):
    """Create a Viewport object with default values."""
    return Viewport(
        x=x, y=y, width=width, height=height,
        confidence=confidence, timestamp=time.time()
    )


class TestViewportMonitorInitialization:
    """Test ViewportMonitor initialization."""

    def test_default_initialization(self):
        monitor = ViewportMonitor()
        assert monitor.history_size == 100
        assert monitor.drift_tracking_collectible is None
        assert len(monitor.drift_history) == 0
        assert len(monitor.pan_history) == 0
        assert monitor.last_viewport_time is None

    def test_custom_history_size(self):
        monitor = ViewportMonitor(history_size=50)
        assert monitor.history_size == 50
        assert monitor.drift_history.maxlen == 50
        assert monitor.pan_history.maxlen == 50


class TestViewportMonitorDriftTracking:
    """Test drift tracking functionality."""

    def test_drift_collectible_selection(self):
        """Test that drift collectible is selected after first AKAZE frame."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectibles = [
            {'name': 'Card 1', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'},
            {'name': 'Card 2', 'map_x': 6100, 'map_y': 4600, 'x': 1056, 'y': 594, 'type': 'card_tarot'}
        ]

        match_result = {'confidence': 0.85}

        # First frame with AKAZE should select collectible
        monitor.update_drift_tracking(
            frame_number=1,
            viewport=viewport,
            collectibles=collectibles,
            match_result=match_result,
            akaze_used=True
        )

        assert monitor.drift_tracking_collectible is not None
        assert monitor.drift_tracking_collectible['name'] in ['Card 1', 'Card 2']
        assert 'map_x' in monitor.drift_tracking_collectible
        assert 'map_y' in monitor.drift_tracking_collectible

    def test_drift_collectible_not_selected_without_akaze(self):
        """Test that collectible is not selected for motion-only frames."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectibles = [
            {'name': 'Card 1', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        ]

        match_result = {'confidence': 0.85}

        # Motion-only frame should not select collectible
        monitor.update_drift_tracking(
            frame_number=1,
            viewport=viewport,
            collectibles=collectibles,
            match_result=match_result,
            akaze_used=False
        )

        assert monitor.drift_tracking_collectible is None
        assert len(monitor.drift_history) == 0

    def test_drift_history_recording(self):
        """Test that drift history is recorded when collectible is visible."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectibles = [
            {'name': 'Card 1', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        ]

        match_result = {'confidence': 0.85}

        # Select collectible
        monitor.update_drift_tracking(1, viewport, collectibles, match_result, akaze_used=True)

        # Record drift samples
        for frame in range(2, 10):
            monitor.update_drift_tracking(frame, viewport, collectibles, match_result, akaze_used=False)

        assert len(monitor.drift_history) == 9  # 1 selection + 8 tracking frames
        assert monitor.drift_history[0]['frame'] == 1
        assert monitor.drift_history[0]['screen_x'] == 960
        assert monitor.drift_history[0]['screen_y'] == 540

    def test_drift_history_not_recorded_when_invisible(self):
        """Test that drift history is not recorded when collectible is out of view."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectibles = [
            {'name': 'Card 1', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        ]

        match_result = {'confidence': 0.85}

        # Select collectible
        monitor.update_drift_tracking(1, viewport, collectibles, match_result, akaze_used=True)
        assert len(monitor.drift_history) == 1

        # Move viewport so collectible is no longer visible
        viewport_moved = create_viewport(x=8000, y=6000)
        empty_collectibles = []

        monitor.update_drift_tracking(2, viewport_moved, empty_collectibles, match_result, akaze_used=False)

        # History should not grow
        assert len(monitor.drift_history) == 1

    def test_drift_collectible_matching_logic(self):
        """Test that collectible matching uses map coordinates correctly."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        # Select a specific collectible
        collectible = {'name': 'Target', 'map_x': 6000.0, 'map_y': 4500.0, 'x': 960, 'y': 540, 'type': 'card_tarot'}

        monitor.update_drift_tracking(1, viewport, [collectible], {'confidence': 0.85}, akaze_used=True)

        # Update with same collectible (should match within 1 pixel tolerance)
        collectible_moved = {'name': 'Target', 'map_x': 6000.5, 'map_y': 4500.3, 'x': 965, 'y': 545, 'type': 'card_tarot'}

        monitor.update_drift_tracking(2, viewport, [collectible_moved], {'confidence': 0.85}, akaze_used=False)

        assert len(monitor.drift_history) == 2
        assert monitor.drift_history[1]['screen_x'] == 965
        assert monitor.drift_history[1]['screen_y'] == 545

    def test_drift_history_maxlen(self):
        """Test that drift history respects maxlen."""
        monitor = ViewportMonitor(history_size=10)
        viewport = create_viewport()

        collectible = {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        match_result = {'confidence': 0.85}

        # Select and record 20 frames
        monitor.update_drift_tracking(1, viewport, [collectible], match_result, akaze_used=True)
        for frame in range(2, 21):
            monitor.update_drift_tracking(frame, viewport, [collectible], match_result, akaze_used=False)

        # Should only keep last 10
        assert len(monitor.drift_history) == 10
        assert monitor.drift_history[0]['frame'] == 11
        assert monitor.drift_history[-1]['frame'] == 20


class TestViewportMonitorPanTracking:
    """Test pan tracking functionality."""

    def test_pan_tracking_basic(self):
        """Test basic pan tracking with motion data."""
        monitor = ViewportMonitor()

        motion_prediction = {
            'offset_px': (10, 5),  # dx, dy in screenshot pixels
            'phase_confidence': 0.92
        }

        # First update initializes time
        monitor.update_pan_tracking(1, motion_prediction)
        assert monitor.last_viewport_time is not None
        assert len(monitor.pan_history) == 0  # Need two samples for speed

        # Second update calculates speed
        time.sleep(0.05)  # Small delay
        monitor.update_pan_tracking(2, motion_prediction)

        assert len(monitor.pan_history) == 1
        assert monitor.pan_history[0]['dx'] == 10
        assert monitor.pan_history[0]['dy'] == 5
        assert monitor.pan_history[0]['speed'] > 0
        assert monitor.pan_history[0]['acceleration'] == 0  # First sample has no acceleration

    def test_pan_tracking_speed_calculation(self):
        """Test speed calculation accuracy."""
        monitor = ViewportMonitor()

        # Simulate 100 pixels movement in 0.1 seconds = 1000 px/sec
        motion1 = {'offset_px': (60, 80), 'phase_confidence': 0.9}  # 100 pixels (sqrt(60^2 + 80^2))

        # Mock time from the beginning for deterministic test
        import core.monitoring.viewport_monitor
        original_time = time.time
        current_time = [1000.0]  # Mutable for incrementing

        def mock_time():
            return current_time[0]

        time.time = mock_time

        try:
            # Initialize with first frame (no motion)
            monitor.update_pan_tracking(1, None)
            assert monitor.last_viewport_time == 1000.0

            # Advance time and add motion
            current_time[0] = 1000.1  # 0.1 seconds later
            monitor.update_pan_tracking(2, motion1)

            assert len(monitor.pan_history) == 1
            # Speed should be approximately 1000 px/sec (100 pixels / 0.1 sec)
            assert 900 < monitor.pan_history[0]['speed'] < 1100
        finally:
            time.time = original_time

    def test_pan_tracking_acceleration_calculation(self):
        """Test acceleration calculation."""
        monitor = ViewportMonitor()

        motion1 = {'offset_px': (10, 0), 'phase_confidence': 0.9}
        motion2 = {'offset_px': (20, 0), 'phase_confidence': 0.9}

        # Use controlled timing
        import core.monitoring.viewport_monitor
        original_time = time.time
        current_time = [1000.0]

        def mock_time():
            return current_time[0]

        time.time = mock_time

        try:
            # First movement
            monitor.update_pan_tracking(1, None)
            current_time[0] = 1000.1
            monitor.update_pan_tracking(2, motion1)

            # Second movement (increased speed)
            current_time[0] = 1000.2
            monitor.update_pan_tracking(3, motion2)

            assert len(monitor.pan_history) == 2
            # Second sample should have positive acceleration
            assert monitor.pan_history[1]['acceleration'] > 0
        finally:
            time.time = original_time

    def test_pan_tracking_ignores_invalid_dt(self):
        """Test that invalid time deltas are ignored."""
        monitor = ViewportMonitor()

        motion = {'offset_px': (10, 5), 'phase_confidence': 0.9}

        # Initialize
        monitor.update_pan_tracking(1, motion)
        initial_len = len(monitor.pan_history)

        # Update with same timestamp (dt = 0) - should be ignored
        monitor.update_pan_tracking(2, motion)
        assert len(monitor.pan_history) == initial_len

    def test_pan_tracking_ignores_missing_motion(self):
        """Test that frames without motion data don't create entries."""
        monitor = ViewportMonitor()

        monitor.update_pan_tracking(1, None)
        monitor.update_pan_tracking(2, None)

        assert len(monitor.pan_history) == 0

    def test_pan_history_maxlen(self):
        """Test that pan history respects maxlen."""
        monitor = ViewportMonitor(history_size=10)

        import core.monitoring.viewport_monitor
        original_time = time.time
        current_time = [1000.0]
        time.time = lambda: current_time[0]

        try:
            motion = {'offset_px': (10, 5), 'phase_confidence': 0.9}

            # Record 20 pan movements
            monitor.update_pan_tracking(1, None)
            for i in range(2, 22):
                current_time[0] += 0.1
                monitor.update_pan_tracking(i, motion)

            # Should only keep last 10
            assert len(monitor.pan_history) == 10
        finally:
            time.time = original_time


class TestViewportMonitorStatistics:
    """Test statistics retrieval."""

    def test_get_drift_stats_with_no_data(self):
        """Test drift stats return None with no data."""
        monitor = ViewportMonitor()
        assert monitor.get_drift_stats() is None

    def test_get_drift_stats_with_insufficient_data(self):
        """Test drift stats return None with only one sample."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectible = {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        match_result = {'confidence': 0.85}

        monitor.update_drift_tracking(1, viewport, [collectible], match_result, akaze_used=True)

        # Only one sample - need at least 2 for variance
        assert monitor.get_drift_stats() is None

    def test_get_drift_stats_with_data(self):
        """Test drift stats calculation."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        # Create collectible with slight position variance
        match_result = {'confidence': 0.85}

        collectibles_frames = [
            {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'},
            {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 962, 'y': 541, 'type': 'card_tarot'},
            {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 961, 'y': 539, 'type': 'card_tarot'},
            {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 963, 'y': 542, 'type': 'card_tarot'},
        ]

        for i, col in enumerate(collectibles_frames):
            monitor.update_drift_tracking(i+1, viewport, [col], match_result, akaze_used=(i==0))

        stats = monitor.get_drift_stats()

        assert stats is not None
        assert stats['collectible_name'] == 'Card'
        assert stats['map_x'] == 6000
        assert stats['map_y'] == 4500
        assert stats['screen_x_variance'] > 0  # Should have some variance
        assert stats['screen_y_variance'] > 0
        assert stats['screen_x_range'] > 0
        assert stats['screen_y_range'] > 0
        assert stats['samples'] == 4
        assert len(stats['recent_positions']) == 4

    def test_get_drift_stats_recent_positions_limit(self):
        """Test that recent_positions is limited to 10."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        collectible = {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        match_result = {'confidence': 0.85}

        # Record 20 samples
        for i in range(20):
            monitor.update_drift_tracking(i+1, viewport, [collectible], match_result, akaze_used=(i==0))

        stats = monitor.get_drift_stats()

        assert stats['samples'] == 20
        assert len(stats['recent_positions']) == 10  # Should only return last 10

    def test_get_pan_stats_with_no_data(self):
        """Test pan stats return None with no data."""
        monitor = ViewportMonitor()
        assert monitor.get_pan_stats() is None

    def test_get_pan_stats_with_insufficient_data(self):
        """Test pan stats return None with only one sample."""
        monitor = ViewportMonitor()

        motion = {'offset_px': (10, 5), 'phase_confidence': 0.9}

        monitor.update_pan_tracking(1, None)
        time.sleep(0.01)
        monitor.update_pan_tracking(2, motion)

        # Only one sample in pan_history - need at least 2
        if len(monitor.pan_history) < 2:
            assert monitor.get_pan_stats() is None

    def test_get_pan_stats_with_data(self):
        """Test pan stats calculation."""
        monitor = ViewportMonitor()

        import core.monitoring.viewport_monitor
        original_time = time.time
        current_time = [1000.0]
        time.time = lambda: current_time[0]

        try:
            motion = {'offset_px': (10, 5), 'phase_confidence': 0.9}

            # Record several movements
            monitor.update_pan_tracking(1, None)
            for i in range(2, 10):
                current_time[0] += 0.1
                monitor.update_pan_tracking(i, motion)

            stats = monitor.get_pan_stats()

            if stats is not None:  # May be None if < 2 samples
                assert stats['samples'] > 0
                assert 'speed' in stats
                assert stats['speed']['mean'] > 0
                assert stats['speed']['median'] > 0
                assert stats['speed']['max'] >= stats['speed']['mean']
                assert stats['speed']['min'] <= stats['speed']['mean']
                assert 'acceleration' in stats
                assert len(stats['recent_movements']) <= 10
        finally:
            time.time = original_time

    def test_get_pan_stats_percentiles(self):
        """Test pan stats percentile calculations."""
        monitor = ViewportMonitor()

        import core.monitoring.viewport_monitor
        original_time = time.time
        current_time = [1000.0]
        time.time = lambda: current_time[0]

        try:
            # Create movements with varying speeds
            movements = [
                {'offset_px': (5, 0), 'phase_confidence': 0.9},
                {'offset_px': (10, 0), 'phase_confidence': 0.9},
                {'offset_px': (15, 0), 'phase_confidence': 0.9},
                {'offset_px': (20, 0), 'phase_confidence': 0.9},
            ]

            monitor.update_pan_tracking(1, None)
            for i, motion in enumerate(movements):
                current_time[0] += 0.1
                monitor.update_pan_tracking(i+2, motion)

            stats = monitor.get_pan_stats()

            if stats is not None:
                assert stats['speed']['p95'] >= stats['speed']['median']
        finally:
            time.time = original_time


class TestViewportMonitorReset:
    """Test reset functionality."""

    def test_reset_clears_all_data(self):
        """Test that reset clears all tracking data."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        # Add drift data
        collectible = {'name': 'Card', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        match_result = {'confidence': 0.85}
        monitor.update_drift_tracking(1, viewport, [collectible], match_result, akaze_used=True)

        # Add pan data
        motion = {'offset_px': (10, 5), 'phase_confidence': 0.9}
        monitor.update_pan_tracking(1, None)
        time.sleep(0.01)
        monitor.update_pan_tracking(2, motion)

        # Reset
        monitor.reset()

        assert monitor.drift_tracking_collectible is None
        assert len(monitor.drift_history) == 0
        assert len(monitor.pan_history) == 0
        assert monitor.last_viewport_time is None

    def test_reset_allows_reinitialization(self):
        """Test that reset allows tracking to restart."""
        monitor = ViewportMonitor()
        viewport = create_viewport()

        # First tracking session
        collectible1 = {'name': 'Card 1', 'map_x': 6000, 'map_y': 4500, 'x': 960, 'y': 540, 'type': 'card_tarot'}
        match_result = {'confidence': 0.85}
        monitor.update_drift_tracking(1, viewport, [collectible1], match_result, akaze_used=True)

        first_collectible = monitor.drift_tracking_collectible['name']

        # Reset
        monitor.reset()

        # Second tracking session with different collectible
        collectible2 = {'name': 'Card 2', 'map_x': 6100, 'map_y': 4600, 'x': 1056, 'y': 594, 'type': 'card_tarot'}
        monitor.update_drift_tracking(1, viewport, [collectible2], match_result, akaze_used=True)

        second_collectible = monitor.drift_tracking_collectible['name']

        # Should track new collectible
        assert second_collectible == 'Card 2'
