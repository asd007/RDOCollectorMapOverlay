# Adaptive FPS and Frame Skipping - Implementation Summary

## Problem Identified

The collectibles were **positionally correct** but **lagged behind camera movement** during continuous panning. Root cause analysis revealed:

1. **Fixed 5 FPS artificial rate limiting** - Backend waited 200ms between frames even when processing finished faster
2. **No frame skipping** - When processing fell behind, lag accumulated instead of skipping to current time
3. **Fundamental latency pipeline**: `capture (200ms) + processing (30-50ms) + network (10-50ms) = 240-300ms total lag`

## Solution Implemented

### 1. Adaptive FPS Target (Lines 216-258 in continuous_capture.py)

**Strategy:**
- Monitor P95 processing time over last 20 frames
- Calculate utilization: `processing_time / frame_budget`
- Adjust FPS every 10 frames:
  - **Utilization < 50%**: Increase FPS by 20% (system can go faster)
  - **Utilization > 80%**: Decrease FPS by 20% (system struggling)
  - **50-80% utilization**: No change (sweet spot)
- Clamp between 5 FPS (min) and 30 FPS (max)

**Example:**
```
Processing: 30ms
Frame budget: 200ms (5 FPS)
Utilization: 15% → Increase to 6 FPS

After adaptation:
Frame budget: 167ms (6 FPS)
Utilization: 18% → Increase to 7.2 FPS

Eventually stabilizes at ~25-30 FPS for 30ms processing
```

### 2. Intelligent Frame Skipping (Lines 305-317 in continuous_capture.py)

**Strategy:**
- If `time_until_next_frame < -frame_interval`: We're more than 1 frame behind
- Skip ahead to current time instead of trying to catch up
- Track skipped frames in stats

**Benefits:**
- Prevents accumulating lag when processing occasionally spikes
- Always captures "latest" frame, not stale frames from the past

### 3. Faster Wake-up Loop (Line 320)

**Changed:**
- Old: `sleep(0.01)` (10ms between checks)
- New: `sleep(0.001)` (1ms between checks)

**Benefit:**
- More responsive to frame timing (especially important at 30 FPS = 33ms intervals)

## Expected Performance Improvement

### Before (Fixed 5 FPS):
```
Frame timing:    0ms   200ms   400ms   600ms   800ms
Camera position: A  →  B    →  C    →  D    →  E
Collectibles:    A      B       C       D       E
Lag:            0ms   200ms   200ms   200ms   200ms
```

### After (Adaptive ~20-30 FPS):
```
Frame timing:    0ms   40ms   80ms   120ms   160ms   200ms
Camera position: A  →  B   →  C   →  D    →  E    →  F
Collectibles:    A     B      C      D       E       F
Lag:            0ms   40ms   40ms   40ms    40ms    40ms
```

**Lag reduction: 200ms → 40ms (5x improvement)**

## Monitoring Adaptive FPS

### Via API Endpoint: `/profiling-stats`

New fields added:
```json
{
  "adaptive_fps": {
    "enabled": true,
    "current_target_fps": 25.3,
    "min_fps": 5,
    "max_fps": 30,
    "p95_processing_ms": 28.5,
    "mean_processing_ms": 24.2,
    "utilization_pct": 61.3,
    "frames_until_next_adapt": 3
  }
}
```

### Console Output (when FPS changes):
```
[Adaptive FPS] 5.0 -> 6.0 FPS (processing: 30.2ms, utilization: 15%)
[Adaptive FPS] 6.0 -> 7.2 FPS (processing: 28.1ms, utilization: 17%)
[Adaptive FPS] 7.2 -> 8.6 FPS (processing: 26.5ms, utilization: 19%)
...
[Adaptive FPS] 25.0 -> 25.0 FPS (processing: 29.8ms, utilization: 75%)
```

## Testing Recommendations

1. **Start RDO and open map**
2. **Monitor `/profiling-stats` endpoint** to see FPS adaptation in real-time
3. **Continuously pan camera** for 10-20 seconds
4. **Observe:**
   - Target FPS should increase from 5 → 20-30 FPS
   - Collectibles should track camera more closely
   - Lag should reduce from ~200ms to ~40-50ms

5. **Check console for adaptation messages:**
   ```bash
   python app.py
   # Look for "[Adaptive FPS]" messages
   ```

## Potential Issues

1. **High CPU systems**: May hit max 30 FPS quickly, could increase `max_fps` to 60
2. **Low-end systems**: May struggle at higher FPS, adaptive system will reduce back to 5 FPS
3. **Variable processing times**: Large spikes may cause temporary FPS drops, system will recover

## Configuration Knobs

In `continuous_capture.py` `__init__`:

```python
self.min_fps = 5              # Minimum FPS when slow
self.max_fps = 30             # Maximum FPS when fast
self.fps_adaptation_interval = 10  # Recalculate every N frames
```

Adjust these values based on testing:
- **Increase max_fps** for high-end systems (e.g., 60)
- **Decrease fps_adaptation_interval** for faster adaptation (e.g., 5)
- **Increase min_fps** if minimum quality threshold needed (e.g., 10)

## Next Steps

1. Test with actual gameplay during continuous panning
2. Monitor drift tracking to verify accuracy isn't affected
3. Consider increasing max_fps to 60 if system can handle it
4. Evaluate if WebSocket transmission latency is now the bottleneck
