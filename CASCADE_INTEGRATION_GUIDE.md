# Cascade Scale Matcher - Integration Guide

## Overview

The `CascadeScaleMatcher` provides flexible multi-scale matching with quality-based fallback, achieving **1.86-2.11× speedup** over baseline with 80-100% accuracy.

## Performance Results

| Configuration | Mean Time | Speedup | Success Rate |
|--------------|-----------|---------|--------------|
| **Baseline (50% only)** | 118ms | 1.0× | 100% |
| **Default Cascade** | 64ms | **1.86×** | 80% |
| **Aggressive Cascade** | 56ms | **2.11×** | 80% |
| **Custom Cascade (100% fallback)** | 84ms | 1.40× | **100%** |

## Quick Start

### Option 1: Default Cascade (Recommended)

```python
from matching.cascade_scale_matcher import create_cascade_matcher

# Create cascade matcher (25% -> 50%)
cascade_matcher = create_cascade_matcher(
    detection_map,
    cascade_type='default',
    verbose=False
)

# Match
result = cascade_matcher.match(screenshot_preprocessed)

if result and result['success']:
    # Access cascade info
    cascade_info = result['cascade_info']
    print(f"Used level: {cascade_info['final_level']}")
    print(f"Levels tried: {len(cascade_info['levels_tried'])}")
```

### Option 2: Aggressive Cascade (Maximum Speed)

```python
cascade_matcher = create_cascade_matcher(
    detection_map,
    cascade_type='aggressive',  # 12.5% -> 25% -> 50%
    verbose=False
)
```

### Option 3: Custom Cascade (Full Control)

```python
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching.simple_matcher import SimpleMatcher

# Create base matcher
base_matcher = SimpleMatcher(
    max_features=0,
    ratio_test_threshold=0.75,
    min_inliers=5,
    min_inlier_ratio=0.5,
    ransac_threshold=5.0,
    use_spatial_distribution=True,
    spatial_grid_size=50,
    max_screenshot_features=300
)
base_matcher.compute_reference_features(detection_map)

# Define custom cascade levels
cascade_levels = [
    ScaleConfig(
        scale=0.125,
        max_features=38,
        min_confidence=0.95,
        min_inliers=15,
        name="Ultra-fast"
    ),
    ScaleConfig(
        scale=0.25,
        max_features=75,
        min_confidence=0.85,
        min_inliers=10,
        name="Fast"
    ),
    ScaleConfig(
        scale=0.5,
        max_features=150,
        min_confidence=0.75,
        min_inliers=8,
        name="Reliable"
    ),
    ScaleConfig(
        scale=1.0,
        max_features=300,
        min_confidence=0.0,  # Always accept (fallback)
        min_inliers=5,
        name="Full (fallback)"
    )
]

cascade_matcher = CascadeScaleMatcher(base_matcher, cascade_levels, verbose=False)
```

## Integration into API

### Update `app.py`

```python
from matching.cascade_scale_matcher import create_cascade_matcher

# Initialize cascade matcher instead of SimpleMatcher
print("Initializing cascade matcher...")
cascade_matcher = create_cascade_matcher(
    detection_map,
    cascade_type='default',  # or 'aggressive'
    verbose=False
)
```

### Update alignment endpoint

```python
@app.route('/align-with-screenshot', methods=['POST'])
def align_with_screenshot():
    # ... screenshot capture and preprocessing ...

    # Match using cascade
    match_start = time.time()
    result = cascade_matcher.match(screenshot_preprocessed)
    match_time = (time.time() - match_start) * 1000

    if not result or not result.get('success', False):
        return jsonify({
            'success': False,
            'error': 'Could not align screenshot'
        })

    # Extract cascade info for logging
    cascade_info = result.get('cascade_info', {})

    # ... collectible filtering and response ...

    return jsonify({
        'success': True,
        'map_x': result['map_x'],
        'map_y': result['map_y'],
        'collectibles': visible_collectibles,
        'timing': {
            'screenshot_ms': screenshot_time,
            'matching_ms': match_time,
            'cascade_level': cascade_info.get('final_level', 'unknown'),
            'levels_tried': len(cascade_info.get('levels_tried', []))
        }
    })
```

## Cascade Levels Explained

### Default Cascade (2 levels)

```
Level 1: Fast (25%)
  - Scale: 0.25 (480×216)
  - Features: 75
  - Min confidence: 0.8
  - Min inliers: 10
  - Expected time: ~8ms

Level 2: Reliable (50%) [FALLBACK]
  - Scale: 0.5 (960×432)
  - Features: 150
  - Min confidence: 0.0 (always accept)
  - Min inliers: 5
  - Expected time: ~42ms
```

**Usage pattern**: 73% of cases succeed at Level 1 (fast path), 27% fall back to Level 2.

### Aggressive Cascade (3 levels)

```
Level 1: Ultra-fast (12.5%)
  - Scale: 0.125 (240×108)
  - Features: 38
  - Min confidence: 0.9
  - Min inliers: 10
  - Expected time: ~5ms

Level 2: Fast (25%)
  - Scale: 0.25 (480×216)
  - Features: 75
  - Min confidence: 0.8
  - Min inliers: 10
  - Expected time: ~8ms

Level 3: Reliable (50%) [FALLBACK]
  - Scale: 0.5 (960×432)
  - Features: 150
  - Min confidence: 0.0 (always accept)
  - Min inliers: 5
  - Expected time: ~42ms
```

**Usage pattern**: More aggressive early exit, potentially faster for simple scenes.

## Tuning Parameters

### Scale Selection

- **0.125×**: Ultra-fast but may miss fine details (5ms)
- **0.25×**: Good balance for most cases (8ms)
- **0.5×**: High reliability, slower (42ms)
- **1.0×**: Full resolution fallback (140ms)

### Confidence Thresholds

- **0.95**: Very strict, only perfect matches
- **0.85**: Strict, high quality required
- **0.75**: Moderate, good quality
- **0.6**: Relaxed, accept most matches
- **0.0**: Always accept (use for fallback level)

### Min Inliers

- **15+**: Very strict, many matching points required
- **10**: Standard threshold
- **5**: Minimum viable match
- **3**: Too low, may produce false positives

## Monitoring Cascade Performance

Enable verbose mode to see cascade behavior:

```python
cascade_matcher = create_cascade_matcher(
    detection_map,
    cascade_type='default',
    verbose=True
)
```

Output example:
```
  Level 1/2 (Fast (25%)): 8.23ms, conf=0.856, inliers=23 - ACCEPTED
```

Or check cascade_info in result:

```python
result = cascade_matcher.match(screenshot_preprocessed)
if result and result['success']:
    info = result['cascade_info']
    print(f"Final level: {info['final_level']}")
    print(f"Total time: {info['total_time_ms']:.2f}ms")
    print(f"Levels tried: {len(info['levels_tried'])}")

    for level_info in info['levels_tried']:
        print(f"  {level_info['name']}: {level_info['time_ms']:.2f}ms, "
              f"accepted={level_info['accepted']}")
```

## Best Practices

1. **Start with default cascade** - Good balance of speed and accuracy
2. **Monitor cascade info** - Track which levels are being used
3. **Tune for your use case**:
   - More close-up screenshots → lower confidence thresholds work
   - More variation in scenes → higher confidence thresholds needed
4. **Always have a fallback level** with `min_confidence=0.0`
5. **Sort levels by speed** (smallest scale first) for optimal performance

## Fallback Behavior

If all levels fail (no match found), the cascade returns `None`. Ensure proper error handling:

```python
result = cascade_matcher.match(screenshot_preprocessed)

if not result or not result.get('success', False):
    # Handle failure
    return jsonify({
        'success': False,
        'error': 'No match found at any cascade level'
    })
```

## Performance Tips

1. **Preprocessing is shared** - Only done once, cascades through scales
2. **Early exit saves time** - Most matches succeed at first level
3. **Feature proportionality** - Reduce max_features proportionally to scale
4. **Quality thresholds** - Higher = faster (more early exits) but may fall back more

## Example: Progressive Enhancement

Start conservative, tune based on analytics:

```python
# Week 1: Conservative (100% success rate)
cascade = CascadeScaleMatcher.create_custom_cascade(
    base_matcher,
    [
        (0.25, 75, 0.9, 12, "Fast (strict)"),
        (0.5, 150, 0.75, 8, "Medium"),
        (1.0, 300, 0.0, 5, "Full (fallback)")
    ]
)

# Week 2: After monitoring - tune based on cascade_info
# If 90% succeed at first level, increase threshold:
cascade = CascadeScaleMatcher.create_custom_cascade(
    base_matcher,
    [
        (0.25, 75, 0.85, 10, "Fast (relaxed)"),  # Relaxed
        (0.5, 150, 0.0, 5, "Medium (fallback)")   # Remove full scale
    ]
)
```

---

## Summary

✅ **1.86-2.11× speedup** with cascade strategy
✅ **Flexible chaining** - add/remove/tune levels easily
✅ **Quality-based fallback** - automatic adaptation to content complexity
✅ **Drop-in replacement** - minimal code changes required
✅ **Detailed telemetry** - cascade_info for monitoring and tuning
