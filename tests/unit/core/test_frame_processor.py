"""
Unit tests for FrameProcessor component.
"""

import pytest
import numpy as np
import hashlib
from unittest.mock import Mock, patch
from core.frame_processor import FrameProcessor


class TestFrameProcessorInitialization:
    """Test FrameProcessor initialization."""

    def test_default_initialization(self, mock_capture_func):
        processor = FrameProcessor(mock_capture_func)
        assert processor.capture_func == mock_capture_func
        assert processor.enable_deduplication is False
        assert processor.enable_map_detection is False
        assert processor.previous_frame_hash is None
        assert processor.cached_result is None

    def test_custom_initialization(self, mock_capture_func):
        processor = FrameProcessor(
            mock_capture_func,
            enable_deduplication=True,
            enable_map_detection=True
        )
        assert processor.enable_deduplication is True
        assert processor.enable_map_detection is True


class TestFrameProcessorCapture:
    """Test frame capture and preprocessing."""

    def test_successful_capture(self, mock_capture_func):
        """Test successful frame capture."""
        processor = FrameProcessor(mock_capture_func)
        screenshot, is_duplicate, error = processor.capture_and_preprocess()

        assert screenshot is not None
        assert is_duplicate is False
        assert error is None
        assert screenshot.shape == (1080, 1920, 3)
        assert processor.total_frames == 1

    def test_capture_with_error(self, mock_capture_func_error):
        """Test capture that returns an error."""
        processor = FrameProcessor(mock_capture_func_error)
        screenshot, is_duplicate, error = processor.capture_and_preprocess()

        assert screenshot is None
        assert is_duplicate is False
        assert error is not None
        assert "Capture failed" in error
        assert processor.capture_errors == 1

    def test_capture_exception(self):
        """Test capture function that raises exception."""
        def bad_capture():
            raise RuntimeError("Camera disconnected")

        processor = FrameProcessor(bad_capture)
        screenshot, is_duplicate, error = processor.capture_and_preprocess()

        assert screenshot is None
        assert error is not None
        assert "Camera disconnected" in error
        assert processor.capture_errors == 1


class TestFrameProcessorDeduplication:
    """Test frame deduplication."""

    def test_deduplication_disabled_by_default(self, mock_screenshot):
        """Test that deduplication is disabled by default."""
        def capture():
            return mock_screenshot.copy(), None

        processor = FrameProcessor(capture, enable_deduplication=False)

        # Capture same frame twice
        s1, dup1, _ = processor.capture_and_preprocess()
        s2, dup2, _ = processor.capture_and_preprocess()

        # Should not detect as duplicate even though they're identical
        assert dup1 is False
        assert dup2 is False
        assert processor.duplicate_frames == 0

    def test_deduplication_enabled(self, mock_screenshot):
        """Test frame deduplication when enabled."""
        def capture():
            return mock_screenshot.copy(), None

        processor = FrameProcessor(capture, enable_deduplication=True)

        # First frame
        s1, dup1, _ = processor.capture_and_preprocess()
        assert dup1 is False

        # Cache a result (deduplication requires cached result)
        processor.cache_result({'test': 'result'})

        # Same frame again
        s2, dup2, _ = processor.capture_and_preprocess()
        assert dup2 is True
        assert processor.duplicate_frames == 1

    def test_deduplication_different_frames(self):
        """Test that different frames are not marked as duplicates."""
        frame_number = [0]

        def capture():
            # Return different frame each time
            frame_number[0] += 1
            frame = np.full((100, 100, 3), frame_number[0], dtype=np.uint8)
            return frame, None

        processor = FrameProcessor(capture, enable_deduplication=True)

        s1, dup1, _ = processor.capture_and_preprocess()
        s2, dup2, _ = processor.capture_and_preprocess()

        assert dup1 is False
        assert dup2 is False
        assert processor.duplicate_frames == 0

    def test_hash_computation(self, mock_screenshot):
        """Test that hash is computed correctly."""
        def capture():
            return mock_screenshot, None

        processor = FrameProcessor(capture, enable_deduplication=True)

        # Capture frame
        processor.capture_and_preprocess()

        # Hash should be stored
        assert processor.previous_frame_hash is not None
        expected_hash = hashlib.md5(mock_screenshot.tobytes()).hexdigest()
        assert processor.previous_frame_hash == expected_hash


class TestFrameProcessorCaching:
    """Test result caching."""

    def test_cache_result(self, mock_capture_func):
        """Test caching a result."""
        processor = FrameProcessor(mock_capture_func)

        result = {'success': True, 'viewport': {}, 'collectibles': []}
        processor.cache_result(result)

        cached = processor.get_cached_result()
        assert cached is not None
        assert cached['success'] is True

    def test_cache_result_returns_copy(self, mock_capture_func):
        """Test that get_cached_result returns a copy."""
        processor = FrameProcessor(mock_capture_func)

        result = {'success': True, 'data': [1, 2, 3]}
        processor.cache_result(result)

        cached1 = processor.get_cached_result()
        cached2 = processor.get_cached_result()

        # Should be different objects
        assert cached1 is not cached2
        # But same content
        assert cached1 == cached2

    def test_reset_cache(self, mock_capture_func):
        """Test resetting the cache."""
        processor = FrameProcessor(mock_capture_func)

        result = {'success': True}
        processor.cache_result(result)
        assert processor.get_cached_result() is not None

        processor.reset_cache()
        assert processor.get_cached_result() is None
        assert processor.previous_frame_hash is None


class TestFrameProcessorStatistics:
    """Test statistics tracking."""

    def test_get_stats_initial(self, mock_capture_func):
        """Test initial statistics."""
        processor = FrameProcessor(mock_capture_func)
        stats = processor.get_stats()

        assert stats['total_frames'] == 0
        assert stats['duplicate_frames'] == 0
        assert stats['map_not_visible_frames'] == 0
        assert stats['capture_errors'] == 0
        assert stats['duplicate_rate'] == 0.0

    def test_get_stats_after_captures(self):
        """Test statistics after processing frames."""
        call_count = [0]

        def capture():
            call_count[0] += 1
            if call_count[0] == 3:
                return None, "Error"
            frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            return frame, None

        processor = FrameProcessor(capture, enable_deduplication=True)

        # Process several frames
        processor.capture_and_preprocess()  # Frame 1 (new)
        processor.capture_and_preprocess()  # Frame 2 (different)
        processor.capture_and_preprocess()  # Frame 3 (error)

        stats = processor.get_stats()

        assert stats['total_frames'] == 3
        assert stats['capture_errors'] == 1
        assert stats['deduplication_enabled'] is True

    def test_duplicate_rate_calculation(self, mock_screenshot):
        """Test duplicate rate calculation."""
        def capture():
            return mock_screenshot.copy(), None

        processor = FrameProcessor(capture, enable_deduplication=True)

        # Capture first frame and cache result
        processor.capture_and_preprocess()
        processor.cache_result({'test': 'result'})

        # Capture 4 more duplicate frames
        for _ in range(4):
            processor.capture_and_preprocess()

        stats = processor.get_stats()
        assert stats['total_frames'] == 5
        assert stats['duplicate_frames'] == 4
        assert stats['duplicate_rate'] == pytest.approx(0.8, rel=0.01)


class TestFrameProcessorMapDetection:
    """Test map visibility detection."""

    def test_map_detection_disabled(self, mock_screenshot):
        """Test that map detection is disabled by default."""
        def capture():
            return mock_screenshot, None

        processor = FrameProcessor(capture, enable_map_detection=False)
        screenshot, is_dup, error = processor.capture_and_preprocess()

        # Should succeed even if map not visible
        assert screenshot is not None
        assert error is None
        assert processor.map_not_visible_frames == 0

    @patch('core.map_detector.is_map_visible')
    def test_map_detection_enabled(self, mock_is_map_visible, mock_screenshot):
        """Test map detection when enabled."""
        mock_is_map_visible.return_value = False

        def capture():
            return mock_screenshot, None

        processor = FrameProcessor(capture, enable_map_detection=True)
        screenshot, is_dup, error = processor.capture_and_preprocess()

        # Should return None when map not visible
        assert screenshot is None
        assert error == "Map not visible"
        assert processor.map_not_visible_frames == 1

    @patch('core.map_detector.is_map_visible')
    def test_map_detection_success(self, mock_is_map_visible, mock_screenshot):
        """Test successful map detection."""
        mock_is_map_visible.return_value = True

        def capture():
            return mock_screenshot, None

        processor = FrameProcessor(capture, enable_map_detection=True)
        screenshot, is_dup, error = processor.capture_and_preprocess()

        # Should succeed when map is visible
        assert screenshot is not None
        assert error is None
        assert processor.map_not_visible_frames == 0
