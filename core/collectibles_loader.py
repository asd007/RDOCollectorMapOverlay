"""Collectibles loading from Ropke API"""

import requests
from datetime import datetime, timezone
from typing import List
from models import Collectible
from core.coordinate_transform import CoordinateTransform
from config import COLLECTIBLES, EXTERNAL_URLS


class CollectiblesLoader:
    """Loads collectibles from Joan Ropke's API"""
    
    @staticmethod
    def load(coord_transform: CoordinateTransform) -> List[Collectible]:
        """Load today's collectibles"""
        try:
            response = requests.get(
                EXTERNAL_URLS.ROPKE_ITEMS_API,
                timeout=COLLECTIBLES.API_TIMEOUT_SECONDS
            )
            items = response.json()
            active_cycles = CollectiblesLoader._get_active_cycles()
            
            collectibles = []
            for category, cycles_dict in items.items():
                if not isinstance(cycles_dict, dict):
                    continue
                
                cycle_key = COLLECTIBLES.CATEGORY_TO_CYCLE_KEY.get(category, category)
                cycle = str(active_cycles.get(cycle_key, 1))
                
                if cycle in cycles_dict:
                    for item in cycles_dict[cycle]:
                        lat = float(item.get('lat', 0))
                        lng = float(item.get('lng', 0))
                        
                        hq_x, hq_y = coord_transform.latlng_to_hq(lat, lng)
                        detection_x, detection_y = coord_transform.hq_to_detection(hq_x, hq_y)
                        
                        collectibles.append(Collectible(
                            x=detection_x, y=detection_y,
                            hq_x=hq_x, hq_y=hq_y,
                            lat=lat, lng=lng,
                            type=category,
                            name=item.get('text', 'unknown'),
                            category=category,
                            tool=item.get('tool', 0),
                            height=item.get('height', 0)
                        ))
            
            print(f"Loaded {len(collectibles)} collectibles")
            return collectibles
        except Exception as e:
            print(f"Failed to load collectibles: {e}")
            return []
    
    @staticmethod
    def _get_active_cycles():
        """Get today's active cycles"""
        try:
            response = requests.get(
                EXTERNAL_URLS.ROPKE_CYCLES_API,
                timeout=COLLECTIBLES.API_TIMEOUT_SECONDS
            )
            cycles_data = response.json()
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            for entry in cycles_data:
                if entry.get('date') == today:
                    return entry
        except:
            pass
        return {}
