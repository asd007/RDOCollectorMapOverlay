"""Application state management"""

import numpy as np
from typing import Optional, List, Dict
from models import Collectible


class OverlayState:
    """Global application state"""
    
    # Fixed screen dimensions
    SCREEN_WIDTH = 1920
    SCREEN_HEIGHT = 1080
    
    def __init__(self):
        self.full_map: Optional[np.ndarray] = None
        self.matcher = None
        self.coord_transform = None
        self.collectibles: List[Collectible] = []
        self.collectibles_x: Optional[np.ndarray] = None
        self.collectibles_y: Optional[np.ndarray] = None
        self.is_initialized = False
    
    def set_collectibles(self, collectibles: List[Collectible]):
        """Update collectibles and prepare numpy arrays for fast lookup"""
        self.collectibles = collectibles
        if collectibles:
            self.collectibles_x = np.array([c.x for c in collectibles], dtype=np.int32)
            self.collectibles_y = np.array([c.y for c in collectibles], dtype=np.int32)
        else:
            self.collectibles_x = None
            self.collectibles_y = None
    
    def get_visible_collectibles(self, viewport: Dict) -> List[Dict]:
        """
        Get collectibles visible in current viewport
        Viewport is from cropped image but collectibles display on full screen
        """
        if not self.collectibles or self.collectibles_x is None:
            return []
        
        x1, y1 = viewport['map_x'], viewport['map_y']
        x2, y2 = x1 + viewport['map_w'], y1 + viewport['map_h']
        
        # Fast numpy filtering for collectibles in map viewport
        in_view = (
            (self.collectibles_x >= x1) & (self.collectibles_x <= x2) &
            (self.collectibles_y >= y1) & (self.collectibles_y <= y2)
        )
        
        visible_indices = np.where(in_view)[0]
        
        # Scale from detection space viewport to full screen
        scale_x = self.SCREEN_WIDTH / viewport['map_w']
        scale_y = self.SCREEN_HEIGHT / viewport['map_h']
        
        visible = []
        for idx in visible_indices:
            col = self.collectibles[idx]
            
            # Calculate position on full screen
            screen_x = int((col.x - x1) * scale_x)
            screen_y = int((col.y - y1) * scale_y)
            
            # Check bounds against full 1920x1080 screen
            if 0 <= screen_x <= self.SCREEN_WIDTH and 0 <= screen_y <= self.SCREEN_HEIGHT:
                visible.append({
                    'x': screen_x,
                    'y': screen_y,
                    'type': col.type,
                    'name': col.name,
                    'category': col.category,
                    'tool': col.tool,
                    'help': f"Collectible at ({col.lat:.2f}, {col.lng:.2f})"
                })
        
        return visible