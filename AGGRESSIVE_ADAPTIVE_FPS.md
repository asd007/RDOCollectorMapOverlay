# Aggressive Adaptive FPS Strategy

## Changes Made

### 1. Removed Maximum FPS Cap
**Before**: Capped at 30 FPS
**After**: No cap - system finds its natural limit based on hardware

```python
self.max_fps = None  # No maximum - let system find its limit
```

### 2. More Aggressive Scaling
**Before**: +20% increase when utilization < 50%
**After**:
- **+50%** increase when utilization < 60% (fast ramp-up)
- **+20%** increase when utilization 60-75% (fine-tuning)
- **No change** when utilization 75-85% (sweet spot)
- **-30%** decrease when utilization > 85% (back off)

### 3. Faster Adaptation Interval
**Before**: Adapt every 10 frames
**After**: Adapt every 3 frames (3.3× faster response)

### 4. Smaller Processing Window
**Before**: Track last 20 processing times (P95)
**After**: Track last 10 processing times (P90, more responsive)

## Performance Comparison

### Example: 12ms Processing Time

**Old Strategy (Conservative)**:
- Adapts every 10 frames
- Increases by 20% each time
- Caps at 30 FPS
- **Result**: Takes 100 frames to reach 30 FPS (capped)

**New Strategy (Aggressive)**:
- Adapts every 3 frames
- Increases by 50% when underutilized
- No cap
- **Result**: Takes 24 frames to reach 68 FPS (optimal)

**Improvement**: 4.2× faster to optimal, 2.3× higher FPS

## FPS Progression Example

```
Frame 3:   5.0 → 7.5 FPS   (+50%, utilization 6%)
Frame 6:   7.5 → 11.2 FPS  (+50%, utilization 9%)
Frame 9:   11.2 → 16.9 FPS (+50%, utilization 14%)
Frame 12:  16.9 → 25.3 FPS (+50%, utilization 20%)
Frame 15:  25.3 → 38.0 FPS (+50%, utilization 30%)
Frame 18:  38.0 → 57.0 FPS (+50%, utilization 46%)
Frame 21:  57.0 → 68.3 FPS (+20%, utilization 68%)
Frame 24:  68.3 FPS       (OPTIMAL - utilization 82%)
```

System stabilizes at **68 FPS** with **82% utilization** (sweet spot).

## Expected Behavior

### Fast Systems (6-10ms processing):
- Will quickly ramp to 80-100+ FPS
- Lag reduced to ~12-15ms
- Near real-time tracking

### Medium Systems (12-15ms processing):
- Will ramp to 50-70 FPS
- Lag reduced to ~15-20ms
- Very smooth tracking

### Slow Systems (20-30ms processing):
- Will ramp to 25-40 FPS
- Lag reduced to ~25-40ms
- Still much better than 200ms

### Very Slow Systems (>40ms processing):
- Will stay at minimum 5 FPS
- Adaptive system backs off automatically
- No worse than before

## Monitoring

Check `/profiling-stats` for new fields:

```json
{
  "adaptive_fps": {
    "enabled": true,
    "current_target_fps": 68.3,
    "min_fps": 5.0,
    "max_fps": null,  // Unlimited
    "utilization_pct": 82.0,
    "adaptation_interval": 3,
    "frames_until_next_adapt": 1
  }
}
```

Watch console for rapid adaptation:
```
[Adaptive FPS] 5.0 -> 7.5 FPS (processing: 12ms, utilization: 6%)
[Adaptive FPS] 7.5 -> 11.2 FPS (processing: 12ms, utilization: 9%)
[Adaptive FPS] 11.2 -> 16.9 FPS (processing: 12ms, utilization: 14%)
...
[Adaptive FPS] 57.0 -> 68.3 FPS (processing: 12ms, utilization: 68%)
```

## Safety Mechanisms

1. **Minimum FPS**: Never goes below 5 FPS
2. **Automatic back-off**: If utilization > 85%, reduces FPS by 30%
3. **Gradual increase**: Still uses 20% increments when close to limit (60-75% utilization)
4. **Outlier filtering**: Uses P90 instead of P95 for faster response

## Edge Cases

### System Stalls (100% utilization):
- Reduces FPS by 30% every 3 frames
- Quickly finds stable rate
- Example: 100 → 70 → 49 → 34 FPS in 9 frames

### Sudden Performance Drop:
- Detects high utilization within 3 frames
- Backs off immediately
- Re-adapts when performance recovers

### Oscillation Prevention:
- Sweet spot range: 75-85% utilization
- No changes in this range
- Prevents flickering between FPS values

## Configuration

If you want to limit maximum FPS:

```python
# In continuous_capture.py:154
self.max_fps = 60  # Cap at 60 FPS instead of unlimited
```

If you want slower adaptation:

```python
# In continuous_capture.py:156
self.fps_adaptation_interval = 5  # Every 5 frames instead of 3
```

## Testing

Restart backend and watch console:

```bash
python app.py
```

Expected output (fast system):
```
[Adaptive FPS] 5.0 -> 7.5 FPS (processing: 12ms, utilization: 6%)
[Adaptive FPS] 7.5 -> 11.2 FPS (processing: 12ms, utilization: 9%)
[Adaptive FPS] 11.2 -> 16.9 FPS (processing: 12ms, utilization: 14%)
[Adaptive FPS] 16.9 -> 25.3 FPS (processing: 12ms, utilization: 20%)
[Adaptive FPS] 25.3 -> 38.0 FPS (processing: 12ms, utilization: 30%)
[Adaptive FPS] 38.0 -> 57.0 FPS (processing: 12ms, utilization: 46%)
[Adaptive FPS] 57.0 -> 68.3 FPS (processing: 12ms, utilization: 68%)
```

Total time to optimal: **~1.2 seconds** (24 frames at initial 5 FPS avg)

Compare to old: **~20 seconds** (100 frames at 5 FPS)

**16× faster ramp-up to optimal FPS!**
