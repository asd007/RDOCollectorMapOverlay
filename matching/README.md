# Matching Module

Computer vision algorithms for viewport detection and position tracking.

## Purpose

Implements multi-scale feature matching to locate the player's viewport on the reference map. Uses AKAZE features with cascade pyramid approach for speed/accuracy balance.

## Files

### `cascade_scale_matcher.py`
Main matching algorithm using multi-scale pyramid:

- **CascadeScaleMatcher class**: Tries multiple scales (25% → 50% → 70%) with early exit
- **Feature pyramids**: Pre-computed AKAZE features at each scale (cached to disk)
- **Smart scale selection**: Quick tracking mode tries last successful scale first
- **ROI optimization**: When tracking, only searches near last position
- **Functions**: `match(screenshot)` returns viewport position + confidence

**Algorithm Flow**:
1. Check if tracking (has recent confident match)
2. If tracking: Try last scale with ROI first
3. If not tracking: Try all scales from coarse to fine
4. For each scale: Extract features, match with BFMatcher, RANSAC homography
5. Early exit at confidence >0.8 to save time

### `simple_matcher.py`
Basic single-scale matcher (legacy/fallback):

- **SimpleMatcher class**: Single-scale AKAZE matching without pyramid
- **Slower but more accurate**: Uses 50000 features for maximum precision
- **No ROI optimization**: Searches entire map
- **Functions**: `match(screenshot)` returns viewport position + confidence

### `spatial_feature_selector.py`
Validates feature distribution for robust matching:

- **SpatialFeatureSelector class**: Ensures features are well-distributed
- **Grid-based selection**: Divides image into grid, selects features from each cell
- **Prevents clustering**: Avoids concentration of features in small areas
- **Functions**: `select_spatial_features()` returns filtered feature indices

### `scale_predictor.py`
ML-based scale prediction for faster matching:

- **ScalePredictor class**: Predicts likely map scale from screenshot
- **Heuristics**: Uses edge density, texture patterns, UI elements
- **Purpose**: Reduces scales to try in cascade matcher
- **Status**: Experimental, not yet integrated into main pipeline

### `viewport_tracker.py`
Position tracking with motion prediction:

- **ViewportTracker class**: Tracks position over time with Kalman filter
- **Motion prediction**: Estimates next position based on velocity
- **Confidence tracking**: Maintains confidence scores over time
- **Functions**: `update()`, `predict()`, `get_position()`
- **Status**: Experimental, not yet integrated into main pipeline

## Usage

```python
from matching.cascade_scale_matcher import CascadeScaleMatcher
from core.map_loader import MapLoader

# Initialize matcher
map_loader = MapLoader()
detection_map = map_loader.load()[1]
matcher = CascadeScaleMatcher(detection_map)

# Match screenshot
screenshot = capture_screen()
result = matcher.match(screenshot)

if result['success']:
    viewport = result['viewport']  # (x, y, width, height) in detection space
    confidence = result['confidence']  # 0.0 - 1.0
```

## Performance

**Target**: <100ms per match
**Current**: ~200ms median (functional but not real-time)

**Breakdown**:
- Feature extraction: ~50ms
- Feature matching: ~100ms
- RANSAC homography: ~30ms
- Overhead: ~20ms

**Optimization strategies**:
- Cascade pyramid: Try coarse scales first (fewer features = faster)
- ROI search: When tracking, only search near last position
- Early exit: Stop at confidence >0.8
- Cached pyramids: Pre-compute features once, reuse across matches

## Notes

- AKAZE features are rotation-invariant but RDO minimap doesn't rotate (2D only)
- Cascade matcher trades accuracy for speed vs simple matcher (50000 features)
- Spatial feature selector helps prevent false matches in repetitive terrain
- Scale predictor and viewport tracker are experimental (not production-ready)
