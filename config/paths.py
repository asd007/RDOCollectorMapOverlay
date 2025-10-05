"""File paths and external URLs configuration"""

from pathlib import Path


class CachePaths:
    """Cache directory and file paths"""
    # Data directory for all cached/stored files
    # Use absolute paths relative to script location for installed versions
    @classmethod
    def _get_data_dir(cls):
        """Get the data directory path, checking installation structure first"""
        # Check if we're running from an installed location
        # Installation structure: $INSTDIR/app/backend/config/paths.py
        # Data location: $INSTDIR/data/
        script_dir = Path(__file__).resolve().parent.parent  # backend/
        install_root = script_dir.parent.parent  # $INSTDIR/
        installed_data = install_root / 'data'

        if installed_data.exists():
            return installed_data

        # Fallback to relative path for development
        return Path('data')

    @property
    def DATA_DIR(self):
        return self._get_data_dir()

    @property
    def CACHE_DIR(self):
        return self.DATA_DIR / 'cache'
    
    # Cache files
    PYRAMID_CACHE_FILE = 'cascade_pyramids_v8_adaptive_features.pkl'
    GRAYSCALE_MAP_FILE = 'full_map_grayscale.png'
    
    # Source files (can be in data directory or root)
    HQ_MAP_SOURCE_FILE = 'rdr2_map_hq.png'  # Check both root and data/
    
    def ensure_cache_dir_exists(self):
        """Create all necessary directories"""
        self.DATA_DIR.mkdir(exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def pyramid_cache_path(self):
        """Full path to pyramid cache file"""
        return self.CACHE_DIR / self.PYRAMID_CACHE_FILE

    def grayscale_map_path(self):
        """Full path to grayscale map cache file"""
        return self.CACHE_DIR / self.GRAYSCALE_MAP_FILE
    
    @classmethod
    def find_hq_map_source(cls):
        """Look for HQ map in multiple locations"""
        import os
        import sys

        # Start with basic locations
        locations = []

        # 1. Check ProgramData location first (shared across installations, downloaded by installer)
        # %PROGRAMDATA% = %ALLUSERSPROFILE% = C:\ProgramData on most systems
        if sys.platform == 'win32':
            programdata = os.getenv('PROGRAMDATA') or os.getenv('ALLUSERSPROFILE')
            if programdata:
                shared_map = Path(programdata) / 'RDO-Map-Overlay' / 'data' / cls.HQ_MAP_SOURCE_FILE
                locations.append(shared_map)

        # 2. Check installed location (if running from installation directory)
        # Installation structure:
        # $INSTDIR/data/rdr2_map_hq.png
        # $INSTDIR/app/backend/config/paths.py (this file)
        # So from this file: ../../../data/rdr2_map_hq.png
        script_dir = Path(__file__).resolve().parent.parent  # Go up from config/ to backend/
        install_root = script_dir.parent.parent  # Go up from backend/ to app/, then to $INSTDIR
        installed_map = install_root / 'data' / cls.HQ_MAP_SOURCE_FILE
        locations.append(installed_map)

        # 3. Check current working directory
        locations.append(Path(cls.HQ_MAP_SOURCE_FILE))

        # 4. Check data/ subdirectory (development structure)
        locations.append(Path('data') / cls.HQ_MAP_SOURCE_FILE)

        # 5. Check cache/ subdirectory (development structure)
        locations.append(Path('data') / 'cache' / cls.HQ_MAP_SOURCE_FILE)

        # 6. Check AppData cache location (legacy, not used by installer)
        if sys.platform == 'win32':
            appdata = os.getenv('APPDATA')
        elif sys.platform == 'darwin':
            appdata = os.path.expanduser('~/Library/Application Support')
        else:
            appdata = os.path.expanduser('~/.local/share')

        if appdata:
            downloaded_map = Path(appdata) / 'RDO-Map-Overlay' / 'data' / cls.HQ_MAP_SOURCE_FILE
            locations.append(downloaded_map)

        # Search all locations
        from config.settings import DEBUG

        if DEBUG:
            print(f"[DEBUG] Searching for HQ map in the following locations:")
            for i, location in enumerate(locations, 1):
                abs_path = location.resolve() if location.exists() else location
                exists = "[OK] FOUND" if location.exists() else "[ERROR] NOT FOUND"
                print(f"  {i}. {abs_path} [{exists}]")

        for location in locations:
            if location.exists():
                if DEBUG:
                    print(f"[DEBUG] Using HQ map from: {location.resolve()}")
                return location

        print(f"[ERROR] HQ map not found in any of the {len(locations)} locations checked!")
        return None


class ExternalURLs:
    """External API URLs"""
    # Joan Ropke's Collectors Map API
    ROPKE_ITEMS_API = "https://jeanropke.github.io/RDR2CollectorsMap/data/items.json"
    ROPKE_CYCLES_API = "https://jeanropke.github.io/RDR2CollectorsMap/data/cycles.json"

    # HQ Map download URL (167MB PNG from GitHub raw content)
    # Uses raw.githubusercontent.com for direct file access (works with Git LFS)
    HQ_MAP_DOWNLOAD_URL = "https://raw.githubusercontent.com/asd007/rdo-overlay/main/data/rdr2_map_hq.png"


# Create singleton instances
CACHE_PATHS = CachePaths()
EXTERNAL_URLS = ExternalURLs()