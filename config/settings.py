"""
Configuration settings for RDO Map Overlay System
Optimized for speed while maintaining good accuracy
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Global debug flag - set to True to enable verbose logging
DEBUG = False


@dataclass(frozen=True)
class MapDimensions:
    """Map dimension constants"""
    HQ_WIDTH: int = 21617
    HQ_HEIGHT: int = 16785
    DETECTION_SCALE: float = 0.5
    LAT_MIN: float = -144.0
    LAT_MAX: float = 0.0
    LNG_MIN: float = 0.0
    LNG_MAX: float = 176.0
    
    CALIBRATION_POINTS: Tuple[Tuple[float, float, int, int], ...] = (
        (-30.3914, 118.2733, 14608, 2506),
        (-104.7555, 62.4881, 7494, 11995),
        (-78.4988, 93.5773, 11457, 8649)
    )


@dataclass(frozen=True)
class MatchingConfig:
    """Feature matching configuration - optimized for speed"""
    
    PYRAMID_SCALES: Tuple[float, ...] = (
        0.125,   # 1/8 - Coarse (fast)
        0.25,    # 1/4 - Medium (balanced)
        0.5      # 1/2 - Fine (accurate)
    )
    
    # Reduced feature counts for speed
    MAX_FEATURES_PER_SCALE: Dict[float, int] = field(default_factory=lambda: {
        0.125: 800,   # Fewer features at coarse scale
        0.25: 1500,   # Moderate for medium
        0.5: 2500     # More for fine detail (but not excessive)
    })
    
    # Game features - kept low for speed
    MAX_GAME_FEATURES_PER_SCALE: Dict[float, int] = field(default_factory=lambda: {
        0.125: 300,
        0.25: 400,
        0.5: 500
    })
    
    # Simplified - no complex expansions
    SEARCH_EXPANSION_FACTORS: Dict[float, float] = field(default_factory=lambda: {
        0.125: 1.5,
        0.25: 1.3,
        0.5: 1.2
    })
    
    # Removed multiple game scales - handled in matcher
    RATIO_TEST_THRESHOLD: float = 0.75
    MIN_MATCHES_REQUIRED: int = 6
    MIN_INLIERS_REQUIRED: int = 5
    RANSAC_REPROJ_THRESHOLD: float = 5.0
    
    MIN_CONFIDENCE_TO_ACCEPT: float = 0.3
    MIN_CONFIDENCE_TO_TRACK: float = 0.6
    MIN_CONFIDENCE_FOR_EARLY_EXIT: float = 0.8


@dataclass(frozen=True)
class PerformanceConfig:
    """Performance settings"""
    TARGET_TOTAL_TIME_MS: int = 100
    USE_THREADING: bool = False  # Threading often adds overhead for small tasks
    MAX_WORKER_THREADS: int = 2
    CACHE_PYRAMID_TO_DISK: bool = True


@dataclass(frozen=True)
class CollectibleConfig:
    """Collectible system configuration"""
    CATEGORY_TO_CYCLE_KEY: Dict[str, str] = field(default_factory=lambda: {
        'arrowhead': 'arrowhead', 'bottle': 'bottle', 'coin': 'coin',
        'egg': 'egg', 'flower': 'flower', 'heirlooms': 'heirlooms',
        'cups': 'tarot_cards', 'pentacles': 'tarot_cards',
        'swords': 'tarot_cards', 'wands': 'tarot_cards',
        'bracelet': 'lost_jewelry', 'earring': 'lost_jewelry',
        'necklace': 'lost_jewelry', 'ring': 'lost_jewelry',
        'jewelry_random': 'lost_jewelry', 'coastal': 'fossils',
        'oceanic': 'fossils', 'megafauna': 'fossils',
        'fossils_random': 'fossils', 'random': 'random'
    })
    
    API_TIMEOUT_SECONDS: int = 15


@dataclass(frozen=True)
class ServerConfig:
    """Flask server configuration"""
    HOST: str = '0.0.0.0'
    PORT: int = 5000
    DEBUG: bool = False
    CORS_ENABLED: bool = True
    CONTINUOUS_CAPTURE: bool = True  # Enable continuous background capture
    CAPTURE_FPS: int = 60  # Target capture rate for smooth panning (60 fps = 16.7ms interval)
    USE_ROI_TRACKING: bool = False  # ROI tracking not yet implemented (would need map cropping)


@dataclass(frozen=True)
class ScreenshotConfig:
    """Screenshot configuration"""
    CROP_TOP_PERCENTAGE: float = 0.8
    MONITOR_INDEX: int = 1


# Create singleton instances
MAP_DIMENSIONS = MapDimensions()
MATCHING = MatchingConfig()
PERFORMANCE = PerformanceConfig()
COLLECTIBLES = CollectibleConfig()
SERVER = ServerConfig()
SCREENSHOT = ScreenshotConfig()