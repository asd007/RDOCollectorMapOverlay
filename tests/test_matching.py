#!/usr/bin/env python3
"""
Accuracy and Performance Tests for RDO Map Overlay
Generates synthetic test images from HQ map and validates matching accuracy
"""

import sys
from pathlib import Path
# Add project root to path (parent of tests/)
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import time
import requests
from typing import List, Dict, Tuple
from datetime import datetime, timezone

from config import MAP_DIMENSIONS, COLLECTIBLES, EXTERNAL_URLS
from core import CoordinateTransform, MapLoader, CollectiblesLoader
from core.matching.image_preprocessing import preprocess_for_matching
from matching.simple_matcher import SimpleMatcher

# Import visualization function for failing tests
try:
    from tests.test_debug_visualization import visualize_failing_test
    VISUALIZATIONS_AVAILABLE = True
except ImportError:
    VISUALIZATIONS_AVAILABLE = False


class SyntheticTestGenerator:
    """Generate synthetic test images from HQ map"""

    # Test screen dimensions (top 80% of 1920x1080)
    TEST_WIDTH = 1920
    TEST_HEIGHT = 864  # 80% of 1080

    def __init__(self, hq_map: np.ndarray):
        self.hq_map = hq_map
        self.map_h, self.map_w = hq_map.shape

    def generate_test_case(self, zoom_level: str = "medium", require_collectibles: bool = True,
                          validator: 'AccuracyValidator' = None, max_attempts: int = 10) -> Dict:
        """
        Generate a synthetic test case at different zoom levels based on realistic in-game zoom.

        Zoom levels (in detection space 10808x8392):
        - max_zoom_out: 50% of map visible (~5404x4196 in detection space)
        - far: ~25% of map visible
        - medium: ~12% of map visible
        - close: ~6% of map visible
        - max_zoom_in: Minimum ~870x370 in detection space
        """
        # Calculate realistic viewport sizes in DETECTION SPACE
        # Detection map is 10808x8392 (0.5x scale of HQ 21617x16785)
        detection_map_w = int(self.map_w * MAP_DIMENSIONS.DETECTION_SCALE)
        detection_map_h = int(self.map_h * MAP_DIMENSIONS.DETECTION_SCALE)

        # Define zoom as viewport size in detection space
        # Based on real gameplay data: viewport range 1327-4264px wide
        # 16:9 aspect ratio (1920x1080)
        zoom_params = {
            'max_zoom_out': (4264, 2402),  # Actual max from gameplay
            'far':          (3500, 1969),  # Upper medium range
            'medium':       (2500, 1406),  # Mid range
            'close':        (1800, 1013),  # Lower medium range
            'max_zoom_in':  (1327, 744)    # Actual min from gameplay
        }

        det_w, det_h = zoom_params.get(zoom_level, zoom_params['medium'])

        # Convert detection space size to HQ space size
        hq_scale = 1.0 / MAP_DIMENSIONS.DETECTION_SCALE
        viewport_w_hq = int(det_w * hq_scale)
        viewport_h_hq = int(det_h * hq_scale)

        # Ensure viewport fits in map
        viewport_w_hq = min(viewport_w_hq, self.map_w - 100)
        viewport_h_hq = min(viewport_h_hq, self.map_h - 100)

        # Focus on SAFE CENTRAL areas of the map (explorable bounds)
        # Define safe region as middle 50% of the map (tighter to avoid out-of-bounds areas)
        central_margin_x = int(self.map_w * 0.25)
        central_margin_y = int(self.map_h * 0.25)

        # Calculate valid range for central positioning
        min_x = central_margin_x
        max_x = self.map_w - viewport_w_hq - central_margin_x
        min_y = central_margin_y
        max_y = self.map_h - viewport_h_hq - central_margin_y

        if max_x <= min_x:
            # Viewport too large, center it
            viewport_x_hq = (self.map_w - viewport_w_hq) // 2
        else:
            viewport_x_hq = np.random.randint(min_x, max_x)

        if max_y <= min_y:
            # Viewport too large, center it
            viewport_y_hq = (self.map_h - viewport_h_hq) // 2
        else:
            viewport_y_hq = np.random.randint(min_y, max_y)

        # Extract viewport from HQ map
        viewport_img = self.hq_map[
            viewport_y_hq:viewport_y_hq + viewport_h_hq,
            viewport_x_hq:viewport_x_hq + viewport_w_hq
        ]

        # Resize to test screen dimensions (1920x864)
        test_img = cv2.resize(viewport_img, (self.TEST_WIDTH, self.TEST_HEIGHT),
                             interpolation=cv2.INTER_LINEAR)

        # Apply realistic variations
        test_img = self._apply_variations(test_img)

        # Ground truth in Detection Space (0.5x)
        detection_scale = MAP_DIMENSIONS.DETECTION_SCALE
        det_x = int(viewport_x_hq * detection_scale)
        det_y = int(viewport_y_hq * detection_scale)
        det_w = int(viewport_w_hq * detection_scale)
        det_h = int(viewport_h_hq * detection_scale)

        # Calculate map coverage percentage (area of viewport / area of detection map)
        viewport_area = det_w * det_h
        map_area = detection_map_w * detection_map_h
        map_coverage_percent = (viewport_area / map_area) * 100

        ground_truth = {
            'hq_x': viewport_x_hq,
            'hq_y': viewport_y_hq,
            'hq_w': viewport_w_hq,
            'hq_h': viewport_h_hq,
            'detection_x': det_x,
            'detection_y': det_y,
            'detection_w': det_w,
            'detection_h': det_h,
            'zoom_level': zoom_level,
            'map_coverage_percent': map_coverage_percent
        }

        # Check if collectibles are present (if required)
        if require_collectibles and validator:
            collectibles = validator.get_collectibles_in_viewport(ground_truth)
            if len(collectibles) == 0:
                # No collectibles, try again if we have attempts left
                if max_attempts > 1:
                    return self.generate_test_case(zoom_level, require_collectibles,
                                                   validator, max_attempts - 1)

        test_case = {
            'image': test_img,
            'ground_truth': ground_truth
        }

        return test_case

    def _apply_variations(self, img: np.ndarray) -> np.ndarray:
        """Apply minimal variations (no brightness/contrast - those don't happen in reality)"""
        # Optional slight noise only
        if np.random.random() < 0.3:
            noise = np.random.normal(0, 2, img.shape).astype(np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return img


class AccuracyValidator:
    """Validate matching accuracy using collectibles as ground truth"""

    def __init__(self, coord_transform: CoordinateTransform):
        self.coord_transform = coord_transform
        self.collectibles_data = None

    def load_collectibles_data(self):
        """Load collectibles from Joan Ropke API"""
        try:
            response = requests.get(EXTERNAL_URLS.ROPKE_ITEMS_API,
                                  timeout=COLLECTIBLES.API_TIMEOUT_SECONDS)
            self.collectibles_data = response.json()

            # Get active cycles
            response = requests.get(EXTERNAL_URLS.ROPKE_CYCLES_API,
                                  timeout=COLLECTIBLES.API_TIMEOUT_SECONDS)
            cycles_data = response.json()
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            active_cycles = {}
            for entry in cycles_data:
                if entry.get('date') == today:
                    active_cycles = entry
                    break

            self.active_cycles = active_cycles
            print(f"Loaded collectibles data with {len(self.collectibles_data)} categories")
            print(f"Active cycles for today: {active_cycles}")

        except Exception as e:
            print(f"Warning: Could not load collectibles data: {e}")
            self.collectibles_data = None

    def get_collectibles_in_viewport(self, viewport_detection: Dict) -> List[Dict]:
        """Get collectibles that should be visible in viewport"""
        if not self.collectibles_data:
            return []

        x1 = viewport_detection['detection_x']
        y1 = viewport_detection['detection_y']
        x2 = x1 + viewport_detection['detection_w']
        y2 = y1 + viewport_detection['detection_h']

        visible_collectibles = []

        for category, cycles_dict in self.collectibles_data.items():
            if not isinstance(cycles_dict, dict):
                continue

            cycle_key = COLLECTIBLES.CATEGORY_TO_CYCLE_KEY.get(category, category)
            cycle = str(self.active_cycles.get(cycle_key, 1))

            if cycle in cycles_dict:
                for item in cycles_dict[cycle]:
                    lat = float(item.get('lat', 0))
                    lng = float(item.get('lng', 0))

                    # Transform to detection space
                    hq_x, hq_y = self.coord_transform.latlng_to_hq(lat, lng)
                    det_x, det_y = self.coord_transform.hq_to_detection(hq_x, hq_y)

                    # Check if in viewport
                    if x1 <= det_x <= x2 and y1 <= det_y <= y2:
                        visible_collectibles.append({
                            'lat': lat,
                            'lng': lng,
                            'detection_x': det_x,
                            'detection_y': det_y,
                            'category': category,
                            'name': item.get('text', 'unknown')
                        })

        return visible_collectibles

    def calculate_pixel_error(self, predicted: Dict, ground_truth: Dict) -> Dict:
        """Calculate pixel-level accuracy metrics"""
        # Position error (top-left corner)
        dx = abs(predicted['detection_x'] - ground_truth['detection_x'])
        dy = abs(predicted['detection_y'] - ground_truth['detection_y'])
        position_error = np.sqrt(dx**2 + dy**2)

        # Size error
        dw = abs(predicted['detection_w'] - ground_truth['detection_w'])
        dh = abs(predicted['detection_h'] - ground_truth['detection_h'])
        size_error = np.sqrt(dw**2 + dh**2)

        # Center error
        pred_center_x = predicted['detection_x'] + predicted['detection_w'] / 2
        pred_center_y = predicted['detection_y'] + predicted['detection_h'] / 2
        gt_center_x = ground_truth['detection_x'] + ground_truth['detection_w'] / 2
        gt_center_y = ground_truth['detection_y'] + ground_truth['detection_h'] / 2

        center_dx = abs(pred_center_x - gt_center_x)
        center_dy = abs(pred_center_y - gt_center_y)
        center_error = np.sqrt(center_dx**2 + center_dy**2)

        return {
            'position_error_pixels': position_error,
            'size_error_pixels': size_error,
            'center_error_pixels': center_error,
            'dx': dx,
            'dy': dy,
            'dw': dw,
            'dh': dh
        }


def run_performance_benchmark(matcher: SimpleMatcher, detection_map: np.ndarray,
                             test_cases: List[Dict], num_iterations: int = 5) -> Dict:
    """Run performance benchmarks"""
    print("\n" + "="*80)
    print("PERFORMANCE BENCHMARK")
    print("="*80)

    timings_by_zoom = {}

    for test_case in test_cases:
        zoom = test_case['ground_truth']['zoom_level']
        if zoom not in timings_by_zoom:
            timings_by_zoom[zoom] = []

        # Preprocess test image (Q10: posterize + CLAHE)
        test_img_preprocessed = preprocess_for_matching(test_case['image'], posterize_before_gray=False)

        # Warm-up run
        try:
            matcher.match(test_img_preprocessed)
        except:
            pass

        # Timed runs
        for i in range(num_iterations):
            start_time = time.time()
            try:
                result = matcher.match(test_img_preprocessed)
                elapsed_ms = (time.time() - start_time) * 1000
                if result['success']:
                    timings_by_zoom[zoom].append(elapsed_ms)
            except Exception as e:
                print(f"  Match failed for {zoom}: {e}")

    # Calculate statistics
    stats = {}
    for zoom, timings in timings_by_zoom.items():
        if timings:
            stats[zoom] = {
                'mean_ms': np.mean(timings),
                'std_ms': np.std(timings),
                'min_ms': np.min(timings),
                'max_ms': np.max(timings),
                'median_ms': np.median(timings),
                'count': len(timings)
            }

    # Print results
    print(f"\nResults from {num_iterations} iterations per zoom level:\n")
    print(f"{'Zoom Level':<15} {'Mean':<10} {'Std':<10} {'Min':<10} {'Max':<10} {'Median':<10}")
    print("-" * 80)

    for zoom in ['max_zoom_out', 'far', 'medium', 'close', 'max_zoom_in']:
        if zoom in stats:
            s = stats[zoom]
            print(f"{zoom:<15} {s['mean_ms']:>8.1f}ms {s['std_ms']:>8.1f}ms "
                  f"{s['min_ms']:>8.1f}ms {s['max_ms']:>8.1f}ms {s['median_ms']:>8.1f}ms")

    # Overall stats
    all_timings = [t for timings in timings_by_zoom.values() for t in timings]
    if all_timings:
        print("-" * 80)
        print(f"{'Overall':<15} {np.mean(all_timings):>8.1f}ms {np.std(all_timings):>8.1f}ms "
              f"{np.min(all_timings):>8.1f}ms {np.max(all_timings):>8.1f}ms {np.median(all_timings):>8.1f}ms")

        target_time = 100  # Target <100ms
        success_rate = sum(1 for t in all_timings if t < target_time) / len(all_timings) * 100
        print(f"\nTarget: <{target_time}ms | Success rate: {success_rate:.1f}%")

    return stats


def run_accuracy_tests(matcher: SimpleMatcher, detection_map: np.ndarray,
                       test_cases: List[Dict], validator: AccuracyValidator) -> Dict:
    """Run accuracy tests"""
    print("\n" + "="*80)
    print("ACCURACY TESTS")
    print("="*80)

    results = []
    failed_visualizations = []  # Track failed tests for visualization

    for i, test_case in enumerate(test_cases):
        gt = test_case['ground_truth']
        zoom = gt['zoom_level']
        is_negative = test_case.get('negative_test', False)

        negative_marker = " [NEGATIVE TEST]" if is_negative else ""
        print(f"\nTest {i+1}/{len(test_cases)}: Zoom={zoom}, Coverage={gt['map_coverage_percent']:.2f}%{negative_marker}")
        if is_negative:
            print(f"  NOTE: {test_case.get('negative_reason', 'Expected to fail')}")
        print(f"  Ground Truth: x={gt['detection_x']}, y={gt['detection_y']}, "
              f"w={gt['detection_w']}, h={gt['detection_h']}")

        try:
            # Preprocess test image (Q10: posterize + CLAHE)
            test_img_preprocessed = preprocess_for_matching(test_case['image'], posterize_before_gray=False)

            # Run matching
            start_time = time.time()
            predicted = matcher.match(test_img_preprocessed)
            elapsed_ms = (time.time() - start_time) * 1000

            if not predicted['success']:
                if is_negative:
                    print(f"  FAILED (EXPECTED): {predicted.get('error', 'Unknown error')}")
                else:
                    print(f"  FAILED: {predicted.get('error', 'Unknown error')}")
                results.append({
                    'success': False,
                    'zoom': zoom,
                    'error': predicted.get('error', 'Matching failed'),
                    'negative_test': is_negative
                })
                # Save for visualization (only if not expected negative)
                if not is_negative:
                    failed_visualizations.append((i+1, test_case))
                continue

            print(f"  Predicted:    x={predicted['map_x']}, y={predicted['map_y']}, "
                  f"w={predicted['map_w']}, h={predicted['map_h']}")
            print(f"  Confidence: {predicted['confidence']:.2%}, "
                  f"Inliers: {predicted['inliers']}, Time: {elapsed_ms:.1f}ms")

            # Convert predicted to same format as ground truth
            predicted_normalized = {
                'detection_x': predicted['map_x'],
                'detection_y': predicted['map_y'],
                'detection_w': predicted['map_w'],
                'detection_h': predicted['map_h']
            }

            # Calculate errors
            errors = validator.calculate_pixel_error(predicted_normalized, gt)

            print(f"  Errors: position={errors['position_error_pixels']:.1f}px, "
                  f"center={errors['center_error_pixels']:.1f}px, "
                  f"size={errors['size_error_pixels']:.1f}px")
            print(f"          dx={errors['dx']}px, dy={errors['dy']}px")

            # Get collectibles in ground truth viewport
            visible_collectibles = validator.get_collectibles_in_viewport(gt)
            print(f"  Collectibles in viewport: {len(visible_collectibles)}")

            results.append({
                'zoom': zoom,
                'success': True,
                'confidence': predicted['confidence'],
                'inliers': predicted['inliers'],
                'time_ms': elapsed_ms,
                'errors': errors,
                'collectibles_count': len(visible_collectibles),
                'ground_truth': gt,
                'predicted': predicted_normalized
            })

        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({
                'zoom': zoom,
                'success': False,
                'error': str(e)
            })

    # Summary statistics
    print("\n" + "="*80)
    print("ACCURACY SUMMARY")
    print("="*80)

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    # Exclude negative tests from success rate
    non_negative_results = [r for r in results if not r.get('negative_test', False)]
    successful_non_negative = [r for r in successful if not r.get('negative_test', False)]

    if non_negative_results:
        success_rate = len(successful_non_negative) / len(non_negative_results) * 100
        print(f"\nSuccess Rate: {len(successful_non_negative)}/{len(non_negative_results)} ({success_rate:.1f}%)")
    else:
        print(f"\nSuccess Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")

    if successful:
        position_errors = [r['errors']['position_error_pixels'] for r in successful]
        center_errors = [r['errors']['center_error_pixels'] for r in successful]

        print(f"\nPosition Error (pixels):")
        print(f"  Mean: {np.mean(position_errors):.2f} ± {np.std(position_errors):.2f}")
        print(f"  Min: {np.min(position_errors):.2f}, Max: {np.max(position_errors):.2f}")
        print(f"  Median: {np.median(position_errors):.2f}")

        print(f"\nCenter Error (pixels):")
        print(f"  Mean: {np.mean(center_errors):.2f} ± {np.std(center_errors):.2f}")
        print(f"  Min: {np.min(center_errors):.2f}, Max: {np.max(center_errors):.2f}")
        print(f"  Median: {np.median(center_errors):.2f}")

        # Accuracy thresholds
        threshold_5px = sum(1 for e in center_errors if e <= 5) / len(center_errors) * 100
        threshold_10px = sum(1 for e in center_errors if e <= 10) / len(center_errors) * 100
        threshold_20px = sum(1 for e in center_errors if e <= 20) / len(center_errors) * 100

        print(f"\nAccuracy at thresholds:")
        print(f"  <=5px:  {threshold_5px:.1f}%")
        print(f"  <=10px: {threshold_10px:.1f}%")
        print(f"  <=20px: {threshold_20px:.1f}%")

    if failed:
        failed_non_negative = [r for r in failed if not r.get('negative_test', False)]
        failed_negative = [r for r in failed if r.get('negative_test', False)]

        print(f"\nFailed tests: {len(failed_non_negative)}")
        for r in failed_non_negative:
            print(f"  - Zoom: {r['zoom']}, Error: {r.get('error', 'Unknown')}")

        if failed_negative:
            print(f"\nNegative tests (expected failures): {len(failed_negative)}")
            for r in failed_negative:
                print(f"  - Zoom: {r['zoom']}, Error: {r.get('error', 'Unknown')}")

        # Generate visualizations for failed tests
        if VISUALIZATIONS_AVAILABLE and failed_visualizations:
            print(f"\nGenerating visualizations for {len(failed_visualizations)} failed tests...")
            viz_dir = Path("tests/data/generated/failed_tests")
            viz_dir.mkdir(parents=True, exist_ok=True)

            for test_num, test_case in failed_visualizations:
                try:
                    output_path = visualize_failing_test(test_case, detection_map, matcher, test_num, viz_dir)
                    print(f"  Saved: {output_path.name}")
                except Exception as e:
                    print(f"  Failed to visualize test #{test_num}: {e}")

            print(f"Visualizations saved to: {viz_dir}")

    return results


def main():
    """Main test runner"""
    # Set random seed for repeatable tests
    np.random.seed(42)

    print("="*80)
    print("RDO Map Overlay - Accuracy & Performance Tests")
    print("="*80)

    # Initialize system
    print("\nInitializing system...")
    coord_transform = CoordinateTransform()

    # Load ORIGINAL map for generating test cases (simulates real screenshots)
    print("Loading ORIGINAL HQ map for test generation...")
    original_map = MapLoader.load_map(use_preprocessing=False, posterize_before_gray=False)
    if original_map is None:
        print("ERROR: Could not load original HQ map")
        print("Please ensure rdr2_map_hq.png exists in data/ directory")
        sys.exit(1)
    print(f"Original map loaded: {original_map.shape[1]}x{original_map.shape[0]}")

    # Load PREPROCESSED map for matching (reference for matching)
    print("Loading preprocessed HQ map for matching...")
    preprocessed_map = MapLoader.load_map(use_preprocessing=True, posterize_before_gray=False)
    if preprocessed_map is None:
        print("ERROR: Could not load preprocessed map")
        sys.exit(1)
    print(f"Preprocessed map loaded: {preprocessed_map.shape[1]}x{preprocessed_map.shape[0]}")

    # Resize to detection space (0.5x scale for matching)
    print("Resizing to detection space...")
    detection_map = cv2.resize(preprocessed_map,
                               (int(preprocessed_map.shape[1] * MAP_DIMENSIONS.DETECTION_SCALE),
                                int(preprocessed_map.shape[0] * MAP_DIMENSIONS.DETECTION_SCALE)),
                               interpolation=cv2.INTER_AREA)
    print(f"Detection map: {detection_map.shape[1]}x{detection_map.shape[0]}")

    # Initialize simple matcher
    print("Initializing simple AKAZE matcher...")
    matcher = SimpleMatcher(
        max_features=0,  # Keep all features (73k+)
        ratio_test_threshold=0.75,
        min_inliers=5,
        min_inlier_ratio=0.5,  # Require 50% of matches to be inliers
        ransac_threshold=5.0,
        use_spatial_distribution=True,
        spatial_grid_size=50,
        max_screenshot_features=300
    )

    # Pre-compute reference map features
    matcher.compute_reference_features(detection_map)

    # Initialize validator first (needed for test generation)
    validator = AccuracyValidator(coord_transform)
    print("\nLoading collectibles data from Joan Ropke API...")
    validator.load_collectibles_data()

    # Generate test cases from ORIGINAL map (simulates real screenshots)
    print("\nGenerating synthetic test cases from ORIGINAL map...")
    generator = SyntheticTestGenerator(original_map)

    test_cases = []
    # Realistic zoom levels from max zoom out (50% of map) to max zoom in (870x370)
    zoom_levels = ['max_zoom_out', 'far', 'medium', 'close', 'max_zoom_in']
    tests_per_zoom = 3  # 5 zoom levels × 3 tests = 15 total (reduced for speed)

    negative_test_added = False
    for zoom in zoom_levels:
        print(f"  Generating {tests_per_zoom} test cases for zoom level: {zoom}")
        for i in range(tests_per_zoom):
            # Last test is the negative case (no collectibles expected)
            is_negative_test = (zoom == 'max_zoom_in' and i == 1 and not negative_test_added)

            if is_negative_test:
                # Generate without collectible requirement (negative test)
                test_case = generator.generate_test_case(zoom, require_collectibles=False)
                test_case['negative_test'] = True
                test_case['negative_reason'] = 'No collectibles in area - detection may fail'
                negative_test_added = True
                print(f"    Generated NEGATIVE test (no collectibles expected)")
            else:
                # Generate with collectibles
                test_case = generator.generate_test_case(zoom, require_collectibles=True,
                                                        validator=validator, max_attempts=20)
                test_case['negative_test'] = False

            test_cases.append(test_case)

    print(f"\nGenerated {len(test_cases)} test cases (within explorable bounds, repeatable with seed=42)")

    # Run tests
    print("\n" + "="*80)
    print("STARTING TESTS")
    print("="*80)

    # Accuracy tests
    accuracy_results = run_accuracy_tests(matcher, detection_map, test_cases, validator)

    # Performance benchmark
    performance_results = run_performance_benchmark(matcher, detection_map, test_cases, num_iterations=5)

    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
