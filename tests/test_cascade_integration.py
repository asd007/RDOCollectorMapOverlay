"""
Integration test for CascadeScaleMatcher with TranslationTracker.
Validates that motion prediction works end-to-end with the cascade matcher.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching.simple_matcher import SimpleMatcher
from config.paths import CachePaths
from core.matching.image_preprocessing import preprocess_with_resize


def test_cascade_with_motion_prediction():
    """Test cascade matcher with motion prediction enabled."""
    print("\n" + "="*80)
    print("INTEGRATION TEST: CascadeScaleMatcher + TranslationTracker")
    print("="*80)

    # Load HQ map
    hq_map_path = CachePaths.find_hq_map_source()
    if not hq_map_path or not hq_map_path.exists():
        print("ERROR: HQ map not found!")
        return

    print(f"\nLoading and preprocessing HQ map...")
    hq_map = cv2.imread(str(hq_map_path))
    detection_map = preprocess_with_resize(hq_map, scale=0.5)
    print(f"Detection map: {detection_map.shape[1]}×{detection_map.shape[0]}")

    # Initialize base matcher
    print("\nInitializing base matcher...")
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
    print(f"Map features: {len(base_matcher.kp_map)}")

    # Create cascade configuration (same as app.py)
    cascade_levels = [
        ScaleConfig(
            scale=0.25,
            max_features=100,
            min_confidence=0.50,
            min_inliers=6,
            min_matches=12,
            name="Fast (25%)"
        ),
        ScaleConfig(
            scale=0.5,
            max_features=150,
            min_confidence=0.45,
            min_inliers=5,
            min_matches=10,
            name="Reliable (50%)"
        ),
        ScaleConfig(
            scale=1.0,
            max_features=300,
            min_confidence=0.0,
            min_inliers=5,
            min_matches=8,
            name="Full Resolution (100%)"
        )
    ]

    print("\nInitializing cascade matcher with motion prediction...")
    cascade_matcher = CascadeScaleMatcher(
        base_matcher,
        cascade_levels,
        use_scale_prediction=False,
        verbose=True,
        enable_roi_tracking=True
    )

    # Generate test sequence with known movements
    print("\nGenerating test sequence...")
    from tests.test_translation_tracker import SyntheticTestDataGenerator

    generator = SyntheticTestDataGenerator(str(hq_map_path))

    # Small movements (typical for inter-frame motion)
    movements = [
        (15, 10),   # Small movement
        (20, -15),  # Small movement
        (10, 5),    # Tiny movement
        (-12, 8),   # Small negative
        (25, -20),  # Medium movement
    ]

    sequence = generator.generate_translation_sequence(10000, 8000, movements, zoom=1.0)

    # Process sequence with cascade matcher
    print("\nProcessing sequence with motion prediction...")
    print("-"*80)

    for i, (frame, dx_true, dy_true) in enumerate(sequence):
        # Preprocess frame (convert to grayscale, apply preprocessing)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)  # Convert to BGR for preprocessing

        # Match with cascade
        result = cascade_matcher.match(frame_gray)

        if not result['success']:
            print(f"Frame {i}: FAILED - {result.get('error', 'Unknown error')}")
            continue

        # Get motion prediction info
        cascade_info = result.get('cascade_info', {})
        motion_pred = cascade_info.get('motion_prediction')
        prediction_ms = cascade_info.get('prediction_ms', 0)
        prediction_used = cascade_info.get('prediction_used', False)
        roi_used = cascade_info.get('roi_used', False)

        # Print results
        level_used = cascade_info.get('final_level', 'Unknown')

        print(f"\nFrame {i}: "
              f"confidence={result['confidence']:.3f}, "
              f"inliers={result['inliers']}, "
              f"level={level_used}")

        if motion_pred:
            offset_px = motion_pred['offset_px']
            phase_conf = motion_pred['phase_confidence']
            print(f"  Motion prediction: offset=({offset_px[0]:.1f}, {offset_px[1]:.1f})px, "
                  f"phase_conf={phase_conf:.3f}, "
                  f"time={prediction_ms:.2f}ms")
            print(f"  Ground truth: ({dx_true:.1f}, {dy_true:.1f})px")

            # Calculate error
            error = np.sqrt((dx_true - offset_px[0])**2 + (dy_true - offset_px[1])**2)
            print(f"  Prediction error: {error:.2f}px")

        print(f"  ROI used: {roi_used}, Prediction used: {prediction_used}")

    print("\n" + "="*80)
    print("Integration test completed!")
    print("="*80)


if __name__ == '__main__':
    test_cascade_with_motion_prediction()
