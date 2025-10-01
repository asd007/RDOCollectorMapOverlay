"""Map loading and caching functionality"""

import cv2
import numpy as np
from typing import Optional
from config import CACHE_PATHS


class MapLoader:
    """Handles map loading and caching"""
    
    @staticmethod
    def load_map() -> Optional[np.ndarray]:
        """Load the game map from cache or HQ source"""
        # Ensure directories exist
        CACHE_PATHS.ensure_cache_dir_exists()
        
        # Try loading from cache first
        cached_path = CACHE_PATHS.grayscale_map_path()
        if cached_path.exists():
            full_map = cv2.imread(str(cached_path), cv2.IMREAD_GRAYSCALE)
            if full_map is not None:
                print(f"Loaded cached map from: {cached_path}")
                print(f"Map shape: {full_map.shape}")
                return full_map
        
        # Try loading HQ source
        hq_source = CACHE_PATHS.find_hq_map_source()
        if hq_source and hq_source.exists():
            print(f"Loading HQ map from: {hq_source}")
            full_map = cv2.imread(str(hq_source), cv2.IMREAD_GRAYSCALE)
            if full_map is not None:
                print(f"Loaded HQ map: {full_map.shape}")
                # Cache it for faster loading next time
                cv2.imwrite(str(cached_path), full_map)
                print(f"Cached grayscale map to: {cached_path}")
                return full_map
        else:
            # List locations that were checked
            locations_checked = [
                "Current directory: rdr2_map_hq.png",
                "Data directory: data/rdr2_map_hq.png",
                "Cache directory: data/cache/rdr2_map_hq.png"
            ]
            print("ERROR: Could not find HQ map file!")
            print("Please place 'rdr2_map_hq.png' in one of these locations:")
            for loc in locations_checked:
                print(f"  - {loc}")
            return None
        
        return None