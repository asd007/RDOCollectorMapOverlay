# Models Module

Data models and type definitions.

## Purpose

Defines data structures used throughout the application. Uses Python dataclasses for type safety and clean serialization.

## Files

### `collectible.py`
Collectible data model:

```python
@dataclass
class Collectible:
    """Represents a single collectible item from Joan Ropke's API."""

    # Identity
    text: str           # Item ID from Joan Ropke (e.g., "flower_agarita_1")
    category: str       # Category from API (e.g., "flower")

    # Coordinates (multiple spaces)
    lat: float          # LatLng space latitude (-144 to 0)
    lng: float          # LatLng space longitude (0 to 176)
    hq_x: float        # HQ map space X (0 to 21617)
    hq_y: float        # HQ map space Y (0 to 16785)
    detection_x: float # Detection space X (0 to 10808)
    detection_y: float # Detection space Y (0 to 8392)

    # Metadata
    type: str          # Mapped type (e.g., "flower_agarita")
    name: str          # Display name (e.g., "Desert Sage")
    tool: str          # Required tool ("shovel", "metal_detector", "none")
```

**Coordinate Spaces**:
- **LatLng**: Source coordinates from Joan Ropke API
- **HQ**: High-resolution map pixels (21617×16785)
- **Detection**: Downscaled map for matching (10808×8392 at 0.5× scale)
- **Screen**: User display coordinates (calculated at runtime, not stored)

**Type Mapping**:
Categories from API are mapped to specific types using `COLLECTIBLES.CATEGORY_MAPPINGS`:
```python
"flower_agarita" → "flower_agarita"
"flower_blood_flower" → "flower_blood_flower"
"coin" → "coin"
"card_tarot" → "card"
```

## Usage

```python
from models.collectible import Collectible

# Create from Joan Ropke API data
collectible = Collectible(
    text="flower_agarita_1",
    category="flower",
    lat=-82.5,
    lng=88.3,
    hq_x=10523.2,
    hq_y=8421.7,
    detection_x=5261.6,
    detection_y=4210.8,
    type="flower_agarita",
    name="Desert Sage",
    tool="none"
)

# Serialize to dict (for JSON response)
data = asdict(collectible)

# Access coordinates
print(f"Collectible at HQ: ({collectible.hq_x}, {collectible.hq_y})")
```

## Notes

- All coordinates are stored as floats to preserve precision
- Coordinate transforms happen once at load time (not per-frame)
- Screen coordinates are calculated on-demand in `api/state.py`
- Tool field used by frontend to show appropriate icon
