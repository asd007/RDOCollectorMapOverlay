"""
Performance tests for TranslationTracker using synthetic data.

Validates pixel-perfect accuracy and <10ms performance target.
Generates synthetic viewports from HQ map with known translations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import time
from matching.translation_tracker import TranslationTracker, AdaptiveTranslationTracker
from config.paths import CachePaths


class SyntheticTestDataGenerator:
    """Generate synthetic test frames with known ground truth translations."""

    def __init__(self, hq_map_path: str):
        """
        Initialize generator with HQ map.

        Args:
            hq_map_path: Path to high-resolution reference map
        """
        print(f"Loading HQ map from: {hq_map_path}")
        self.hq_map = cv2.imread(hq_map_path, cv2.IMREAD_GRAYSCALE)
        if self.hq_map is None:
            raise FileNotFoundError(f"Could not load map from {hq_map_path}")

        self.map_height, self.map_width = self.hq_map.shape
        print(f"HQ map loaded: {self.map_width}×{self.map_height}")

    def generate_viewport(self, center_x: int, center_y: int,
                         width: int = 1920, height: int = 1080,
                         zoom: float = 1.0) -> np.ndarray:
        """
        Extract viewport from HQ map with optional zoom.

        Args:
            center_x: Center X in map coordinates
            center_y: Center Y in map coordinates
            width: Viewport width (default 1920)
            height: Viewport height (default 1080)
            zoom: Zoom level (1.0 = native, 0.5 = zoomed out 2×)

        Returns:
            Extracted viewport as grayscale image
        """
        # Calculate extraction size based on zoom
        extract_width = int(width / zoom)
        extract_height = int(height / zoom)

        # Calculate bounds (ensure within map)
        x1 = max(0, center_x - extract_width // 2)
        y1 = max(0, center_y - extract_height // 2)
        x2 = min(self.map_width, x1 + extract_width)
        y2 = min(self.map_height, y1 + extract_height)

        # Adjust if we hit edge
        if x2 - x1 < extract_width:
            x1 = max(0, x2 - extract_width)
        if y2 - y1 < extract_height:
            y1 = max(0, y2 - extract_height)

        # Extract region
        viewport = self.hq_map[y1:y2, x1:x2]

        # Resize to target size if zoomed
        if zoom != 1.0:
            viewport = cv2.resize(viewport, (width, height), interpolation=cv2.INTER_LINEAR)

        return viewport

    def generate_translation_sequence(self, start_x: int, start_y: int,
                                     movements: list, zoom: float = 1.0) -> list:
        """
        Generate sequence of frames with known translations.

        Args:
            start_x: Starting center X
            start_y: Starting center Y
            movements: List of (dx, dy) movements in map coordinates
            zoom: Zoom level

        Returns:
            List of (frame, dx_true, dy_true) tuples
        """
        sequence = []
        current_x, current_y = start_x, start_y

        # Generate first frame
        first_frame = self.generate_viewport(current_x, current_y, zoom=zoom)
        sequence.append((first_frame, 0.0, 0.0))

        # Generate subsequent frames with movements
        for dx, dy in movements:
            current_x += dx
            current_y += dy

            # Ensure we stay within map bounds
            current_x = np.clip(current_x, 1000, self.map_width - 1000)
            current_y = np.clip(current_y, 1000, self.map_height - 1000)

            frame = self.generate_viewport(current_x, current_y, zoom=zoom)
            sequence.append((frame, dx, dy))

        return sequence


def test_basic_accuracy():
    """Test basic tracking accuracy with simple movements."""
    print("\n" + "="*80)
    print("TEST 1: Basic Accuracy - Simple Translations")
    print("="*80)

    # Load HQ map
    hq_map_path = CachePaths.find_hq_map_source()
    if not hq_map_path or not hq_map_path.exists():
        print("ERROR: HQ map not found!")
        return

    generator = SyntheticTestDataGenerator(str(hq_map_path))

    # Test movements (in map coordinates)
    test_movements = [
        (10, 5),    # Small movement
        (25, -15),  # Medium movement
        (50, 30),   # Larger movement
        (-75, 20),  # Negative X
        (100, -50), # Large movement
        (5, 2),     # Tiny movement
        (-8, 3),    # Small negative
        (15, -10),  # Medium
        (-30, 25),  # Medium negative
        (0, 40),    # Y-only movement
    ]

    # Generate test sequence
    print("\nGenerating synthetic test sequence...")
    start_x, start_y = 10000, 8000  # Center of map roughly
    sequence = generator.generate_translation_sequence(start_x, start_y, test_movements, zoom=1.0)

    # Test tracker
    tracker = TranslationTracker(scale=0.5, min_confidence=0.1)
    errors = []
    timings = []

    print("\nTracking sequence...")
    for i, (frame, dx_true, dy_true) in enumerate(sequence):
        result, confidence, debug = tracker.track(frame)

        if i == 0:
            # First frame has no movement
            assert result is None, "First frame should return None"
            continue

        # Check result
        if result is None:
            print(f"Frame {i}: FAILED - No result returned (confidence too low)")
            errors.append(float('inf'))
            continue

        dx_pred, dy_pred = result
        error = np.sqrt((dx_true - dx_pred)**2 + (dy_true - dy_pred)**2)
        errors.append(error)
        timings.append(debug['total_ms'])

        status = "PASS" if error < 1.0 else "WARN" if error < 3.0 else "FAIL"
        print(f"Frame {i}: {status} | True: ({dx_true:6.1f}, {dy_true:6.1f}) | "
              f"Pred: ({dx_pred:6.1f}, {dy_pred:6.1f}) | "
              f"Error: {error:5.2f}px | Time: {debug['total_ms']:.2f}ms | "
              f"Conf: {confidence:.3f}")

    # Statistics
    print("\n" + "-"*80)
    print("RESULTS:")
    print(f"Mean error:   {np.mean(errors):.2f} pixels")
    print(f"Median error: {np.median(errors):.2f} pixels")
    print(f"Max error:    {np.max(errors):.2f} pixels")
    print(f"Errors < 1px: {sum(1 for e in errors if e < 1.0)}/{len(errors)} ({sum(1 for e in errors if e < 1.0)/len(errors)*100:.1f}%)")
    print(f"\nMean time:    {np.mean(timings):.2f} ms")
    print(f"Median time:  {np.median(timings):.2f} ms")
    print(f"Max time:     {np.max(timings):.2f} ms")
    print(f"Target:       < 10 ms")

    # Pass/fail
    mean_error = np.mean(errors)
    mean_time = np.mean(timings)

    if mean_error < 1.0 and mean_time < 10.0:
        print("\n[PASS] Test passed - accuracy and performance within targets")
    elif mean_error < 3.0 and mean_time < 10.0:
        print("\n[WARN] Test passed with warnings - accuracy slightly degraded but acceptable")
    else:
        print("\n[FAIL] Test failed - accuracy or performance outside targets")


def test_zoom_levels():
    """Test accuracy across different zoom levels."""
    print("\n" + "="*80)
    print("TEST 2: Multi-Zoom Accuracy")
    print("="*80)

    hq_map_path = CachePaths.find_hq_map_source()
    if not hq_map_path or not hq_map_path.exists():
        print("ERROR: HQ map not found!")
        return

    generator = SyntheticTestDataGenerator(str(hq_map_path))

    # Test at different zoom levels
    zoom_levels = [0.5, 0.75, 1.0, 1.5, 2.0]  # Detection scale relative to HQ map

    # Simple movement sequence
    movements = [(20, 10), (30, -15), (-25, 20), (15, 25), (-10, -30)]

    print("\nTesting at different zoom levels...")
    for zoom in zoom_levels:
        print(f"\n--- Zoom {zoom}× ---")

        sequence = generator.generate_translation_sequence(10000, 8000, movements, zoom=zoom)
        tracker = TranslationTracker(scale=0.5)

        errors = []
        for i, (frame, dx_true, dy_true) in enumerate(sequence):
            result, confidence, debug = tracker.track(frame)

            if i == 0 or result is None:
                continue

            dx_pred, dy_pred = result
            error = np.sqrt((dx_true - dx_pred)**2 + (dy_true - dy_pred)**2)
            errors.append(error)

        print(f"Mean error: {np.mean(errors):.2f}px | Max error: {np.max(errors):.2f}px")


def test_performance_scaling():
    """Test performance with different tracker configurations."""
    print("\n" + "="*80)
    print("TEST 3: Performance Scaling")
    print("="*80)

    hq_map_path = CachePaths.find_hq_map_source()
    if not hq_map_path or not hq_map_path.exists():
        print("ERROR: HQ map not found!")
        return

    generator = SyntheticTestDataGenerator(str(hq_map_path))

    # Generate test sequence
    movements = [(20, 10)] * 20  # Consistent movement
    sequence = generator.generate_translation_sequence(10000, 8000, movements, zoom=1.0)

    # Test different scales
    scales = [0.25, 0.5, 0.75, 1.0]

    print("\nTesting different downsampling scales...")
    for scale in scales:
        tracker = TranslationTracker(scale=scale)
        timings = []
        errors = []

        for i, (frame, dx_true, dy_true) in enumerate(sequence):
            result, confidence, debug = tracker.track(frame)

            if i == 0 or result is None:
                continue

            timings.append(debug['total_ms'])

            dx_pred, dy_pred = result
            error = np.sqrt((dx_true - dx_pred)**2 + (dy_true - dy_pred)**2)
            errors.append(error)

        print(f"Scale {scale:4.2f}× | Mean time: {np.mean(timings):5.2f}ms | "
              f"Mean error: {np.mean(errors):5.2f}px")


def test_adaptive_tracker():
    """Test adaptive scale selection."""
    print("\n" + "="*80)
    print("TEST 4: Adaptive Scale Selection")
    print("="*80)

    hq_map_path = CachePaths.find_hq_map_source()
    if not hq_map_path or not hq_map_path.exists():
        print("ERROR: HQ map not found!")
        return

    generator = SyntheticTestDataGenerator(str(hq_map_path))

    # Movements with varying magnitudes
    movements = [
        (5, 5),      # Small
        (10, 8),     # Small
        (60, 40),    # Medium -> should trigger 0.5×
        (80, 50),    # Medium
        (250, 150),  # Large -> should trigger 0.25×
        (300, 200),  # Large
        (10, 5),     # Small -> should trigger 0.75×
        (8, 3),      # Small
    ]

    sequence = generator.generate_translation_sequence(10000, 8000, movements, zoom=1.0)

    # Test adaptive tracker
    tracker = AdaptiveTranslationTracker()

    print("\nTracking with adaptive scale selection...")
    for i, (frame, dx_true, dy_true) in enumerate(sequence):
        result, confidence, debug = tracker.track(frame)

        if i == 0:
            continue

        if result is None:
            print(f"Frame {i}: No result")
            continue

        dx_pred, dy_pred = result
        error = np.sqrt((dx_true - dx_pred)**2 + (dy_true - dy_pred)**2)

        adaptive_scale = debug.get('adaptive_scale', 0.5)
        current_movement = debug.get('current_movement', 0)

        print(f"Frame {i}: Movement={current_movement:6.1f}px | "
              f"Scale={adaptive_scale:.2f}× | Error={error:5.2f}px | "
              f"Time={debug['total_ms']:.2f}ms")


def main():
    """Run all tests."""
    print("\nTranslationTracker Performance Tests")
    print("Using synthetic data from HQ map")

    try:
        test_basic_accuracy()
        test_zoom_levels()
        test_performance_scaling()
        test_adaptive_tracker()

        print("\n" + "="*80)
        print("All tests completed!")
        print("="*80)

    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
