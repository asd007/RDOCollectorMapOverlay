# Collection Tracker - Full Row Clickable for Items

## Issue
Only the checkbox was clickable to toggle collected state, not the entire item row.

## Root Cause
`.tracker-item-checkbox` had `pointer-events: auto`, which meant clicking on it captured the event instead of letting it bubble to the parent container.

## Solution
Changed `.tracker-item-checkbox` and `.tracker-item-name` to have `pointer-events: none`, so all clicks bubble up to the parent `.tracker-item-compact` div.

## Implementation

**Before** (index.html:31):
```css
button, input, a, .tracker-set, .tracker-category, .tracker-item-compact,
.tracker-header, .tracker-tab, .tracker-eye-icon, .tracker-item-checkbox {
  pointer-events: auto;
  cursor: pointer;
}
```

**After** (index.html:30-40):
```css
button, input, a, .tracker-set, .tracker-category, .tracker-item-compact,
.tracker-header, .tracker-tab, .tracker-eye-icon {
  pointer-events: auto;
  cursor: pointer;
}

/* Checkbox and item name should not capture events - let parent handle */
.tracker-item-checkbox, .tracker-item-name {
  pointer-events: none;
  cursor: pointer;
}
```

## How It Works

### HTML Structure (renderer.js:2322-2329)
```html
<div class="tracker-item-compact" onclick="toggleTrackerCollected(...)">
  <span class="tracker-item-checkbox">✓</span>
  <span class="tracker-item-name">Item Name</span>
</div>
```

### Event Flow
1. User clicks anywhere on the row
2. Child spans have `pointer-events: none`
3. Click event bubbles to parent `.tracker-item-compact`
4. Parent's `onclick` handler fires
5. Item's collected state toggles

### Visual Feedback
- Entire row has hover effect (background change)
- Cursor shows pointer over entire row
- Full 50% width is clickable

## Files Modified

- `frontend/index.html` (lines 30-40)

## Testing

Restart Electron:
```bash
npm start
```

Expected behavior:
1. Open any collection set
2. Hover over an item → entire row highlights
3. Click anywhere on the row → collected state toggles
4. Checkbox changes: ○ → ✓ or ✓ → ○
5. Item name strikes through when collected

The entire hover area is now the clickable toggle! ✓
