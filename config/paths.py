"""File paths and external URLs configuration"""

from pathlib import Path


class CachePaths:
    """Cache directory and file paths"""
    # Data directory for all cached/stored files
    DATA_DIR = Path('data')
    CACHE_DIR = DATA_DIR / 'cache'
    
    # Cache files
    PYRAMID_CACHE_FILE = 'cascade_pyramids_v8_adaptive_features.pkl'
    GRAYSCALE_MAP_FILE = 'full_map_grayscale.png'
    
    # Source files (can be in data directory or root)
    HQ_MAP_SOURCE_FILE = 'rdr2_map_hq.png'  # Check both root and data/
    
    @classmethod
    def ensure_cache_dir_exists(cls):
        """Create all necessary directories"""
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def pyramid_cache_path(cls):
        """Full path to pyramid cache file"""
        return cls.CACHE_DIR / cls.PYRAMID_CACHE_FILE
    
    @classmethod
    def grayscale_map_path(cls):
        """Full path to grayscale map cache file"""
        return cls.CACHE_DIR / cls.GRAYSCALE_MAP_FILE
    
    @classmethod
    def find_hq_map_source(cls):
        """Look for HQ map in multiple locations"""
        import os
        import sys

        # Check in order of preference
        locations = [
            Path(cls.HQ_MAP_SOURCE_FILE),  # Current directory
            cls.DATA_DIR / cls.HQ_MAP_SOURCE_FILE,  # data directory
            cls.CACHE_DIR / cls.HQ_MAP_SOURCE_FILE,  # cache directory
        ]

        # Also check downloaded cache location (%APPDATA% on Windows)
        if sys.platform == 'win32':
            appdata = os.getenv('APPDATA')
        elif sys.platform == 'darwin':
            appdata = os.path.expanduser('~/Library/Application Support')
        else:
            appdata = os.path.expanduser('~/.local/share')

        if appdata:
            downloaded_map = Path(appdata) / 'RDO-Map-Overlay' / 'data' / cls.HQ_MAP_SOURCE_FILE
            locations.insert(0, downloaded_map)  # Check downloaded location first

        for location in locations:
            if location.exists():
                return location
        return None


class ExternalURLs:
    """External API URLs"""
    # Joan Ropke's Collectors Map API
    ROPKE_ITEMS_API = "https://jeanropke.github.io/RDR2CollectorsMap/data/items.json"
    ROPKE_CYCLES_API = "https://jeanropke.github.io/RDR2CollectorsMap/data/cycles.json"

    # HQ Map download URL (167MB PNG from GitHub raw content)
    # Uses raw.githubusercontent.com for direct file access (works with Git LFS)
    HQ_MAP_DOWNLOAD_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/rdo_overlay/main/data/rdr2_map_hq.png"


# Create singleton instances
CACHE_PATHS = CachePaths()
EXTERNAL_URLS = ExternalURLs()