"""Collectibles loading from Ropke API"""

import requests
from datetime import datetime, timezone
from typing import List
from models import Collectible
from core.coordinate_transform import CoordinateTransform
from config import COLLECTIBLES, EXTERNAL_URLS


class CollectiblesLoader:
    """Loads collectibles from Joan Ropke's API"""

    # Cache for language data
    _lang_data_cache = None

    @staticmethod
    def _load_lang_data():
        """Load language data (hints and video links) from en.json"""
        if CollectiblesLoader._lang_data_cache is not None:
            return CollectiblesLoader._lang_data_cache

        try:
            response = requests.get(
                "https://raw.githubusercontent.com/jeanropke/RDR2CollectorsMap/refs/heads/master/langs/en.json",
                timeout=COLLECTIBLES.API_TIMEOUT_SECONDS
            )
            CollectiblesLoader._lang_data_cache = response.json()
            print(f"Loaded language data with {len(CollectiblesLoader._lang_data_cache)} entries")
            return CollectiblesLoader._lang_data_cache
        except Exception as e:
            print(f"Failed to load language data: {e}")
            return {}

    @staticmethod
    def _get_hint_and_video(item_text: str, cycle: str, video_url: str, lang_data: dict) -> tuple:
        """Get hint and video link for a collectible item"""
        # Video is already in items.json
        video = video_url

        # Help text pattern: {item_text}_{cycle}.desc
        hint_key = f"{item_text}_{cycle}.desc"
        hint = lang_data.get(hint_key, '')

        return hint, video

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

            # Load language data for hints and videos
            lang_data = CollectiblesLoader._load_lang_data()

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
                        item_text = item.get('text', 'unknown')
                        video_url = item.get('video', '')

                        # Get hint and video for this item
                        hint, video = CollectiblesLoader._get_hint_and_video(item_text, cycle, video_url, lang_data)

                        hq_x, hq_y = coord_transform.latlng_to_hq(lat, lng)
                        detection_x, detection_y = coord_transform.hq_to_detection(hq_x, hq_y)

                        collectibles.append(Collectible(
                            x=detection_x, y=detection_y,
                            hq_x=hq_x, hq_y=hq_y,
                            lat=lat, lng=lng,
                            type=category,
                            name=item_text,
                            category=category,
                            tool=item.get('tool', 0),
                            height=item.get('height', 0),
                            help=hint,
                            video=video
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
