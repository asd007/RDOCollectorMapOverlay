# Collection Tracker - Header Always Visible

## Changes Made

### Problem
When pressing F5 to collapse the tracker, the entire tracker (including header) disappeared.

### Solution
Header now stays visible when collapsed - only the body/footer hide.

## Implementation

### 1. Changed Collapse Behavior (index.html)

**Before**:
```css
#cycle-tracker.collapsed {
  width: 0;
  border-right: none;
}
```

**After**:
```css
#cycle-tracker.collapsed .tracker-body {
  display: none;
}

#cycle-tracker.collapsed .tracker-footer {
  display: none;
}
```

### 2. Restored Tracker Styling
- Tracker stays 420px wide always
- Background and border always visible
- Only body and footer hide when collapsed

### 3. Updated Click-Through Detection (renderer.js)

**Smart detection**:
- When **expanded**: Entire 420px width is interactable
- When **collapsed**: Only header is interactable
- Below header when collapsed: Click-through enabled (can click game)

```javascript
// If collapsed, only the header is interactable
if (tracker.classList.contains('collapsed')) {
  const header = document.getElementById('tracker-header-clickable');
  if (header) {
    const headerRect = header.getBoundingClientRect();
    return x >= headerRect.left &&
           x <= headerRect.right &&
           y >= headerRect.top &&
           y <= headerRect.bottom;
  }
  return false;
}
```

## Behavior

### Expanded (Default after F5)
```
+-------------------+
| Header (F5)       | <- Always visible
+-------------------+
| Tabs              |
| Collections...    |
| ...               |
| Footer            |
+-------------------+
```
- Full 420px width
- All content visible
- Entire area interactable

### Collapsed (After F5)
```
+-------------------+
| Header (F5)       | <- Stays visible, clickable
+-------------------+
```
- Still 420px wide (for header)
- Only header visible
- Body/footer hidden
- Only header interactable (below is click-through)

## Files Modified

1. `frontend/index.html`:
   - Removed width: 0 collapse
   - Added display: none for body/footer when collapsed
   - Restored background/border to tracker

2. `frontend/renderer.js`:
   - Updated `isCursorOverTracker()` for smart detection
   - Header-only hitbox when collapsed

## Testing

Restart Electron:
```bash
npm start
```

Expected:
1. **Press F5**: Body/footer hide, header stays
2. **Hover header when collapsed**: Click-through disabled (can click header)
3. **Hover below header when collapsed**: Click-through enabled (can click game)
4. **Press F5 again**: Body/footer reappear
5. **Click header to toggle entire tracker**: Works in both states

Perfect accordion behavior with persistent header! ✓
