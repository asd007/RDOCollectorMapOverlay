"""
Run tests using real gameplay screenshots captured during test collection.
Validates matching accuracy and performance against real-world scenarios.
"""

import cv2
import json
import time
import numpy as np
from pathlib import Path
from typing import List, Dict
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching.simple_matcher import SimpleMatcher
from core.image_preprocessing import preprocess_with_resize
from config import MAP_DIMENSIONS


def load_test_manifest(test_data_dir: str = "tests/test_data") -> Dict:
    """Load test manifest."""
    manifest_path = Path(test_data_dir) / "test_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No test manifest found at {manifest_path}")

    with open(manifest_path) as f:
        return json.load(f)


def run_tests(test_data_dir: str = "tests/test_data"):
    """
    Run tests using captured real gameplay data.

    Tests each screenshot and compares:
    - Viewport position accuracy (within tolerance)
    - Performance vs expected time
    - Cascade level selection
    """
    print("="*70)
    print("REAL GAMEPLAY TEST SUITE")
    print("="*70)

    # Load test manifest
    manifest = load_test_manifest(test_data_dir)
    test_cases = manifest['test_cases']
    print(f"\nLoaded {len(test_cases)} test cases from {manifest['created_at']}")

    # Initialize matcher (same config as production)
    print("\nInitializing matcher...")
    from config.paths import CachePaths
    hq_source = CachePaths.find_hq_map_source()
    if not hq_source:
        raise FileNotFoundError("HQ map not found!")

    hq_map = cv2.imread(str(hq_source))
    detection_map = preprocess_with_resize(hq_map, scale=MAP_DIMENSIONS.DETECTION_SCALE)

    base_matcher = SimpleMatcher(
        max_features=0,
        ratio_test_threshold=0.75,
        min_inliers=5,
        min_inlier_ratio=0.5,
        ransac_threshold=5.0,
        use_spatial_distribution=True,
        spatial_grid_size=50,
        max_screenshot_features=300,
        use_flann=False,
        use_gpu=True
    )
    base_matcher.compute_reference_features(detection_map)

    cascade_levels = [
        ScaleConfig(scale=0.25, max_features=75, min_confidence=0.85, min_inliers=10, name="Fast (25%)"),
        ScaleConfig(scale=0.5, max_features=150, min_confidence=0.75, min_inliers=8, name="Reliable (50%)"),
        ScaleConfig(scale=0.7, max_features=210, min_confidence=0.0, min_inliers=5, name="Optimized (70% fallback)")
    ]

    matcher = CascadeScaleMatcher(base_matcher, cascade_levels, use_scale_prediction=False, verbose=False)

    # Run tests
    results = []
    position_errors = []
    timing_comparisons = []

    print("\nRunning tests...\n")

    for i, test_case in enumerate(test_cases):
        test_id = test_case['test_id']
        screenshot_path = Path(test_data_dir) / test_case['screenshot']
        expected = test_case['expected_viewport']

        # Load screenshot
        screenshot = cv2.imread(str(screenshot_path))
        if screenshot is None:
            print(f"❌ {test_id}: Screenshot not found")
            continue

        # Run matcher
        start_time = time.time()
        result = matcher.match(screenshot)
        match_time = (time.time() - start_time) * 1000

        if result and result.get('success'):
            # Calculate position error
            error_x = abs(result['map_x'] - expected['map_x'])
            error_y = abs(result['map_y'] - expected['map_y'])
            position_error = np.sqrt(error_x**2 + error_y**2)
            position_errors.append(position_error)

            # Compare timing
            reference_time = test_case['reference_timing']['match_ms']
            timing_ratio = match_time / reference_time if reference_time > 0 else 0
            timing_comparisons.append(timing_ratio)

            cascade_info = result.get('cascade_info', {})
            cascade_level = cascade_info.get('final_level', 'unknown')

            # Check if position is accurate (within 50px tolerance)
            accurate = position_error < 50
            symbol = "PASS" if accurate else "WARN"

            print(f"{symbol} {test_id}:")
            print(f"  Position error: {position_error:.1f}px")
            print(f"  Timing: {match_time:.1f}ms (ref: {reference_time:.1f}ms, {timing_ratio:.2f}x)")
            print(f"  Cascade: {cascade_level} (ref: {test_case['cascade_level']})")
            print(f"  Confidence: {result['confidence']:.2%} ({result['inliers']} inliers)")

            results.append({
                'test_id': test_id,
                'success': True,
                'accurate': accurate,
                'position_error': position_error,
                'match_time_ms': match_time,
                'reference_time_ms': reference_time,
                'timing_ratio': timing_ratio,
                'cascade_level': cascade_level
            })
        else:
            print(f"❌ {test_id}: Matching failed - {result.get('error', 'Unknown error')}")
            results.append({
                'test_id': test_id,
                'success': False,
                'error': result.get('error', 'Unknown')
            })

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    successful = sum(1 for r in results if r.get('success'))
    accurate = sum(1 for r in results if r.get('accurate', False))
    success_rate = (successful / len(results)) * 100 if results else 0
    accuracy_rate = (accurate / len(results)) * 100 if results else 0

    print(f"\nTotal tests: {len(results)}")
    print(f"Successful matches: {successful}/{len(results)} ({success_rate:.1f}%)")
    print(f"Accurate positions: {accurate}/{len(results)} ({accuracy_rate:.1f}%)")

    if position_errors:
        print(f"\nPosition Error:")
        print(f"  Mean: {np.mean(position_errors):.1f}px")
        print(f"  Median: {np.median(position_errors):.1f}px")
        print(f"  P95: {np.percentile(position_errors, 95):.1f}px")
        print(f"  Max: {np.max(position_errors):.1f}px")

    if timing_comparisons:
        print(f"\nTiming vs Reference:")
        print(f"  Mean ratio: {np.mean(timing_comparisons):.2f}x")
        print(f"  Median ratio: {np.median(timing_comparisons):.2f}x")
        print(f"  Better than ref: {sum(1 for t in timing_comparisons if t < 1)}/{len(timing_comparisons)}")
        print(f"  Worse than ref: {sum(1 for t in timing_comparisons if t > 1)}/{len(timing_comparisons)}")

    print("="*70 + "\n")

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run tests on real gameplay data')
    parser.add_argument('--test-dir', default='tests/test_data', help='Test data directory')
    args = parser.parse_args()

    try:
        results = run_tests(args.test_dir)
    except Exception as e:
        print(f"\nTest suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
