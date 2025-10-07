#!/usr/bin/env python3
"""
Test the CascadeScaleMatcher implementation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import time

from config import MAP_DIMENSIONS
from core.map.map_loader import MapLoader
from core.matching.image_preprocessing import preprocess_for_matching
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig, create_cascade_matcher
from matching.simple_matcher import SimpleMatcher
from tests.test_matching import SyntheticTestGenerator, AccuracyValidator, CoordinateTransform


def test_cascade_matcher():
    """Test cascade matcher with different configurations."""
    print("=" * 80)
    print("CASCADE SCALE MATCHER TEST")
    print("=" * 80)

    np.random.seed(42)

    # Load maps
    print("\nLoading maps...")
    original_map = MapLoader.load_map(use_preprocessing=False, posterize_before_gray=False)
    preprocessed_map = MapLoader.load_map(use_preprocessing=True, posterize_before_gray=False)

    h, w = preprocessed_map.shape
    detection_map = cv2.resize(preprocessed_map, (int(w * 0.5), int(h * 0.5)),
                               interpolation=cv2.INTER_AREA)

    print(f"Detection map: {detection_map.shape[1]}x{detection_map.shape[0]}")

    # Initialize matchers
    print("\n" + "-" * 80)
    print("INITIALIZING MATCHERS")
    print("-" * 80)

    # Base matcher for comparison
    print("\n1. SimpleMatcher (baseline 50%):")
    base_matcher_baseline = SimpleMatcher(
        max_features=0, ratio_test_threshold=0.75, min_inliers=5,
        min_inlier_ratio=0.5, ransac_threshold=5.0,
        use_spatial_distribution=True, spatial_grid_size=50,
        max_screenshot_features=150  # 50% scale
    )
    base_matcher_baseline.compute_reference_features(detection_map)
    print(f"   Map features: {len(base_matcher_baseline.kp_map)}")

    # Cascade matchers
    print("\n2. Default Cascade (25% -> 50%):")
    cascade_default = create_cascade_matcher(detection_map, cascade_type='default', verbose=False)

    print("\n3. Aggressive Cascade (12.5% -> 25% -> 50%):")
    cascade_aggressive = create_cascade_matcher(detection_map, cascade_type='aggressive', verbose=False)

    print("\n4. Custom Cascade (25% strict -> 50% relaxed -> 100% fallback):")
    base_matcher_custom = SimpleMatcher(
        max_features=0, ratio_test_threshold=0.75, min_inliers=5,
        min_inlier_ratio=0.5, ransac_threshold=5.0,
        use_spatial_distribution=True, spatial_grid_size=50,
        max_screenshot_features=300
    )
    base_matcher_custom.compute_reference_features(detection_map)

    cascade_custom = CascadeScaleMatcher.create_custom_cascade(
        base_matcher_custom,
        [
            (0.25, 75, 0.85, 10, "Fast (strict)"),
            (0.5, 150, 0.75, 8, "Medium (relaxed)"),
            (1.0, 300, 0.0, 5, "Full (fallback)")
        ],
        verbose=False
    )

    # Generate test cases
    print("\n" + "-" * 80)
    print("GENERATING TEST CASES")
    print("-" * 80)

    coord_transform = CoordinateTransform()
    validator = AccuracyValidator(coord_transform)
    validator.load_collectibles_data()
    generator = SyntheticTestGenerator(original_map)

    test_cases = []
    for zoom in ['very_close', 'close', 'medium', 'far', 'very_far']:
        for i in range(3):
            test_case = generator.generate_test_case(zoom, require_collectibles=True,
                                                     validator=validator, max_attempts=20)
            if test_case:
                test_cases.append((zoom, test_case))

    print(f"Generated {len(test_cases)} test cases")

    # Test all configurations
    configs = [
        ('Baseline (50% only)', base_matcher_baseline, None),
        ('Default Cascade', None, cascade_default),
        ('Aggressive Cascade', None, cascade_aggressive),
        ('Custom Cascade', None, cascade_custom)
    ]

    all_results = {}

    for config_name, simple_matcher, cascade_matcher in configs:
        print("\n" + "=" * 80)
        print(f"TESTING: {config_name}")
        print("=" * 80)

        results = []

        for i, (zoom, test_case) in enumerate(test_cases, 1):
            screenshot_gray = test_case['image']
            screenshot_color = cv2.cvtColor(screenshot_gray, cv2.COLOR_GRAY2BGR)

            # Preprocess
            start_prep = time.time()
            screenshot_preprocessed = preprocess_for_matching(screenshot_color, posterize_before_gray=False)
            prep_time = (time.time() - start_prep) * 1000

            # Match
            start_match = time.time()
            if cascade_matcher:
                # Cascade handles scaling internally
                result = cascade_matcher.match(screenshot_preprocessed)
            else:
                # Baseline: manually scale to 50%
                screenshot_scaled = cv2.resize(screenshot_preprocessed,
                                              (int(screenshot_preprocessed.shape[1] * 0.5),
                                               int(screenshot_preprocessed.shape[0] * 0.5)),
                                              interpolation=cv2.INTER_AREA)
                result = simple_matcher.match(screenshot_scaled)

            match_time = (time.time() - start_match) * 1000
            total_time = prep_time + match_time

            success = result is not None and result.get('success', False)

            result_info = {
                'time': total_time,
                'prep_time': prep_time,
                'match_time': match_time,
                'success': success,
                'zoom': zoom
            }

            if success and cascade_matcher and 'cascade_info' in result:
                result_info['cascade_info'] = result['cascade_info']
                final_level = result['cascade_info']['final_level']
                levels_tried = len(result['cascade_info']['levels_tried'])
                print(f"  Test {i}/{len(test_cases)} ({zoom}): {total_time:>6.2f}ms  OK  "
                      f"(used {final_level}, tried {levels_tried} levels)")
            else:
                status = 'OK' if success else 'FAIL'
                print(f"  Test {i}/{len(test_cases)} ({zoom}): {total_time:>6.2f}ms  {status}")

            results.append(result_info)

        all_results[config_name] = results

    # Summary
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)

    print(f"\n{'Configuration':<30} {'Mean':<10} {'Median':<10} {'Min':<10} {'Max':<10} {'Success':<10}")
    print("-" * 90)

    for config_name, results in all_results.items():
        times = [r['time'] for r in results]
        success_rate = sum(r['success'] for r in results) / len(results) * 100

        print(f"{config_name:<30} {np.mean(times):<10.2f} {np.median(times):<10.2f} "
              f"{np.min(times):<10.2f} {np.max(times):<10.2f} {success_rate:<10.1f}%")

    # Cascade level usage breakdown
    print("\n" + "-" * 80)
    print("CASCADE LEVEL USAGE")
    print("-" * 80)

    for config_name, results in all_results.items():
        if 'Cascade' in config_name:
            print(f"\n{config_name}:")

            level_usage = {}
            for r in results:
                if r['success'] and 'cascade_info' in r:
                    final_level = r['cascade_info']['final_level']
                    level_usage[final_level] = level_usage.get(final_level, 0) + 1

            for level, count in sorted(level_usage.items()):
                pct = count / len(results) * 100
                print(f"  {level}: {count}/{len(results)} ({pct:.1f}%)")

    # Speedup analysis
    print("\n" + "-" * 80)
    print("SPEEDUP vs BASELINE")
    print("-" * 80)

    baseline_times = [r['time'] for r in all_results['Baseline (50% only)']]
    baseline_mean = np.mean(baseline_times)

    print(f"\nBaseline: {baseline_mean:.2f}ms\n")

    for config_name, results in all_results.items():
        if 'Cascade' in config_name:
            times = [r['time'] for r in results]
            mean_time = np.mean(times)
            speedup = baseline_mean / mean_time
            time_saved = baseline_mean - mean_time
            success_rate = sum(r['success'] for r in results) / len(results) * 100

            print(f"{config_name}:")
            print(f"  Mean time: {mean_time:.2f}ms")
            print(f"  Speedup: {speedup:.2f}x")
            print(f"  Time saved: {time_saved:.2f}ms")
            print(f"  Success rate: {success_rate:.1f}%")

            if mean_time < 50:
                print(f"  SUCCESS: <50ms target achieved!")
            print()

    print("=" * 80)


if __name__ == '__main__':
    test_cascade_matcher()
