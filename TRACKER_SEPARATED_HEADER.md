# Collection Tracker - Separated Header and Accordion

## Changes Made

### Problem
Header was inside the accordion container, causing issues:
- Clicking anywhere in a set/collection row would collapse the accordion
- Header would collapse along with the body when toggling

### Solution
Completely separated header and accordion body into two independent elements.

## New Structure

### Before
```
#cycle-tracker (container)
  ├── .tracker-header (inside container)
  └── .tracker-body
      ├── .tracker-tabs
      ├── .tracker-content
      └── .tracker-footer
```

### After
```
.tracker-header (standalone, always visible)

#cycle-tracker (accordion body only)
  ├── .tracker-tabs
  ├── .tracker-content
  └── .tracker-footer
```

## Implementation

### 1. HTML Changes (index.html)

**Header** - Standalone element:
- Position: `fixed` at `top: 0, left: 0`
- Width: `420px`
- Z-index: `10002` (above body)
- Always visible

**Body** - Separate accordion:
- Position: `fixed` at `top: 68px, left: 0`
- Height: `calc(100vh - 68px)` (fills remaining height)
- Z-index: `10001` (below header)
- `display: none` when `.collapsed`

### 2. CSS Changes

```css
/* Header - Always visible */
.tracker-header {
  position: fixed;
  top: 0;
  left: 0;
  width: 420px;
  z-index: 10002;
}

/* Body - Collapsible */
#cycle-tracker {
  position: fixed;
  top: 68px;
  left: 0;
  width: 420px;
  height: calc(100vh - 68px);
  z-index: 10001;
}

#cycle-tracker.collapsed {
  display: none;
}
```

### 3. Click-Through Detection (renderer.js)

Updated to check header and body separately:

```javascript
function isCursorOverTracker(x, y) {
  // Check header (always visible)
  const header = document.getElementById('tracker-header-clickable');
  if (header) {
    const headerRect = header.getBoundingClientRect();
    if (cursor in headerRect) return true;
  }

  // Check body (only if not collapsed)
  const tracker = document.getElementById('cycle-tracker');
  if (tracker && !tracker.classList.contains('collapsed')) {
    if (cursor in trackerRect) return true;
  }

  return false;
}
```

## Behavior

### F5 or Header Click
- **Action**: Toggles `collapsed` class on `#cycle-tracker`
- **Result**: Body disappears/appears, header stays

### Clicking Collection Set Row
- **Before**: Entire accordion would toggle
- **After**: Only the clicked set expands (accordion behavior)

### Click-Through
- **Header area**: Always disables click-through
- **Body area when expanded**: Disables click-through
- **Body area when collapsed**: Click-through enabled (clicks game)

## Files Modified

1. `frontend/index.html`:
   - Moved `.tracker-header` outside `#cycle-tracker`
   - Updated CSS positioning and z-indexes
   - Simplified collapse: `display: none`

2. `frontend/renderer.js`:
   - Updated `isCursorOverTracker()` for separate elements

## Testing

Restart Electron:
```bash
npm start
```

Expected behavior:
1. **Header always visible** at top-left
2. **Press F5**: Body disappears, header stays
3. **Press F5 again**: Body reappears
4. **Click header**: Same as F5 (toggles body)
5. **Click set row**: Expands that set only (accordion)
6. **Click item row**: Toggles collected state
7. **Hover header**: Click-through disabled
8. **Hover body when collapsed**: Click-through enabled (can click game)

Clean separation of header and accordion! ✓
