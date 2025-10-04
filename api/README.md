# API Module

Flask REST API and WebSocket endpoints for frontend communication.

## Purpose

Provides HTTP REST API for on-demand operations (alignment, refresh) and WebSocket push updates for real-time viewport/collectible tracking.

## Files

### `routes.py`
Flask application with all endpoints:

**REST Endpoints**:
- `GET /status`: System readiness check, returns collectible count and backend version
- `POST /align-with-screenshot`: Main workflow - captures screenshot, runs matching, returns collectibles
- `POST /reset-tracking`: Clears cascade matcher history (forces fresh match)
- `POST /refresh-data`: Reloads collectibles from Joan Ropke API
- `GET /profiling-stats`: Performance metrics (match time, feature counts, confidence)

**WebSocket Events**:
- `connect`: Client connection established
- `viewport_update`: Push new viewport position + collectibles (triggered by continuous capture)
- `collectible_marked`: Client marks collectible as collected

**Response Format**:
```json
{
  "success": true,
  "collectibles": [
    {
      "x": 150, "y": 200,
      "type": "flower_agarita",
      "name": "Desert Sage",
      "tool": "none"
    }
  ],
  "viewport": {"x": 1000, "y": 2000, "width": 1920, "height": 1080},
  "confidence": 0.85,
  "timing": {
    "screenshot_ms": 50,
    "matching_ms": 180,
    "overlay_ms": 5,
    "total_ms": 235
  }
}
```

### `state.py`
Overlay state management:

- **OverlayState class**: Maintains viewport position, collectibles, marked items
- **get_visible_collectibles()**: Filters collectibles in current viewport, transforms to screen coordinates
- **Coordinate transforms**: Detection space → Screen space with 80% crop adjustment
- **Numpy vectorization**: Fast spatial queries for thousands of collectibles

**Key Methods**:
- `update_viewport()`: Updates position from matcher
- `get_visible_collectibles()`: Returns collectibles in viewport
- `mark_collected()`: Marks collectible as collected (filters from view)

## Usage

**Starting the server**:
```python
from api.routes import app, socketio
from config.settings import SERVER

socketio.run(app, host=SERVER.HOST, port=SERVER.PORT)
```

**Client requests**:
```javascript
// HTTP request (one-time alignment)
const response = await axios.post('http://127.0.0.1:5000/align-with-screenshot');

// WebSocket connection (continuous updates)
const socket = io('http://127.0.0.1:5000');
socket.on('viewport_update', (data) => {
  updateMarkers(data.collectibles);
});
```

## Request Flow

1. **F9 Pressed (Manual Sync)**:
   - Frontend → `POST /align-with-screenshot`
   - Backend captures screenshot
   - Cascade matcher finds viewport
   - Collectibles filtered + transformed to screen space
   - Response sent with collectibles + viewport

2. **Continuous Tracking**:
   - Background thread captures at 5fps
   - Each frame: match → update state → push via WebSocket
   - Frontend receives `viewport_update` events
   - Canvas redraws collectibles at new positions

3. **Collectible Marked**:
   - Frontend → `collectible_marked` WebSocket event
   - Backend removes from state
   - Next viewport update excludes marked collectible

## Performance Logging

All endpoints log timing breakdown:
```
[2025-10-03 12:34:56] Screenshot: 45ms | Matching: 187ms | Overlay: 3ms | Total: 235ms
```

Useful for identifying bottlenecks and tracking optimization improvements.

## Notes

- CORS enabled for development (allows frontend on different port)
- WebSocket uses Socket.IO for automatic reconnection
- State is in-memory only (resets on backend restart)
- Marked collectibles don't persist across sessions
