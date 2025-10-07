"""
Pytest configuration and shared fixtures.
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import List
from unittest.mock import Mock, MagicMock


# === Test Data Fixtures ===

@pytest.fixture
def mock_screenshot():
    """Create a mock screenshot (1920x1080 RGB)."""
    return np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def mock_screenshot_small():
    """Create a small mock screenshot for faster tests."""
    return np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)


@pytest.fixture
def mock_viewport():
    """Create a mock viewport dict."""
    return {
        'x': 5000.0,
        'y': 4000.0,
        'width': 2000.0,
        'height': 1500.0,
        'map_x': 5000.0,
        'map_y': 4000.0,
        'map_w': 2000.0,
        'map_h': 1500.0
    }


@pytest.fixture
def mock_collectible():
    """Create a mock collectible dict."""
    return {
        'x': 960,  # Screen coordinates
        'y': 540,
        'map_x': 6000.0,  # Detection space coordinates
        'map_y': 4500.0,
        'type': 'card_tarot',
        'name': 'The Fool',
        'category': 'tarot_cards',
        'help': 'Found on a barrel',
        'video': 'https://example.com/video'
    }


@pytest.fixture
def mock_collectibles(mock_collectible):
    """Create a list of mock collectibles."""
    collectibles = []
    for i in range(10):
        col = mock_collectible.copy()
        col['x'] = 500 + i * 100
        col['y'] = 500 + i * 50
        col['map_x'] = 5500.0 + i * 100
        col['map_y'] = 4200.0 + i * 50
        col['name'] = f'Collectible {i}'
        collectibles.append(col)
    return collectibles


@pytest.fixture
def mock_match_result(mock_viewport):
    """Create a mock match result."""
    return {
        'success': True,
        'match_type': 'akaze',  # High-level categorization
        'map_x': mock_viewport['x'],
        'map_y': mock_viewport['y'],
        'map_w': mock_viewport['width'],
        'map_h': mock_viewport['height'],
        'confidence': 0.85,
        'inliers': 150,
        'match_time_ms': 45.5,
        'cascade_info': {
            'match_type': 'akaze',
            'final_level': 0.5,  # Scale level
            'prediction_used': True,
            'roi_used': True,
            'prediction_ms': 2.3,
            'motion_prediction': {
                'offset_px': (10, 5),
                'phase_confidence': 0.92
            }
        }
    }


@pytest.fixture
def mock_capture_func():
    """Create a mock capture function."""
    def capture():
        screenshot = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        return screenshot, None  # (screenshot, error)
    return capture


@pytest.fixture
def mock_capture_func_error():
    """Create a mock capture function that returns errors."""
    def capture():
        return None, "Capture failed"
    return capture


@pytest.fixture
def mock_matcher():
    """Create a mock cascade matcher."""
    matcher = Mock()
    matcher.match.return_value = {
        'success': True,
        'match_type': 'akaze',
        'map_x': 5000.0,
        'map_y': 4000.0,
        'map_w': 2000.0,
        'map_h': 1500.0,
        'confidence': 0.85,
        'inliers': 150,
        'cascade_info': {
            'match_type': 'akaze',
            'final_level': 0.5  # Scale level
        }
    }
    return matcher


@pytest.fixture
def mock_collectibles_func(mock_collectibles):
    """Create a mock collectibles function."""
    def get_collectibles(viewport):
        return mock_collectibles
    return get_collectibles


# === Model Fixtures ===

@dataclass
class MockCollectible:
    """Mock collectible model for testing."""
    x: float
    y: float
    type: str
    name: str
    category: str
    help: str = ""
    video: str = ""
    lat: float = None
    lng: float = None


@pytest.fixture
def mock_collectible_model():
    """Create a mock Collectible model instance."""
    return MockCollectible(
        x=6000.0,
        y=4500.0,
        type='card_tarot',
        name='The Fool',
        category='tarot_cards',
        help='Found on a barrel'
    )


@pytest.fixture
def mock_collectible_models():
    """Create a list of mock Collectible model instances."""
    collectibles = []
    for i in range(10):
        collectibles.append(MockCollectible(
            x=5500.0 + i * 100,
            y=4200.0 + i * 50,
            type='card_tarot',
            name=f'Card {i}',
            category='tarot_cards'
        ))
    return collectibles


@pytest.fixture
def mock_viewport_obj():
    """Create a mock Viewport object (dataclass instance)."""
    from matching.viewport_tracker import Viewport
    import time
    return Viewport(
        x=5000.0,
        y=4000.0,
        width=2000.0,
        height=1500.0,
        confidence=0.85,
        timestamp=time.time()
    )


# === Qt Fixtures ===

@pytest.fixture
def mock_qobject():
    """Create a mock QObject parent."""
    return None  # QObject parent is optional


# === Time Control Fixtures ===

@pytest.fixture
def mock_time(monkeypatch):
    """Mock time.time() for deterministic tests."""
    current_time = [1000.0]  # Use list for mutability

    def mock_time_func():
        return current_time[0]

    def advance_time(seconds):
        current_time[0] += seconds

    monkeypatch.setattr('time.time', mock_time_func)
    return advance_time


# === Performance Fixtures ===

@pytest.fixture
def fast_timings():
    """Return typical fast processing timings (ms)."""
    return {
        'capture_ms': 10.0,
        'match_ms': 45.0,
        'overlay_ms': 5.0,
        'total_ms': 60.0
    }


@pytest.fixture
def slow_timings():
    """Return typical slow processing timings (ms)."""
    return {
        'capture_ms': 20.0,
        'match_ms': 150.0,
        'overlay_ms': 10.0,
        'total_ms': 180.0
    }
