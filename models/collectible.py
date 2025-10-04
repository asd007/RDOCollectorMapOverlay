"""Data models for collectibles"""

from dataclasses import dataclass
from enum import Enum


class CollectibleTool(Enum):
    """Tools required for collectibles"""
    NONE = 0
    SHOVEL = 1
    METAL_DETECTOR = 2
    BOTH = 3


@dataclass
class Collectible:
    """Represents a collectible item in the game world"""
    x: int
    y: int
    hq_x: int
    hq_y: int
    lat: float
    lng: float
    type: str
    name: str
    category: str
    tool: int = 0
    height: int = 0
    help: str = ''
    video: str = ''

    def __hash__(self):
        return hash((self.x, self.y, self.type, self.name))
