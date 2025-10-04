# Config Module

Configuration management for RDO Map Overlay.

## Purpose

Centralizes all application settings, file paths, and constants used throughout the system. Uses frozen dataclasses for type safety and immutability.

## Files

### `settings.py`
Main configuration file with all system parameters organized into frozen dataclasses:

- **MAP_DIMENSIONS**: HQ map size (21617×16785), detection scale (0.5), lat/lng bounds, calibration points
- **MATCHING**: Pyramid scales, feature counts, ratio test threshold (0.75), RANSAC parameters
- **PERFORMANCE**: Target matching time (100ms), threading settings, caching flags
- **COLLECTIBLES**: Category mappings for Joan Ropke API, request timeout (15s)
- **SERVER**: Flask host/port, CORS settings
- **SCREENSHOT**: Crop ratio (0.8 = top 80%), monitor index

### `paths.py`
File path management and external URLs:

- Data paths: Map file, cache directory, pyramids cache
- External URLs: Joan Ropke's API endpoints (items.json, cycles.json)
- Uses `pathlib.Path` for cross-platform compatibility

## Usage

```python
from config.settings import MATCHING, MAP_DIMENSIONS, PERFORMANCE
from config.paths import Paths

# Access settings
feature_count = MATCHING.PYRAMID_FEATURE_COUNTS[0]
detection_scale = MAP_DIMENSIONS.DETECTION_SCALE

# Access paths
map_file = Paths.MAP_FILE
cache_dir = Paths.CACHE_DIR
```

## Notes

- All settings are immutable (frozen dataclasses) to prevent accidental modification
- Detection scale (0.5) trades accuracy for speed - full HQ map would be too slow
- 80% crop excludes bottom UI elements (minimap) from matching
