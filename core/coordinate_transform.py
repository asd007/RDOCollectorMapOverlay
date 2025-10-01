"""Coordinate system transformations"""

import numpy as np
from typing import Tuple
from config import MAP_DIMENSIONS


class CoordinateTransform:
    """Handles coordinate transformations between different systems"""
    
    def __init__(self):
        self._latlng_params = None
        self._initialize_transformations()
    
    def _initialize_transformations(self):
        """Initialize linear transformation parameters"""
        points = MAP_DIMENSIONS.CALIBRATION_POINTS
        lngs = np.array([lng for _, lng, _, _ in points])
        lats = np.array([lat for lat, _, _, _ in points])
        hq_xs = np.array([hq_x for _, _, hq_x, _ in points])
        hq_ys = np.array([hq_y for _, _, _, hq_y in points])
        
        A_x = np.column_stack([lngs, np.ones(len(lngs))])
        scale_x, offset_x = np.linalg.lstsq(A_x, hq_xs, rcond=None)[0]
        
        A_y = np.column_stack([lats, np.ones(len(lats))])
        scale_y, offset_y = np.linalg.lstsq(A_y, hq_ys, rcond=None)[0]
        
        self._latlng_params = {
            'scale_x': scale_x, 'offset_x': offset_x,
            'scale_y': scale_y, 'offset_y': offset_y
        }
    
    def latlng_to_hq(self, lat: float, lng: float) -> Tuple[int, int]:
        """Convert lat/lng to HQ map coordinates"""
        params = self._latlng_params
        hq_x = int(params['scale_x'] * lng + params['offset_x'])
        hq_y = int(params['scale_y'] * lat + params['offset_y'])
        hq_x = max(0, min(hq_x, MAP_DIMENSIONS.HQ_WIDTH - 1))
        hq_y = max(0, min(hq_y, MAP_DIMENSIONS.HQ_HEIGHT - 1))
        return hq_x, hq_y
    
    def hq_to_detection(self, hq_x: int, hq_y: int) -> Tuple[int, int]:
        """Convert HQ coordinates to detection space (0.5x)"""
        return int(hq_x * MAP_DIMENSIONS.DETECTION_SCALE), int(hq_y * MAP_DIMENSIONS.DETECTION_SCALE)
