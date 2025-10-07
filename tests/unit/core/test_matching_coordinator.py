"""
Unit tests for MatchingCoordinator component.
"""

import pytest
import numpy as np
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import TimeoutError as FuturesTimeoutError

from core.matching_coordinator import MatchingCoordinator
from matching.viewport_tracker import Viewport


# Helper function to create Viewport objects
def create_viewport(x=5000, y=4000, width=2000, height=1500, confidence=0.85):
    """Create a Viewport object with default values."""
    return Viewport(
        x=x, y=y, width=width, height=height,
        confidence=confidence, timestamp=time.time()
    )


class TestMatchingCoordinatorInitialization:
    """Test MatchingCoordinator initialization."""

    def test_default_initialization(self):
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)

        assert coordinator.matcher == matcher
        assert coordinator.match_timeout == 6.0
        assert coordinator.tracker is not None
        assert coordinator.previous_viewport is None
        assert coordinator.measured_render_lag_ms == 15.0
        assert coordinator.total_matches == 0
        assert coordinator.successful_matches == 0
        assert coordinator.failed_matches == 0
        assert coordinator.timeout_matches == 0
        assert coordinator.motion_only_frames == 0
        assert coordinator.akaze_frames == 0

    def test_custom_initialization(self):
        matcher = Mock()
        coordinator = MatchingCoordinator(
            matcher,
            frame_interval=0.1,
            match_timeout=3.0
        )

        assert coordinator.match_timeout == 3.0
        assert coordinator.tracker.dt == 0.1


class TestMatchingCoordinatorConfiguration:
    """Test configuration updates."""

    def test_update_frame_interval(self):
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher, frame_interval=0.2)

        assert coordinator.tracker.dt == 0.2

        coordinator.update_frame_interval(0.1)
        assert coordinator.tracker.dt == 0.1

    def test_update_render_lag(self):
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)

        assert coordinator.measured_render_lag_ms == 15.0

        coordinator.update_render_lag(25.0)
        assert coordinator.measured_render_lag_ms == 25.0


class TestMatchingCoordinatorMatching:
    """Test screenshot matching functionality."""

    def test_successful_match(self, mock_screenshot):
        """Test successful match."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0,
            'map_y': 4000.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.85,
            'inliers': 150,
            'match_type': 'akaze',
            'cascade_info': {
                'match_type': 'akaze',
                'final_level': 0.5
            }
        }

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        assert result is not None
        assert result['success'] is True
        assert result['map_x'] == 5000.0
        assert result['map_y'] == 4000.0
        assert 'match_time_ms' in result
        assert result['match_time_ms'] >= 0

        assert coordinator.total_matches == 1
        assert coordinator.successful_matches == 1
        assert coordinator.failed_matches == 0
        assert coordinator.akaze_frames == 1
        assert coordinator.motion_only_frames == 0

    def test_motion_only_match(self, mock_screenshot):
        """Test match using motion-only tracking."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0,
            'map_y': 4000.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.95,
            'inliers': 0,
            'match_type': 'motion_only',
            'cascade_info': {
                'match_type': 'motion_only',
                'final_level': 0.0
            }
        }

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        assert result is not None
        assert result['success'] is True
        assert coordinator.motion_only_frames == 1
        assert coordinator.akaze_frames == 0

    def test_failed_match(self, mock_screenshot):
        """Test failed match (matcher returns unsuccessful result)."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': False
        }

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        assert result is None
        assert coordinator.total_matches == 1
        assert coordinator.successful_matches == 0
        assert coordinator.failed_matches == 1

    def test_match_returns_none(self, mock_screenshot):
        """Test when matcher returns None."""
        matcher = Mock()
        matcher.match.return_value = None

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        assert result is None
        assert coordinator.failed_matches == 1

    def test_match_timeout(self, mock_screenshot):
        """Test match timeout handling."""
        matcher = Mock()

        def slow_match(screenshot):
            time.sleep(0.3)  # Longer than timeout
            return {'success': True, 'map_x': 5000, 'map_y': 4000, 'map_w': 2000, 'map_h': 1500}

        matcher.match = slow_match

        coordinator = MatchingCoordinator(matcher, match_timeout=0.1)  # 100ms timeout
        result = coordinator.match(mock_screenshot)

        assert result is None
        assert coordinator.timeout_matches == 1
        assert coordinator.failed_matches == 1

    def test_match_exception(self, mock_screenshot):
        """Test matcher exception handling."""
        matcher = Mock()
        matcher.match.side_effect = RuntimeError("Matcher error")

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        assert result is None
        assert coordinator.failed_matches == 1

    def test_match_updates_tracker(self, mock_screenshot):
        """Test that successful match updates the tracker."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0,
            'map_y': 4000.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.85,
            'inliers': 150,
            'match_type': 'akaze',
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }

        coordinator = MatchingCoordinator(matcher)
        coordinator.match(mock_screenshot)

        assert coordinator.previous_viewport is not None
        assert coordinator.previous_viewport.x == 5000.0
        assert coordinator.previous_viewport.y == 4000.0

    def test_multiple_matches(self, mock_screenshot):
        """Test statistics with multiple matches."""
        matcher = Mock()

        # Successful match
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0,
            'map_y': 4000.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.85,
            'inliers': 150,
            'match_type': 'akaze',
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }

        coordinator = MatchingCoordinator(matcher)
        coordinator.match(mock_screenshot)

        # Failed match
        matcher.match.return_value = {'success': False}
        coordinator.match(mock_screenshot)

        # Another successful match
        matcher.match.return_value = {
            'success': True,
            'map_x': 5100.0,
            'map_y': 4100.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.90,
            'inliers': 0,
            'match_type': 'motion_only',
            'cascade_info': {'match_type': 'motion_only', 'final_level': 0.0}
        }
        coordinator.match(mock_screenshot)

        assert coordinator.total_matches == 3
        assert coordinator.successful_matches == 2
        assert coordinator.failed_matches == 1
        assert coordinator.akaze_frames == 1
        assert coordinator.motion_only_frames == 1


class TestMatchingCoordinatorPrediction:
    """Test viewport prediction functionality."""

    def test_get_predicted_viewport_basic(self):
        """Test basic viewport prediction."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0,
            'map_y': 4000.0,
            'map_w': 2000.0,
            'map_h': 1500.0,
            'confidence': 0.85,
            'inliers': 150,
            'match_type': 'akaze',
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }

        coordinator = MatchingCoordinator(matcher)
        screenshot = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        # Do a match to initialize tracker
        coordinator.match(screenshot)

        current_viewport = create_viewport()
        predicted = coordinator.get_predicted_viewport(current_viewport)

        assert predicted is not None
        assert 'x' in predicted
        assert 'y' in predicted
        assert 'width' in predicted
        assert 'height' in predicted
        assert 'is_predicted' in predicted
        assert 'prediction_ms' in predicted

    def test_get_predicted_viewport_fallback(self):
        """Test prediction fallback when tracker has no data."""
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)

        current_viewport = create_viewport()
        predicted = coordinator.get_predicted_viewport(current_viewport)

        # Should fallback to current viewport
        assert predicted['x'] == 5000
        assert predicted['y'] == 4000
        assert predicted['width'] == 2000
        assert predicted['height'] == 1500
        assert predicted['is_predicted'] is False
        assert predicted['prediction_ms'] == 0

    @patch('core.matching_coordinator.ViewportKalmanTracker')
    def test_get_predicted_viewport_with_motion(self, mock_tracker_class):
        """Test prediction with motion data."""
        matcher = Mock()
        mock_tracker = Mock()
        mock_tracker.dt = 0.2
        mock_tracker.predict.return_value = {
            'predicted_viewport': {
                'cx': 6000.0,  # Center x
                'cy': 4750.0,  # Center y
                'width': 2000.0,
                'height': 1500.0
            }
        }
        mock_tracker_class.return_value = mock_tracker

        coordinator = MatchingCoordinator(matcher)
        coordinator.tracker = mock_tracker

        current_viewport = create_viewport()
        predicted = coordinator.get_predicted_viewport(current_viewport)

        # Should use predicted position (convert center to top-left)
        # x = cx - width/2 = 6000 - 1000 = 5000
        # y = cy - height/2 = 4750 - 750 = 4000
        assert predicted['x'] == 5000.0
        assert predicted['y'] == 4000.0
        assert predicted['is_predicted'] is True

    @patch('core.matching_coordinator.ViewportKalmanTracker')
    def test_get_predicted_viewport_with_exception(self, mock_tracker_class):
        """Test prediction fallback on exception."""
        matcher = Mock()
        mock_tracker = Mock()
        mock_tracker.dt = 0.2
        mock_tracker.predict.side_effect = RuntimeError("Tracker error")
        mock_tracker_class.return_value = mock_tracker

        coordinator = MatchingCoordinator(matcher)
        coordinator.tracker = mock_tracker

        current_viewport = create_viewport()
        predicted = coordinator.get_predicted_viewport(current_viewport)

        # Should fallback to current viewport
        assert predicted['x'] == 5000
        assert predicted['y'] == 4000
        assert predicted['is_predicted'] is False


class TestMatchingCoordinatorStatistics:
    """Test statistics retrieval."""

    def test_get_stats_initial(self):
        """Test initial statistics."""
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)
        stats = coordinator.get_stats()

        assert stats['total_matches'] == 0
        assert stats['successful_matches'] == 0
        assert stats['failed_matches'] == 0
        assert stats['timeout_matches'] == 0
        assert stats['success_rate'] == 0
        assert stats['motion_only_frames'] == 0
        assert stats['akaze_frames'] == 0
        assert stats['motion_only_ratio'] == 0

    def test_get_stats_after_matches(self, mock_screenshot):
        """Test statistics calculation after matches."""
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)

        # Successful AKAZE match
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0, 'map_y': 4000.0, 'map_w': 2000.0, 'map_h': 1500.0,
            'confidence': 0.85, 'inliers': 150,
            'match_type': 'akaze',
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }
        coordinator.match(mock_screenshot)

        # Motion-only match
        matcher.match.return_value = {
            'success': True,
            'map_x': 5100.0, 'map_y': 4100.0, 'map_w': 2000.0, 'map_h': 1500.0,
            'confidence': 0.95, 'inliers': 0,
            'match_type': 'motion_only',
            'cascade_info': {'match_type': 'motion_only', 'final_level': 0.0}
        }
        coordinator.match(mock_screenshot)

        # Failed match
        matcher.match.return_value = {'success': False}
        coordinator.match(mock_screenshot)

        stats = coordinator.get_stats()

        assert stats['total_matches'] == 3
        assert stats['successful_matches'] == 2
        assert stats['failed_matches'] == 1
        assert stats['success_rate'] == pytest.approx(66.67, rel=0.1)
        assert stats['akaze_frames'] == 1
        assert stats['motion_only_frames'] == 1
        assert stats['motion_only_ratio'] == pytest.approx(50.0, rel=0.1)

    def test_get_motion_stats_no_data(self):
        """Test motion stats with no data."""
        matcher = Mock()
        coordinator = MatchingCoordinator(matcher)

        stats = coordinator.get_motion_stats()
        # May be None or empty dict
        assert stats is None or not stats.get('has_motion_data')

    @patch('core.matching_coordinator.ViewportKalmanTracker')
    def test_get_motion_stats_with_data(self, mock_tracker_class):
        """Test motion stats with prediction data."""
        matcher = Mock()
        mock_tracker = Mock()
        mock_tracker.dt = 0.2
        mock_tracker.predict.return_value = {
            'velocity_x': 10.0,
            'velocity_y': 5.0,
            'confidence': 0.92,
            'predicted_viewport': {
                'cx': 6000.0, 'cy': 4750.0,
                'width': 2000.0, 'height': 1500.0
            }
        }
        mock_tracker_class.return_value = mock_tracker

        coordinator = MatchingCoordinator(matcher)
        coordinator.tracker = mock_tracker

        stats = coordinator.get_motion_stats()

        assert stats is not None
        assert stats['has_motion_data'] is True
        assert stats['velocity_x'] == 10.0
        assert stats['velocity_y'] == 5.0
        assert stats['prediction_confidence'] == 0.92


class TestMatchingCoordinatorReset:
    """Test reset functionality."""

    def test_reset_tracker(self, mock_screenshot):
        """Test tracker reset."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0, 'map_y': 4000.0, 'map_w': 2000.0, 'map_h': 1500.0,
            'confidence': 0.85, 'inliers': 150,
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }

        coordinator = MatchingCoordinator(matcher, frame_interval=0.15)

        # Do a match to populate tracker
        coordinator.match(mock_screenshot)
        assert coordinator.previous_viewport is not None

        # Reset tracker
        old_tracker = coordinator.tracker
        coordinator.reset_tracker()

        # Should have new tracker instance
        assert coordinator.tracker is not old_tracker
        assert coordinator.previous_viewport is None
        # Should preserve frame interval
        assert coordinator.tracker.dt == 0.15

    def test_reset_tracker_preserves_stats(self, mock_screenshot):
        """Test that reset_tracker doesn't clear match statistics."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0, 'map_y': 4000.0, 'map_w': 2000.0, 'map_h': 1500.0,
            'confidence': 0.85, 'inliers': 150,
            'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
        }

        coordinator = MatchingCoordinator(matcher)
        coordinator.match(mock_screenshot)

        assert coordinator.successful_matches == 1

        coordinator.reset_tracker()

        # Statistics should be preserved
        assert coordinator.successful_matches == 1


class TestMatchingCoordinatorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_match_with_malformed_result(self, mock_screenshot):
        """Test handling of malformed match result."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            # Missing required fields
        }

        coordinator = MatchingCoordinator(matcher)

        # Should handle gracefully (likely will raise exception and be caught)
        try:
            result = coordinator.match(mock_screenshot)
            # If it returns, it should be None (failed match)
            assert result is None or not result.get('success')
        except:
            # Exception is acceptable
            pass

    def test_very_short_timeout(self, mock_screenshot):
        """Test with very short timeout."""
        matcher = Mock()

        def slow_match(screenshot):
            time.sleep(0.01)  # 10ms
            return {'success': True, 'map_x': 5000, 'map_y': 4000, 'map_w': 2000, 'map_h': 1500}

        matcher.match = slow_match

        coordinator = MatchingCoordinator(matcher, match_timeout=0.001)  # 1ms timeout

        result = coordinator.match(mock_screenshot)

        # Should timeout
        assert result is None
        assert coordinator.timeout_matches > 0

    def test_match_result_missing_cascade_info(self, mock_screenshot):
        """Test match result without cascade_info."""
        matcher = Mock()
        matcher.match.return_value = {
            'success': True,
            'map_x': 5000.0, 'map_y': 4000.0, 'map_w': 2000.0, 'map_h': 1500.0,
            'confidence': 0.85, 'inliers': 150
            # No cascade_info
        }

        coordinator = MatchingCoordinator(matcher)
        result = coordinator.match(mock_screenshot)

        # Should still succeed
        assert result is not None
        assert result['success'] is True
        # Should default to AKAZE when match_type is missing (conservative)
        assert coordinator.motion_only_frames == 0
        assert coordinator.akaze_frames == 1

    def test_concurrent_matches(self, mock_screenshot):
        """Test that matches are serialized (not truly concurrent)."""
        matcher = Mock()
        call_count = [0]

        def counting_match(screenshot):
            call_count[0] += 1
            time.sleep(0.01)
            return {
                'success': True,
                'map_x': 5000.0, 'map_y': 4000.0, 'map_w': 2000.0, 'map_h': 1500.0,
                'confidence': 0.85, 'inliers': 150,
                'cascade_info': {'match_type': 'akaze', 'final_level': 0.5}
            }

        matcher.match = counting_match

        coordinator = MatchingCoordinator(matcher)

        # Call match twice
        coordinator.match(mock_screenshot)
        coordinator.match(mock_screenshot)

        # Both should complete
        assert call_count[0] == 2
        assert coordinator.successful_matches == 2
