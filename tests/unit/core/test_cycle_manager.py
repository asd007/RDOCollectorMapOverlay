"""
Unit tests for CycleManager component.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from core.collectibles.cycle_manager import CycleManager


class TestCycleManagerInitialization:
    """Test CycleManager initialization."""

    def test_default_initialization(self):
        manager = CycleManager()
        assert manager.check_interval == 300.0  # 5 minutes
        assert manager.total_checks == 0
        assert manager.cycle_changes_detected == 0
        assert manager.reload_successes == 0
        assert manager.reload_failures == 0

    def test_custom_check_interval(self):
        manager = CycleManager(check_interval=60.0)  # 1 minute
        assert manager.check_interval == 60.0


class TestCycleManagerTiming:
    """Test timing and check scheduling."""

    def test_should_check_now_initial(self):
        """Test that should_check_now returns False immediately after init."""
        manager = CycleManager(check_interval=10.0)
        # Should not trigger check immediately
        assert manager.should_check_now() is False

    def test_should_check_now_after_interval(self):
        """Test that check triggers after interval elapsed."""
        manager = CycleManager(check_interval=0.05)  # 50ms

        # Should not trigger immediately
        assert manager.should_check_now() is False

        # Wait for interval
        time.sleep(0.06)

        # Should trigger now
        assert manager.should_check_now() is True

    def test_should_check_now_updates_last_check_time(self):
        """Test that should_check_now updates the last check time."""
        manager = CycleManager(check_interval=0.05)

        initial_time = manager.last_check_time
        time.sleep(0.06)

        manager.should_check_now()

        # Last check time should be updated
        assert manager.last_check_time > initial_time

    def test_should_check_now_resets_timer(self):
        """Test that timer resets after check."""
        manager = CycleManager(check_interval=0.05)

        time.sleep(0.06)
        assert manager.should_check_now() is True

        # Should not trigger again immediately
        assert manager.should_check_now() is False

    def test_should_check_now_with_mocked_time(self, mock_time):
        """Test timing logic with controlled time."""
        manager = CycleManager(check_interval=300.0)  # 5 minutes

        # Should not trigger at start
        assert manager.should_check_now() is False

        # Advance time by 250 seconds (not enough)
        mock_time(250)
        assert manager.should_check_now() is False

        # Advance time by another 60 seconds (310 total - should trigger)
        mock_time(60)
        assert manager.should_check_now() is True

        # Should not trigger again immediately
        assert manager.should_check_now() is False


class TestCycleManagerCheckAndReload:
    """Test cycle checking and reloading."""

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_no_cycle_change(self, mock_loader):
        """Test when no cycle change is detected."""
        mock_loader.check_cycle_changed.return_value = False

        manager = CycleManager()
        state = Mock()

        result = manager.check_and_reload(state)

        assert result is False
        assert manager.total_checks == 1
        assert manager.cycle_changes_detected == 0
        assert manager.reload_successes == 0

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_with_cycle_change(self, mock_loader):
        """Test successful reload when cycle changes."""
        mock_loader.check_cycle_changed.return_value = True
        mock_collectibles = [
            {'name': 'Card 1', 'x': 100, 'y': 200},
            {'name': 'Card 2', 'x': 300, 'y': 400}
        ]
        mock_loader.load.return_value = mock_collectibles

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        result = manager.check_and_reload(state)

        assert result is True
        assert manager.total_checks == 1
        assert manager.cycle_changes_detected == 1
        assert manager.reload_successes == 1
        assert manager.reload_failures == 0

        # Verify state was updated
        state.set_collectibles.assert_called_once_with(mock_collectibles)
        mock_loader.load.assert_called_once_with(state.coord_transform)

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_with_null_state(self, mock_loader):
        """Test handling of null state."""
        mock_loader.check_cycle_changed.return_value = True

        manager = CycleManager()

        result = manager.check_and_reload(None)

        assert result is False
        assert manager.cycle_changes_detected == 1
        assert manager.reload_failures == 1
        assert manager.reload_successes == 0

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_with_loader_exception(self, mock_loader):
        """Test handling of exception during reload."""
        mock_loader.check_cycle_changed.side_effect = RuntimeError("API error")

        manager = CycleManager()
        state = Mock()

        result = manager.check_and_reload(state)

        assert result is False
        assert manager.total_checks == 1
        assert manager.reload_failures == 1

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_with_load_exception(self, mock_loader):
        """Test handling of exception during collectibles load."""
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.side_effect = RuntimeError("Network error")

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        result = manager.check_and_reload(state)

        assert result is False
        assert manager.cycle_changes_detected == 1
        assert manager.reload_failures == 1
        assert manager.reload_successes == 0

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_check_and_reload_multiple_times(self, mock_loader):
        """Test multiple check and reload cycles."""
        # First check: no change
        mock_loader.check_cycle_changed.return_value = False

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        result1 = manager.check_and_reload(state)
        assert result1 is False
        assert manager.total_checks == 1

        # Second check: cycle changed
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.return_value = [{'name': 'Card 1'}]

        result2 = manager.check_and_reload(state)
        assert result2 is True
        assert manager.total_checks == 2
        assert manager.cycle_changes_detected == 1
        assert manager.reload_successes == 1

        # Third check: no change
        mock_loader.check_cycle_changed.return_value = False

        result3 = manager.check_and_reload(state)
        assert result3 is False
        assert manager.total_checks == 3
        assert manager.cycle_changes_detected == 1  # Still 1
        assert manager.reload_successes == 1


class TestCycleManagerStatistics:
    """Test statistics tracking."""

    def test_get_stats_initial(self):
        """Test initial statistics."""
        manager = CycleManager(check_interval=300.0)
        stats = manager.get_stats()

        assert stats['check_interval'] == 300.0
        assert stats['total_checks'] == 0
        assert stats['cycle_changes_detected'] == 0
        assert stats['reload_successes'] == 0
        assert stats['reload_failures'] == 0
        assert 'last_check_time' in stats
        assert 'seconds_until_next_check' in stats

    def test_get_stats_seconds_until_next_check(self):
        """Test seconds_until_next_check calculation."""
        manager = CycleManager(check_interval=10.0)

        # Immediately after init
        stats = manager.get_stats()
        assert stats['seconds_until_next_check'] <= 10.0
        assert stats['seconds_until_next_check'] >= 9.0  # Some tolerance for execution time

    def test_get_stats_with_mocked_time(self, mock_time):
        """Test stats calculation with controlled time."""
        manager = CycleManager(check_interval=300.0)

        initial_stats = manager.get_stats()
        assert initial_stats['seconds_until_next_check'] >= 299.0

        # Advance time by 100 seconds
        mock_time(100)

        mid_stats = manager.get_stats()
        assert 199.0 <= mid_stats['seconds_until_next_check'] <= 201.0

        # Advance time by another 250 seconds (350 total - past interval)
        mock_time(250)

        late_stats = manager.get_stats()
        # Should be 0 or negative (clamped to 0)
        assert late_stats['seconds_until_next_check'] == 0

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_get_stats_after_checks(self, mock_loader):
        """Test statistics after performing checks."""
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.return_value = [{'name': 'Card 1'}]

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        # Perform several checks
        manager.check_and_reload(state)
        manager.check_and_reload(state)
        manager.check_and_reload(state)

        stats = manager.get_stats()

        assert stats['total_checks'] == 3
        assert stats['cycle_changes_detected'] == 3
        assert stats['reload_successes'] == 3


class TestCycleManagerReset:
    """Test reset functionality."""

    def test_reset_clears_statistics(self):
        """Test that reset clears all statistics."""
        manager = CycleManager()

        # Manually set some statistics
        manager.total_checks = 10
        manager.cycle_changes_detected = 2
        manager.reload_successes = 1
        manager.reload_failures = 1

        manager.reset()

        assert manager.total_checks == 0
        assert manager.cycle_changes_detected == 0
        assert manager.reload_successes == 0
        assert manager.reload_failures == 0

    def test_reset_updates_last_check_time(self):
        """Test that reset updates the last check time."""
        manager = CycleManager()

        initial_time = manager.last_check_time
        time.sleep(0.01)  # Small delay

        manager.reset()

        # Last check time should be updated
        assert manager.last_check_time > initial_time

    def test_reset_allows_immediate_recheck(self):
        """Test that reset doesn't immediately trigger a check."""
        manager = CycleManager(check_interval=0.05)

        # Wait for interval
        time.sleep(0.06)
        assert manager.should_check_now() is True

        # Reset
        manager.reset()

        # Should not trigger immediately after reset
        assert manager.should_check_now() is False

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_reset_after_checks(self, mock_loader):
        """Test reset after performing checks."""
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.return_value = [{'name': 'Card 1'}]

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        # Perform checks
        manager.check_and_reload(state)
        manager.check_and_reload(state)

        assert manager.total_checks == 2
        assert manager.reload_successes == 2

        # Reset
        manager.reset()

        # Statistics should be cleared
        stats = manager.get_stats()
        assert stats['total_checks'] == 0
        assert stats['cycle_changes_detected'] == 0
        assert stats['reload_successes'] == 0
        assert stats['reload_failures'] == 0


class TestCycleManagerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_short_check_interval(self):
        """Test with very short check interval."""
        manager = CycleManager(check_interval=0.001)  # 1ms

        time.sleep(0.002)
        assert manager.should_check_now() is True

    def test_very_long_check_interval(self):
        """Test with very long check interval."""
        manager = CycleManager(check_interval=86400.0)  # 24 hours

        stats = manager.get_stats()
        assert stats['check_interval'] == 86400.0
        assert stats['seconds_until_next_check'] > 86000

    def test_zero_check_interval(self):
        """Test with zero check interval (always trigger)."""
        manager = CycleManager(check_interval=0.0)

        # Should trigger on every call
        assert manager.should_check_now() is True
        assert manager.should_check_now() is True

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_empty_collectibles_reload(self, mock_loader):
        """Test reload with empty collectibles list."""
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.return_value = []  # Empty list

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()

        result = manager.check_and_reload(state)

        # Should still count as success
        assert result is True
        assert manager.reload_successes == 1
        state.set_collectibles.assert_called_once_with([])

    @patch('core.collectibles.collectibles_repository.CollectiblesRepository')
    def test_state_without_set_collectibles_method(self, mock_loader):
        """Test handling when state doesn't have set_collectibles method."""
        mock_loader.check_cycle_changed.return_value = True
        mock_loader.load.return_value = [{'name': 'Card 1'}]

        manager = CycleManager()
        state = Mock()
        state.coord_transform = Mock()
        del state.set_collectibles  # Remove method

        result = manager.check_and_reload(state)

        # Should catch AttributeError and count as failure
        assert result is False
        assert manager.reload_failures == 1
