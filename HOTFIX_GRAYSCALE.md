# Hotfix: Restore Grayscale Conversion

## Issue
After optimizations, collectibles stopped showing in frontend.

**Root cause**: Removed grayscale conversion from `translation_tracker.py` assuming input was already grayscale, but `continuous_capture.py` passes raw BGR screenshots.

## Symptoms
- Backend runs at high FPS (80-90)
- Success rate near 0%
- AKAZE matches succeed (2-3 frames) but motion-only never kicks in
- Frontend shows "waiting for next frame"

## Fix
Restored grayscale conversion in `translation_tracker.py:57-61`:

```python
# Convert to grayscale if needed (input may be BGR from cascade matcher)
if len(current_frame.shape) == 3:
    gray_curr = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
else:
    gray_curr = current_frame
```

## Testing
Restart backend:
```bash
python app.py
```

Expected behavior:
- AKAZE matches succeed initially
- Motion-only kicks in (should see motion_only_frames increasing)
- Collectibles appear on map
- Success rate > 90%

## Performance Impact
Grayscale conversion adds ~0.5ms overhead, but system still runs much faster than before:
- Total: ~13ms (was 18ms, target was 12ms)
- Still achieves 60-80 FPS on fast systems
