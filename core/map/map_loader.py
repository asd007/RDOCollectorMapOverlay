"""Map loading and caching functionality"""

import cv2
import numpy as np
from typing import Optional
from config import CACHE_PATHS
from core.matching.image_preprocessing import preprocess_for_matching


class MapLoader:
    """Handles map loading and caching"""

    @staticmethod
    def load_map(use_preprocessing: bool = True, posterize_before_gray: bool = False) -> Optional[np.ndarray]:
        """
        Load the game map from cache or HQ source with optional preprocessing.

        Args:
            use_preprocessing: If True, apply Q10 preprocessing (posterize + CLAHE)
            posterize_before_gray: If True, posterize in color space before grayscale conversion

        Returns:
            Loaded and optionally preprocessed map, or None if loading fails
        """
        # Ensure directories exist
        CACHE_PATHS.ensure_cache_dir_exists()

        # Create cache key based on preprocessing options
        cache_suffix = ""
        if use_preprocessing:
            cache_suffix = "_preprocessed"
            if posterize_before_gray:
                cache_suffix += "_color_first"

        # Try loading from cache first
        if use_preprocessing:
            # Custom cache path for preprocessed versions
            cached_path = CACHE_PATHS.CACHE_DIR / f"full_map_grayscale{cache_suffix}.png"
        else:
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

            if use_preprocessing and posterize_before_gray:
                # Load as color for preprocessing in color space
                full_map_color = cv2.imread(str(hq_source), cv2.IMREAD_COLOR)
                if full_map_color is not None:
                    print(f"Loaded HQ map (color): {full_map_color.shape}")
                    print("Applying Q10 preprocessing (posterize in color space)...")
                    full_map = preprocess_for_matching(full_map_color, posterize_before_gray=True)
                    print(f"Preprocessed map shape: {full_map.shape}")
                else:
                    return None
            else:
                # Load as grayscale
                full_map = cv2.imread(str(hq_source), cv2.IMREAD_GRAYSCALE)
                if full_map is not None:
                    print(f"Loaded HQ map (grayscale): {full_map.shape}")

                    if use_preprocessing:
                        # Apply preprocessing after grayscale conversion
                        print("Applying Q10 preprocessing (posterize after grayscale)...")
                        full_map = preprocess_for_matching(full_map, posterize_before_gray=False)
                        print(f"Preprocessed map shape: {full_map.shape}")
                else:
                    return None

            # Cache it for faster loading next time
            cv2.imwrite(str(cached_path), full_map)
            print(f"Cached map to: {cached_path}")
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