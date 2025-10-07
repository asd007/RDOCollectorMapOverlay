# Integration Tests

Integration tests that verify the complete RDO Overlay application workflow, including:

- Flask API endpoints
- Continuous capture service
- Matching pipeline
- Collectibles data loading
- Qt/QML overlay initialization
- Hotkey system
- State management

## Running Integration Tests

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific test category
python -m pytest tests/integration/test_api_integration.py -v
python -m pytest tests/integration/test_capture_integration.py -v
python -m pytest tests/integration/test_overlay_integration.py -v

# Run with detailed output
python -m pytest tests/integration/ -v -s
```

## Test Categories

### API Integration Tests (`test_api_integration.py`)
- Flask server startup/shutdown
- `/status` endpoint
- `/stats` endpoint
- `/align-with-screenshot` workflow
- `/reset-tracking` functionality
- `/refresh-data` collectibles reload
- Error handling and timeouts

### Capture Integration Tests (`test_capture_integration.py`)
- Continuous capture service lifecycle
- Frame processing pipeline
- Deduplication system
- Game focus detection
- Adaptive FPS adjustment
- Performance monitoring

### Overlay Integration Tests (`test_overlay_integration.py`)
- Qt/QML application initialization
- CollectibleCanvas rendering
- OverlayBackend signal/slot communication
- Hotkey system (F7/F8/F9/F6)
- CollectionTracker UI updates
- Theme and styling

### Matcher Integration Tests (`test_matcher_integration.py`)
- Full matching pipeline with real map
- Cascade matcher with ROI tracking
- Motion prediction integration
- Feature cache loading
- Viewport transform accuracy

## Test Data

Integration tests may use:
- `tests/data/` - Real gameplay screenshots for validation
- `data/cache/` - Pre-computed feature pyramids
- `data/rdr2_map_hq.png` - Reference map

## Notes

- Some tests require the game to be running (marked with `@pytest.mark.requires_game`)
- Tests that need network access are marked with `@pytest.mark.requires_network`
- Slow tests (>5s) are marked with `@pytest.mark.slow`
- Use `-m "not slow"` to skip slow tests during development
