# Core Module

Core backend functionality for map processing, collectible loading, and system services.

## Purpose

Handles fundamental operations: coordinate transformations, map loading, collectible data fetching, screenshot capture, and port management.

## Files

### `coordinate_transform.py`
Transforms between coordinate systems:

- **LatLng ↔ HQ Space**: Converts Joan Ropke's geographic coordinates (lat: -144 to 0, lng: 0 to 176) to HQ map pixels (21617×16785)
- **Linear Transform**: Uses calibrated points from config for accurate mapping
- **Functions**: `latlng_to_hq()`, `hq_to_latlng()`, `latlngs_to_hq_batch()` (vectorized numpy)

### `map_loader.py`
Loads and caches the reference map:

- **MapLoader class**: Singleton for map loading/caching
- **Preprocessing**: Converts to grayscale, downscales to detection scale (0.5×)
- **Caching**: Saves preprocessed map to `data/cache/map_preprocessed_v*.pkl`
- **Memory management**: ~500MB for full HQ map, ~125MB for detection scale

### `collectibles_loader.py`
Fetches collectible data from Joan Ropke's API:

- **CollectiblesLoader class**: Downloads items.json and cycles.json
- **Daily cycles**: Identifies active collectibles for current game day
- **Coordinate conversion**: Transforms LatLng → HQ → Detection for matching
- **Functions**: `load_collectibles()` returns list of Collectible objects

### `continuous_capture.py`
Background screenshot capture service:

- **ContinuousCapture class**: Runs capture loop at 5fps
- **Windows Graphics Capture API**: Clean game window capture (no overlays)
- **Threading**: Separate thread for non-blocking captures
- **Functions**: `start()`, `stop()`, `get_latest_frame()`

### `map_detector.py`
High-level position detection wrapper:

- **MapDetector class**: Coordinates matching and viewport calculation
- **Integration**: Combines cascade matcher + coordinate transforms
- **Functions**: `detect_position()` returns viewport + collectibles

### `port_manager.py`
Dynamic port allocation for packaged app:

- **find_available_port()**: Finds free port starting from 5000
- **write_port_file()**: Writes port to temp file for Electron to read
- **read_port_file()**: Reads port from temp file
- **Purpose**: Prevents port conflicts when multiple instances run

### `image_preprocessing.py`
Image enhancement for better feature matching:

- **Posterization**: Reduces color levels for cleaner edges
- **CLAHE**: Contrast Limited Adaptive Histogram Equalization for terrain details
- **Custom LUT**: Lookup table for edge enhancement
- **Functions**: `preprocess_for_matching()` applies full pipeline

## Usage

```python
from core.map_loader import MapLoader
from core.collectibles_loader import CollectiblesLoader
from core.continuous_capture import ContinuousCapture

# Load map
map_loader = MapLoader()
hq_map, detection_map = map_loader.load()

# Load collectibles
collectibles = CollectiblesLoader.load_collectibles()

# Start continuous capture
capture = ContinuousCapture()
capture.start()
frame = capture.get_latest_frame()
```

## Notes

- All coordinate transforms preserve precision (use float64)
- Map caching significantly speeds up startup (seconds vs minutes)
- Continuous capture runs at 5fps to balance performance and responsiveness
- Port manager uses Windows temp directory for cross-process communication
