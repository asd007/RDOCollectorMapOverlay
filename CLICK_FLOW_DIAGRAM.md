# Click Flow Diagram - RDO Map Overlay

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER CLICKS MOUSE                        │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
        ┌───────────────────┐     ┌──────────────────┐
        │  Backend Observer │     │   DOM Events     │
        │   (pynput hook)   │     │  (when enabled)  │
        └───────────────────┘     └──────────────────┘
                    │                         │
                    │ Always sends            │ Only when
                    │ to frontend             │ click-through
                    │                         │ disabled
                    ▼                         ▼
        ┌───────────────────────────────────────────┐
        │     Frontend Renderer (renderer.js)       │
        │                                            │
        │  socket.on('mouse-clicked', (data) => {   │
        │    // Hit-test & route clicks             │
        │  })                                        │
        └───────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Hit Testing   │
                    │   Priority:     │
                    │   1. Video      │
                    │   2. Tooltip    │
                    │   3. Menu       │
                    │   4. Collectible│
                    │   5. Game       │
                    └─────────────────┘
```

---

## Click-Through States

### State 1: Click-Through ENABLED (Default)

```
┌─────────────────────────────────────────────────────────────┐
│                      Electron Window                         │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Transparent Overlay (click-through)       │    │
│  │                                                     │    │
│  │   Cursor NOT over UI → Clicks pass to game        │    │
│  │                                                     │    │
│  │   [Collectible]  ← Backend observes click         │    │
│  │                  → Hit-test finds collectible      │    │
│  │                  → Toggle collected status         │    │
│  │                  → Click ALSO passes to game ✅    │    │
│  │                                                     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    Red Dead Redemption 2 (receives ALL clicks)
```

### State 2: Click-Through DISABLED (Menu/Tooltip/Video Open)

```
┌─────────────────────────────────────────────────────────────┐
│                      Electron Window                         │
│  ┌────────────────────────────────────────────────────────┐│
│  │       Overlay (click-through DISABLED)                 ││
│  │                                                         ││
│  │  ┌──────────────┐  [Collectible] ← Still works!      ││
│  │  │ Tracker Menu │                 (backend observer)   ││
│  │  │ [✓] Item 1   │                                      ││
│  │  │ [ ] Item 2   │  Click collectible → toggles ✅      ││
│  │  │ [👁️] Show   │  Click menu → DOM handles ✅         ││
│  │  └──────────────┘                                      ││
│  │      ▲                                                  ││
│  │      │ DOM events work                                 ││
│  │      │ (checkbox, expand, close)                       ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    Red Dead Redemption 2 (blocked - overlay captures input)
```

---

## Click Handling Decision Tree

```
                        [User Clicks]
                              │
                              ▼
                    ┌──────────────────┐
                    │ Backend Observer │
                    │ (Always Captures)│
                    └──────────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │  Send 'mouse-clicked'   │
                  │  {x, y, button}         │
                  └─────────────────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │   Frontend Hit-Testing  │
                  └─────────────────────────┘
                              │
                              ▼
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
        [Video Close?] ─YES→ closeVideoPlayer()
                │
               NO
                │
                ▼
        [Tooltip Video?] ─YES→ showVideoPlayer()
                │
               NO
                │
                ▼
        [Over Menu?] ───YES→ ┌───────────────────────┐
                │            │ Click-through enabled?│
               NO            └───────────────────────┘
                │                      │         │
                ▼                     YES       NO
        [Collectible?] ─YES→           │         │
                │              Pass to game   Let DOM
               NO                       │      handle
                │                       ▼         ▼
                ▼                   [GAME]    [MENU]
        ┌─────────────────────┐
        │ Click-through on?   │
        └─────────────────────┘
                │         │
               YES       NO
                │         │
                ▼         ▼
          Pass to game  Ignore
```

---

## Cursor Polling Flow (60fps)

```
        ┌──────────────────────────────┐
        │   pollCursor() - 60fps loop  │
        └──────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │  Get cursor position (IPC)   │
        └──────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │   Check if over UI elements  │
        │                              │
        │   • Tooltip?                 │
        │   • Timer widget?            │
        │   • Tracker menu?            │
        │   • Video player open?       │
        └──────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │  needsInteraction?           │
        └──────────────────────────────┘
              │              │
             YES            NO
              │              │
              ▼              ▼
    [Disable Click-Through]  [Enable Click-Through]
              │              │
              └──────┬───────┘
                     │
                     ▼
        ┌──────────────────────────────┐
        │   Over tooltip/menu?         │
        └──────────────────────────────┘
              │              │
             YES            NO
              │              │
              ▼              ▼
        Keep current    Check collectible
        tooltip state   hover state
              │              │
              └──────┬───────┘
                     │
                     ▼
        ┌──────────────────────────────┐
        │   Hovering collectible?      │
        └──────────────────────────────┘
              │              │
             YES            NO
              │              │
              ▼              ▼
        showTooltip()   hideTooltip()
```

---

## Example Scenarios

### Scenario 1: Click Collectible (Menu Closed)

```
1. User clicks collectible at (500, 300)
2. Backend observer captures click → sends to frontend
3. Click-through: ENABLED ✅
4. Hit-test: isClickOnVideoCloseButton? NO
5. Hit-test: isClickOnTooltipVideoLink? NO
6. Hit-test: isCursorOverTracker? NO
7. Hit-test: findCollectibleAt(500, 300)? YES ✅
8. toggleCollected(collectible)
9. Click also passes to game (click-through enabled)
```

### Scenario 2: Click Collectible (Menu Open Elsewhere)

```
1. User clicks collectible at (500, 300)
2. Tracker menu is open at (100, 100)
3. Cursor at (500, 300) → NOT over menu
4. Click-through: ENABLED ✅ (cursor not over menu)
5. Backend observer captures click → sends to frontend
6. Hit-test: findCollectibleAt(500, 300)? YES ✅
7. toggleCollected(collectible)
8. Click passes to game
```

Wait, this is wrong! Let me reconsider...

Actually, when the menu is open at (100, 100) but cursor is at (500, 300):
- `isCursorOverTracker(500, 300)` returns FALSE
- So `needsInteraction` = FALSE
- So `isClickThroughEnabled` = TRUE ✅

This is correct! Click-through is only disabled when cursor is ACTIVELY over the menu.

### Scenario 3: Click Menu Item

```
1. User clicks menu checkbox at (150, 150)
2. Cursor at (150, 150) → over tracker menu
3. Click-through: DISABLED ❌ (cursor over menu)
4. Backend observer captures click → sends to frontend
5. Hit-test: isClickOnVideoCloseButton? NO
6. Hit-test: isClickOnTooltipVideoLink? NO
7. Hit-test: isCursorOverTracker(150, 150)? YES
8. Click-through disabled? YES
9. → Let DOM handle (return early)
10. DOM onclick handler fires → checkbox toggles ✅
```

### Scenario 4: Right-Click Collectible While Menu Open (Cursor Over Menu)

```
1. Tracker menu open at (100, 100)
2. User moves cursor to collectible at (500, 300)
3. Cursor at (500, 300) → NOT over menu anymore
4. pollCursor() detects: needsInteraction = FALSE
5. Click-through → ENABLED ✅
6. User right-clicks collectible
7. Backend observer sends click to frontend
8. Hit-test: findCollectibleAt(500, 300)? YES
9. toggleCollected(collectible) ✅

Result: Works perfectly! Menu stays open, collectible toggles.
```

### Scenario 5: Click Collectible With Cursor Over Menu

```
1. Tracker menu open at (100, 100)
2. Cursor hovering over menu at (150, 150)
3. Click-through: DISABLED (cursor over menu)
4. Collectible at (500, 300) is visible but cursor not near it
5. User can't click it without moving cursor away from menu first
6. This is expected behavior - prevents accidental clicks through menu
```

---

## Key Insights

### ✅ What Works Now

1. **Collectibles always respond to right-click** (even when menu open elsewhere)
   - As long as cursor moves to the collectible (which disables click-through for that region)

2. **Menu is fully interactive**
   - DOM events work when click-through disabled
   - Backend clicks are filtered out for menu region

3. **Tooltips show correctly**
   - Cursor polling detects hover
   - Tooltip appears immediately
   - Stays visible when cursor moves to tooltip itself

4. **Click-through is smart**
   - Only disabled when cursor ACTIVELY over UI elements
   - Re-enables when cursor moves away

### ⚠️ Important Constraints

1. **Can't click collectibles while cursor is over menu**
   - Must move cursor to collectible first
   - This prevents clicks from "passing through" the menu

2. **Backend always sends clicks**
   - Even when click-through disabled
   - Frontend filters them appropriately

3. **60fps cursor polling**
   - Uses IPC to get cursor position
   - Async operation (negligible lag)

---

## Testing Commands

### Enable Debug Logging

In `renderer.js`, all relevant logs are already in place:

```javascript
console.log(`[Click Observer] Backend click at (${x}, ${y}), button: ${button}, click-through: ${isClickThroughEnabled}`);
console.log(`[Click Observer] Click on menu/timer - letting DOM handle it`);
console.log(`[Click Observer] Right-click on collectible: ${collectible.name}`);
console.log(`[Cursor] Hovering collectible: ${hoveredItem.name} at (${hoveredItem.x}, ${hoveredItem.y})`);
```

### Watch Console While Testing

1. Hover collectible → See: `[Cursor] Hovering collectible: ...`
2. Right-click collectible → See: `[Click Observer] Right-click on collectible: ...`
3. Click menu → See: `[Click Observer] Click on menu/timer - letting DOM handle it`
4. Open video → See: `[Video Player] Opening video player`, `[Video Player] Click-through disabled`

---

## Conclusion

The fix maintains clean separation between:
- **Backend observation**: Global click monitoring (never interferes)
- **Frontend routing**: Smart hit-testing and event delegation
- **Click-through control**: Dynamic based on cursor position

This architecture allows all UI elements to work simultaneously while preserving the overlay's transparent behavior for gameplay.
