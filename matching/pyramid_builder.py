"""Feature pyramid construction"""

import cv2
import numpy as np
import pickle
from typing import Dict
from config import MATCHING, CACHE_PATHS


class PyramidBuilder:
    """Builds and manages feature pyramids for multi-scale matching"""
    
    @staticmethod
    def build_pyramids(full_map: np.ndarray) -> Dict:
        """Build feature pyramids at configured scales"""
        pyramids = {}
        
        for scale in MATCHING.PYRAMID_SCALES:
            print(f"Building pyramid at scale {scale}...")
            w = int(full_map.shape[1] * scale)
            h = int(full_map.shape[0] * scale)
            scaled_map = cv2.resize(full_map, (w, h), interpolation=cv2.INTER_AREA)
            
            detector = cv2.AKAZE_create()
            max_features = MATCHING.MAX_FEATURES_PER_SCALE[scale]
            detector.setMaxPoints(max_features)
            
            kp, des = detector.detectAndCompute(scaled_map, None)
            
            if des is not None and len(kp) > 0:
                pyramids[scale] = {
                    'keypoints': kp,
                    'descriptors': des,
                    'shape': scaled_map.shape,
                    'original_shape': full_map.shape
                }
                print(f"  Scale {scale}: {len(kp)} features, size {w}x{h}")
        
        return pyramids
    
    @staticmethod
    def save_pyramids(pyramids: Dict) -> None:
        """Save pyramids to cache"""
        CACHE_PATHS.ensure_cache_dir_exists()
        cache_data = {}
        
        for scale, data in pyramids.items():
            cache_data[scale] = {
                'keypoints': [
                    {'pt': kp.pt, 'size': kp.size, 'angle': kp.angle,
                     'response': kp.response, 'octave': kp.octave,
                     'class_id': kp.class_id}
                    for kp in data['keypoints']
                ],
                'descriptors': data['descriptors'],
                'shape': data['shape']
            }
        
        with open(CACHE_PATHS.pyramid_cache_path(), 'wb') as f:
            pickle.dump(cache_data, f)
        print("Cached pyramids to disk")
    
    @staticmethod
    def load_pyramids(original_shape: tuple) -> Dict:
        """Load pyramids from cache"""
        cache_path = CACHE_PATHS.pyramid_cache_path()
        if not cache_path.exists():
            return None
        
        print("Loading cached pyramids...")
        with open(cache_path, 'rb') as f:
            cached = pickle.load(f)
        
        pyramids = {}
        for scale, data in cached.items():
            pyramids[scale] = {
                'keypoints': [
                    cv2.KeyPoint(
                        x=float(kp['pt'][0]),
                        y=float(kp['pt'][1]),
                        size=float(kp['size']),
                        angle=float(kp['angle']),
                        response=float(kp['response']),
                        octave=int(kp['octave']),
                        class_id=int(kp['class_id'])
                    ) for kp in data['keypoints']
                ],
                'descriptors': data['descriptors'],
                'shape': data['shape'],
                'original_shape': original_shape
            }
        
        print(f"Loaded pyramids: {list(pyramids.keys())}")
        return pyramids
