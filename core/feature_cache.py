"""
Feature cache for fast startup.
Caches preprocessed map and AKAZE features to avoid recomputation.
"""

import pickle
import hashlib
import numpy as np
import cv2
from pathlib import Path
from typing import Optional, Tuple, List


class FeatureCache:
    """Cache for preprocessed map and extracted features"""

    CACHE_VERSION = 1  # Increment when cache format changes

    def __init__(self, cache_dir: Path):
        """
        Initialize feature cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.preprocessed_map_cache = self.cache_dir / 'preprocessed_map_v1.png'
        self.features_cache = self.cache_dir / 'map_features_v1.pkl'
        self.cache_metadata = self.cache_dir / 'feature_cache_metadata.pkl'

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file for cache validation"""
        if not file_path.exists():
            return ""

        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def _is_cache_valid(self, source_file: Path, params: dict) -> bool:
        """Check if cached data is still valid"""
        if not self.cache_metadata.exists():
            return False

        try:
            with open(self.cache_metadata, 'rb') as f:
                metadata = pickle.load(f)

            # Check version
            if metadata.get('version') != self.CACHE_VERSION:
                return False

            # Check source file hash
            current_hash = self._compute_file_hash(source_file)
            if metadata.get('source_hash') != current_hash:
                return False

            # Check preprocessing parameters
            if metadata.get('params') != params:
                return False

            # Check if cache files exist
            if not self.preprocessed_map_cache.exists():
                return False
            if not self.features_cache.exists():
                return False

            return True

        except Exception as e:
            print(f"Cache validation failed: {e}")
            return False

    def load(self, source_file: Path, params: dict) -> Optional[Tuple[np.ndarray, List, np.ndarray]]:
        """
        Load preprocessed map and features from cache.

        Args:
            source_file: Original HQ map file
            params: Preprocessing parameters (scale, etc.)

        Returns:
            Tuple of (preprocessed_map, keypoints, descriptors) or None if cache invalid
        """
        if not self._is_cache_valid(source_file, params):
            return None

        try:
            # Load preprocessed map
            preprocessed_map = cv2.imread(str(self.preprocessed_map_cache), cv2.IMREAD_GRAYSCALE)
            if preprocessed_map is None:
                return None

            # Load features
            with open(self.features_cache, 'rb') as f:
                features_data = pickle.load(f)

            keypoints = features_data['keypoints']
            descriptors = features_data['descriptors']

            return preprocessed_map, keypoints, descriptors

        except Exception as e:
            print(f"Cache load failed: {e}")
            return None

    def save(self, source_file: Path, params: dict, preprocessed_map: np.ndarray,
             keypoints: List, descriptors: np.ndarray):
        """
        Save preprocessed map and features to cache.

        Args:
            source_file: Original HQ map file
            params: Preprocessing parameters
            preprocessed_map: Preprocessed detection-scale map
            keypoints: List of cv2.KeyPoint objects
            descriptors: Numpy array of descriptors
        """
        try:
            # Save preprocessed map
            cv2.imwrite(str(self.preprocessed_map_cache), preprocessed_map)

            # Save features (keypoints are not directly picklable, convert to data)
            keypoint_data = [(kp.pt, kp.size, kp.angle, kp.response, kp.octave, kp.class_id)
                           for kp in keypoints]

            features_data = {
                'keypoints': keypoint_data,
                'descriptors': descriptors
            }

            with open(self.features_cache, 'wb') as f:
                pickle.dump(features_data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Save metadata
            metadata = {
                'version': self.CACHE_VERSION,
                'source_hash': self._compute_file_hash(source_file),
                'params': params
            }

            with open(self.cache_metadata, 'wb') as f:
                pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

            print(f"Feature cache saved ({len(keypoints)} keypoints)")

        except Exception as e:
            print(f"Cache save failed: {e}")

    @staticmethod
    def keypoints_from_data(keypoint_data: List[Tuple]) -> List:
        """
        Reconstruct cv2.KeyPoint objects from saved data.

        Args:
            keypoint_data: List of tuples (pt, size, angle, response, octave, class_id)

        Returns:
            List of cv2.KeyPoint objects
        """
        keypoints = []
        for pt, size, angle, response, octave, class_id in keypoint_data:
            kp = cv2.KeyPoint(
                x=pt[0], y=pt[1],
                size=size,
                angle=angle,
                response=response,
                octave=octave,
                class_id=class_id
            )
            keypoints.append(kp)
        return keypoints
