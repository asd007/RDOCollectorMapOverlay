"""Core functionality module"""

# Backward compatibility - re-export from reorganized subdirectories
from .map.coordinate_transform import CoordinateTransform
from .map.map_loader import MapLoader
from .collectibles.collectibles_loader import CollectiblesLoader
from .matching.image_preprocessing import ImagePreprocessor, PREPROCESSOR, preprocess_for_matching

__all__ = ['CoordinateTransform', 'MapLoader', 'CollectiblesLoader',
           'ImagePreprocessor', 'PREPROCESSOR', 'preprocess_for_matching']
