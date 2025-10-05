# Collection Tracker Accordion Update

## Changes Made

### 1. Accordion Behavior
- Only one collection/set can be open at a time
- Clicking a set closes all others and opens the clicked one
- Clicking an already-open set closes it

### 2. F5 Hotkey Added
- F5 now toggles the entire collection tracker (show/hide)
- Hotkey hint "F5" shown in title bar
- Smooth collapse animation to width: 0

### 3. Fixed Hitboxes
- Item hitboxes now match the full hover container size
- Increased padding: 8px 12px (was 3px 6px)
- Full 50% width for each item
- Better hover feedback

### 4. Fixed Margins/Padding
- Removed bottom padding from tracker-content
- Removed margin-bottom from tracker-set-item
- Increased set header padding: 12px (was 6px 3px)
- Items now extend edge-to-edge
- Removed gaps between items (gap: 0)

### 5. Visual Improvements
- Added borders between items for clarity
- Better hover states (20% opacity vs 15%)
- Consistent spacing throughout

## Files Modified

1. `frontend/index.html`:
   - Updated CSS for accordion behavior
   - Added hotkey hint styling
   - Fixed padding/margins
   - Improved hitbox sizes

2. `frontend/main.js`:
   - Added F5 global shortcut registration

3. `frontend/renderer.js`:
   - Implemented accordion logic (close all, open one)
   - Added toggle-tracker IPC handler

## Testing

Restart Electron overlay:
```bash
npm start
```

Expected behavior:
- Press F5: Tracker slides in/out
- Click a set: Opens that set, closes all others
- Click open set: Closes it
- Hover items: Full row highlights
- Click items: Toggle collected status

## Before/After

**Before**:
- Multiple sets could be open simultaneously
- Small hitboxes (hard to click items)
- Padding at bottom
- No hotkey to hide tracker
- Gaps between items

**After**:
- Only one set open at a time (accordion)
- Full-width hitboxes (easy to click)
- No bottom padding (extends to footer)
- F5 to toggle visibility
- Clean edge-to-edge items
