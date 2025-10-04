# Tests Module

Automated test suites for matching accuracy and performance validation.

## Purpose

Validates matching accuracy, tracks performance regressions, and provides ground truth for development. Includes synthetic tests (programmatic) and real gameplay tests (captured screenshots).

## Files

### `test_matching.py`
Synthetic test suite with programmatically generated viewports:

- **15 test cases**: Random viewports from HQ map at various scales
- **Ground truth**: Known viewport position from extraction
- **Accuracy validation**: Compares predicted vs actual position (pixel error)
- **Pass criteria**: <10px error, >0.7 confidence
- **Fast execution**: ~3 seconds for all tests

**Usage**:
```bash
python tests/test_matching.py
```

### `run_real_tests.py`
Real gameplay test suite with captured screenshots:

- **9 test cases**: Real RDO screenshots with ground truth positions
- **Ground truth**: Captured using test_data_collector.py
- **More realistic**: Tests actual game rendering, UI elements, lighting
- **Pass criteria**: <20px error (more lenient due to real-world variations)

**Usage**:
```bash
python tests/run_real_tests.py
```

### `test_data_collector.py`
Interactive tool for capturing ground truth test data:

- **Purpose**: Press F9 in-game to capture screenshot + position
- **Output**: Saves to `tests/test_data/` as screenshot + JSON metadata
- **Metadata**: Viewport position in all coordinate spaces, confidence, timestamp
- **Usage**: Run tool, play game, press F9 at interesting locations

**Usage**:
```bash
python tests/test_data_collector.py
# Press F9 in game to capture test case
```

### `test_cascade_matcher.py`
Unit tests for cascade matcher components:

- Tests pyramid building
- Tests scale selection logic
- Tests ROI optimization
- Tests early exit behavior

### `test_preprocessing.py`, `test_preprocessing_refined.py`, `test_quantization.py`
Image preprocessing experiments:

- Test different preprocessing pipelines
- Compare feature detection quality
- Validate performance impact
- Not part of main test suite (research code)

### `test_windows_capture.py`, `test_windows_capture_simple.py`
Windows Graphics Capture API tests:

- Validate clean game capture
- Test performance (FPS, memory)
- Compare to MSS/PIL approaches

### `benchmark_screenshot_capture.py`
Performance benchmarking for screenshot capture methods:

- Compares MSS, PIL, Windows Graphics Capture
- Measures FPS, latency, memory usage
- Validates capture quality

### `test_debug_visualization.py`
Visual debugging tool:

- Shows matched features overlaid on screenshot
- Displays homography transform
- Helps diagnose matching failures

## Test Data Organization

```
tests/
├── test_data/              # Real gameplay screenshots (Git-tracked)
│   ├── real_test_001.png
│   ├── real_test_001.json
│   └── ...
└── data/
    └── generated/          # Generated test outputs (Git-ignored)
        ├── debug_*.png
        ├── profile_*.json
        └── ...
```

**Important**: Generated data (debug visualizations, profiling results, temporary outputs) should be saved to `tests/data/generated/` to avoid committing temporary files. This directory is Git-ignored.

## Running All Tests

**Synthetic tests only**:
```bash
python tests/test_matching.py
```

**Real gameplay tests only**:
```bash
python tests/run_real_tests.py
```

**CI tests** (GitHub Actions):
```bash
# Runs both synthetic and real tests
pytest tests/
```

## Test Results Format

```
Test: real_test_001.png
  Expected: (1234, 5678) in HQ space
  Predicted: (1236, 5679) in HQ space
  Error: 2.2 pixels
  Confidence: 0.87
  Status: PASS ✓
```

## Notes

- Synthetic tests are fast but may not catch real-world issues
- Real gameplay tests are slower but more realistic
- Test data collector is essential for expanding test coverage
- Generated data should always go to `tests/data/generated/` (Git-ignored)
- Debug visualizations help diagnose failures but should not be committed
