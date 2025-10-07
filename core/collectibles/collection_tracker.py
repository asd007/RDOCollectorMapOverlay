"""
Collection tracking system for RDO collectibles.

Manages:
- Collected item state (persistent)
- Set completion tracking
- Category visibility
- Collection statistics
"""

import json
from pathlib import Path
from typing import Dict, List, Set as PySet
from dataclasses import dataclass, field
from PySide6.QtCore import QObject, Signal, Property, Slot
from config.paths import CachePaths


@dataclass
class CollectionSet:
    """Represents a collectible set (e.g., Tarot Cards - Cups)"""
    name: str
    category: str
    icon: str  # SVG icon name (see qml/svg_icons.py)
    items: List[str] = field(default_factory=list)
    is_random: bool = False  # Random spawns vs guaranteed sets

    @property
    def total(self) -> int:
        return len(self.items)


class CollectionTracker(QObject):
    """
    Tracks collection progress across all collectibles.
    Exposes data to QML via Qt properties and signals.
    """

    # Signals for QML
    collectedChanged = Signal()
    visibilityChanged = Signal(str, bool)  # category, visible
    progressChanged = Signal()

    # Category configuration matching Electron implementation
    # Uses SVG icon names instead of emoji (see qml/svg_icons.py)
    CATEGORY_CONFIG = {
        'cups': {'icon': 'tarot_card', 'name': 'Cups', 'type': 'guaranteed'},
        'swords': {'icon': 'tarot_card', 'name': 'Swords', 'type': 'guaranteed'},
        'wands': {'icon': 'tarot_card', 'name': 'Wands', 'type': 'guaranteed'},
        'pentacles': {'icon': 'tarot_card', 'name': 'Pentacles', 'type': 'guaranteed'},
        'egg': {'icon': 'egg', 'name': 'Eggs', 'type': 'guaranteed'},
        'bottle': {'icon': 'bottle', 'name': 'Bottles', 'type': 'guaranteed'},
        'flower': {'icon': 'flower', 'name': 'Flowers', 'type': 'guaranteed'},
        'heirlooms': {'icon': 'crown', 'name': 'Heirlooms', 'type': 'guaranteed'},
        'arrowhead': {'icon': 'arrowhead', 'name': 'Arrowheads', 'type': 'random'},
        'coin': {'icon': 'coin', 'name': 'Coins', 'type': 'random'},
        'fossils': {'icon': 'fossil', 'name': 'Fossils', 'type': 'random'},
        # Jewelry categories - each type is separate (matching Electron)
        'ring': {'icon': 'ring', 'name': 'Rings', 'type': 'random'},
        'earring': {'icon': 'earring', 'name': 'Earrings', 'type': 'random'},
        'bracelet': {'icon': 'bracelet', 'name': 'Bracelets', 'type': 'random'},
        'necklace': {'icon': 'necklace', 'name': 'Necklaces', 'type': 'random'},
        'jewelry_random': {'icon': 'jewelry_random', 'name': 'Random Jewelry', 'type': 'random'}
    }

    def __init__(self):
        super().__init__()

        # Collected items (persistent): set_name -> set of item IDs
        self._collected: Dict[str, PySet[str]] = {}

        # Category visibility (persistent): category -> bool
        self._visibility: Dict[str, bool] = {}

        # Set expansion state (persistent): set_name -> bool
        self._expanded: Dict[str, bool] = {}

        # Collection sets organized by category
        self._sets: Dict[str, CollectionSet] = {}

        # Cache directory for persistence
        cache_paths = CachePaths()
        self._save_path = cache_paths.CACHE_DIR / "collection_tracker.json"

        # Load persisted state
        self._load_state()

    def initialize_from_collectibles(self, collectibles: List[Dict]):
        """
        Build collection sets from loaded collectibles.

        Args:
            collectibles: List of collectible dicts with keys: name, type, category
        """
        # Group items by category
        category_items: Dict[str, List[str]] = {}

        for item in collectibles:
            category = item.get('type', item.get('category', 'unknown'))
            item_name = item.get('name', 'Unknown')

            if category not in category_items:
                category_items[category] = []
            category_items[category].append(item_name)

        # Create CollectionSet objects
        self._sets.clear()
        for category, items in category_items.items():
            config = self.CATEGORY_CONFIG.get(category, {
                'icon': 'random',
                'name': category.title(),
                'type': 'unknown'
            })

            set_obj = CollectionSet(
                name=config['name'],
                category=category,
                icon=config['icon'],
                items=sorted(set(items)),  # Remove duplicates and sort
                is_random=config['type'] == 'random'
            )

            self._sets[category] = set_obj

            # Initialize empty collected set if not exists
            if category not in self._collected:
                self._collected[category] = set()

            # Initialize visibility (default: visible)
            if category not in self._visibility:
                self._visibility[category] = True

        print(f"[CollectionTracker] Initialized {len(self._sets)} sets")
        self.progressChanged.emit()

    @Slot(str, str)
    def toggle_collected(self, category: str, item_name: str):
        """Mark/unmark item as collected"""
        if category not in self._collected:
            self._collected[category] = set()

        if item_name in self._collected[category]:
            self._collected[category].remove(item_name)
        else:
            self._collected[category].add(item_name)

        self._save_state()
        self.collectedChanged.emit()
        self.progressChanged.emit()

    @Slot(str)
    def toggle_visibility(self, category: str):
        """Toggle category visibility on overlay"""
        current = self._visibility.get(category, True)
        self._visibility[category] = not current

        self._save_state()
        self.visibilityChanged.emit(category, not current)

    @Slot(str)
    def toggle_expanded(self, set_name: str):
        """
        Toggle set expansion in UI.
        True accordion: Only one set can be expanded per tab (sets vs random).
        """
        current = self._expanded.get(set_name, False)

        if current:
            # Clicking expanded set collapses it
            self._expanded[set_name] = False
        else:
            # Clicking collapsed set expands it and collapses others IN THE SAME TAB
            # Find which tab this set belongs to using the set object's is_random property
            clicked_set = self._sets.get(set_name)
            if not clicked_set:
                return  # Set not found, do nothing

            is_random = clicked_set.is_random

            # Collapse all sets in the same tab
            for key in list(self._expanded.keys()):
                key_set = self._sets.get(key)
                if key_set and key_set.is_random == is_random:  # Same tab
                    self._expanded[key] = False

            # Expand the clicked set
            self._expanded[set_name] = True

        self._save_state()

    def is_collected(self, category: str, item_name: str) -> bool:
        """Check if item is collected"""
        return item_name in self._collected.get(category, set())

    def is_visible(self, category: str) -> bool:
        """Check if category is visible on overlay"""
        return self._visibility.get(category, True)

    def is_expanded(self, set_name: str) -> bool:
        """Check if set is expanded in UI"""
        return self._expanded.get(set_name, False)

    def get_set_progress(self, category: str) -> tuple:
        """Get (collected, total) for a set"""
        set_obj = self._sets.get(category)
        if not set_obj:
            return (0, 0)

        collected = len(self._collected.get(category, set()))
        total = set_obj.total
        return (collected, total)

    def get_total_progress(self) -> tuple:
        """Get overall (collected, total) progress"""
        total_collected = sum(len(items) for items in self._collected.values())
        total_items = sum(s.total for s in self._sets.values())
        return (total_collected, total_items)

    def get_visible_collectibles(self, all_collectibles: List[Dict]) -> List[Dict]:
        """Filter collectibles based on visibility settings"""
        return [
            item for item in all_collectibles
            if self.is_visible(item.get('type', item.get('category', '')))
        ]

    def _load_state(self):
        """Load persisted state from disk"""
        if not self._save_path.exists():
            return

        try:
            with open(self._save_path, 'r') as f:
                data = json.load(f)

            # Convert lists back to sets
            self._collected = {
                category: set(items)
                for category, items in data.get('collected', {}).items()
            }
            self._visibility = data.get('visibility', {})
            self._expanded = data.get('expanded', {})

            print(f"[CollectionTracker] Loaded state from {self._save_path}")
        except Exception as e:
            print(f"[CollectionTracker] Failed to load state: {e}")

    def _save_state(self):
        """Save state to disk"""
        try:
            # Ensure cache directory exists
            self._save_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert sets to lists for JSON serialization
            data = {
                'collected': {
                    category: list(items)
                    for category, items in self._collected.items()
                },
                'visibility': self._visibility,
                'expanded': self._expanded
            }

            with open(self._save_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CollectionTracker] Failed to save state: {e}")

    # Qt Properties for QML binding
    @Property(int, notify=progressChanged)
    def totalCollected(self):
        """Total collected items across all sets"""
        return sum(len(items) for items in self._collected.values())

    @Property(int, notify=progressChanged)
    def totalItems(self):
        """Total items across all sets"""
        return sum(s.total for s in self._sets.values())

    @Property(int, notify=progressChanged)
    def completionPercent(self):
        """Completion percentage"""
        if self.totalItems == 0:
            return 0
        return int((self.totalCollected / self.totalItems) * 100)
