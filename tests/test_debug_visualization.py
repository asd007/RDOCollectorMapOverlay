#!/usr/bin/env python3
"""
Debug visualization for AKAZE feature detection and matching failures.
Creates visual outputs to understand why tests fail.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from config import MAP_DIMENSIONS
from core import MapLoader
from core.image_preprocessing import preprocess_for_matching
from matching.simple_matcher import SimpleMatcher
from tests.test_matching import SyntheticTestGenerator


def visualize_reference_map_keypoints(detection_map: np.ndarray, matcher: SimpleMatcher, output_path: Path):
    """Visualize the reference map with all detected AKAZE keypoints"""
    print("Creating reference map keypoint visualization...")

    # Get keypoints
    if hasattr(matcher, 'kp_map'):
        kp_map = matcher.kp_map
    else:
        print("ERROR: Matcher doesn't have pre-computed keypoints")
        return

    # Create RGB version for drawing
    map_rgb = cv2.cvtColor(detection_map, cv2.COLOR_GRAY2RGB)

    # Draw all keypoints
    map_with_kp = cv2.drawKeypoints(
        map_rgb, kp_map, None,
        color=(0, 255, 0),  # Green keypoints
        flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
    )

    # Create figure with full map
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))

    # Original map
    axes[0].imshow(detection_map, cmap='gray')
    axes[0].set_title(f'Detection Map (Preprocessed)\n{detection_map.shape[1]}x{detection_map.shape[0]}')
    axes[0].axis('off')

    # Map with keypoints
    axes[1].imshow(map_with_kp)
    axes[1].set_title(f'AKAZE Keypoints ({len(kp_map)} features)\nGreen = detected keypoints')
    axes[1].axis('off')

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved reference map visualization to: {output_path}")

    # Also create a zoomed-in version showing keypoint density
    create_keypoint_density_map(detection_map, kp_map, output_path.parent / "reference_keypoint_density.png")


def create_keypoint_density_map(detection_map: np.ndarray, keypoints, output_path: Path):
    """Create a heatmap showing keypoint density across the map"""
    print("Creating keypoint density heatmap...")

    # Create density grid
    grid_size = 50  # pixels per grid cell
    grid_h = detection_map.shape[0] // grid_size + 1
    grid_w = detection_map.shape[1] // grid_size + 1
    density = np.zeros((grid_h, grid_w))

    # Count keypoints in each grid cell
    for kp in keypoints:
        x, y = kp.pt
        grid_x = min(int(x / grid_size), grid_w - 1)
        grid_y = min(int(y / grid_size), grid_h - 1)
        density[grid_y, grid_x] += 1

    # Visualize
    fig, ax = plt.subplots(1, 1, figsize=(15, 12))
    im = ax.imshow(density, cmap='hot', interpolation='nearest')
    ax.set_title(f'AKAZE Keypoint Density Heatmap\n(Grid: {grid_size}x{grid_size} pixels)')
    ax.set_xlabel('Grid X')
    ax.set_ylabel('Grid Y')
    plt.colorbar(im, ax=ax, label='Keypoint Count')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved density heatmap to: {output_path}")


def visualize_failing_test(
    test_case: dict,
    detection_map: np.ndarray,
    matcher: SimpleMatcher,
    test_num: int,
    output_dir: Path
):
    """Visualize a failing test case to understand why it failed"""

    # Preprocess screenshot
    screenshot_gray = test_case['image']
    screenshot_preprocessed = preprocess_for_matching(screenshot_gray, posterize_before_gray=False)

    # Detect features on screenshot
    detector = cv2.AKAZE_create()
    detector.setThreshold(0.001)
    kp_screenshot, desc_screenshot = detector.detectAndCompute(screenshot_preprocessed, None)

    # Get ground truth region from detection map
    gt = test_case['ground_truth']
    x1, y1 = gt['detection_x'], gt['detection_y']
    x2, y2 = x1 + gt['detection_w'], y1 + gt['detection_h']

    # Ensure bounds are valid
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(detection_map.shape[1], x2)
    y2 = min(detection_map.shape[0], y2)

    gt_region = detection_map[y1:y2, x1:x2]

    # Detect features on ground truth region
    kp_gt_region, desc_gt_region = detector.detectAndCompute(gt_region, None)

    # Try matching
    result = matcher.match(screenshot_preprocessed)

    # Create visualization
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Row 1: Original images
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.imshow(screenshot_gray, cmap='gray')
    ax1.set_title(f'Test #{test_num} - Original Screenshot\nZoom: {gt["zoom_level"]}, Coverage: {gt["map_coverage_percent"]:.2f}%')
    ax1.axis('off')

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(screenshot_preprocessed, cmap='gray')
    ax2.set_title(f'Preprocessed Screenshot\n(Q10: Posterize + CLAHE)')
    ax2.axis('off')

    ax3 = fig.add_subplot(gs[0, 2])
    # Show ground truth region on full map (and predicted if available)
    map_copy = detection_map.copy()
    map_rgb = cv2.cvtColor(map_copy, cv2.COLOR_GRAY2RGB)
    # Ground truth in green
    cv2.rectangle(map_rgb, (x1, y1), (x2, y2), (0, 255, 0), 3)
    # Predicted in red (if match succeeded)
    if result['success']:
        pred_x1 = result['map_x']
        pred_y1 = result['map_y']
        pred_x2 = pred_x1 + result['map_w']
        pred_y2 = pred_y1 + result['map_h']
        cv2.rectangle(map_rgb, (pred_x1, pred_y1), (pred_x2, pred_y2), (255, 0, 0), 2)
    ax3.imshow(map_rgb)
    title = f'Ground Truth (Green) vs Predicted (Red)\n({gt["detection_w"]}x{gt["detection_h"]} pixels)'
    ax3.set_title(title)
    ax3.axis('off')

    # Row 2: With keypoints
    ax4 = fig.add_subplot(gs[1, 0])
    if kp_screenshot and len(kp_screenshot) > 0:
        screenshot_rgb = cv2.cvtColor(screenshot_preprocessed, cv2.COLOR_GRAY2RGB)
        screenshot_with_kp = cv2.drawKeypoints(
            screenshot_rgb, kp_screenshot, None,
            color=(0, 255, 0),
            flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
        )
        ax4.imshow(screenshot_with_kp)
        ax4.set_title(f'Screenshot Keypoints: {len(kp_screenshot)} features')
    else:
        ax4.imshow(screenshot_preprocessed, cmap='gray')
        ax4.set_title('Screenshot Keypoints: 0 features ❌')
    ax4.axis('off')

    ax5 = fig.add_subplot(gs[1, 1])
    if kp_gt_region and len(kp_gt_region) > 0:
        gt_rgb = cv2.cvtColor(gt_region, cv2.COLOR_GRAY2RGB)
        gt_with_kp = cv2.drawKeypoints(
            gt_rgb, kp_gt_region, None,
            color=(255, 0, 0),
            flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
        )
        ax5.imshow(gt_with_kp)
        ax5.set_title(f'Ground Truth Region Keypoints: {len(kp_gt_region)} features')
    else:
        ax5.imshow(gt_region, cmap='gray')
        ax5.set_title('Ground Truth Region Keypoints: 0 features ❌')
    ax5.axis('off')

    ax6 = fig.add_subplot(gs[1, 2])
    # Show matched features if available
    if result['success'] and kp_screenshot and desc_screenshot is not None and len(kp_screenshot) > 0:
        # Re-do the matching to get match objects
        if matcher.kp_map and matcher.desc_map is not None and len(matcher.kp_map) > 0:
            bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf_matcher.knnMatch(desc_screenshot, matcher.desc_map, k=2)

            # Apply ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

            # Draw matches (sample up to 50 for clarity)
            sample_matches = good_matches[:50] if len(good_matches) > 50 else good_matches

            # Create small versions for visualization
            screenshot_rgb_small = cv2.cvtColor(screenshot_preprocessed, cv2.COLOR_GRAY2RGB)
            map_region_rgb_small = cv2.cvtColor(gt_region, cv2.COLOR_GRAY2RGB)

            match_img = cv2.drawMatches(
                screenshot_rgb_small, kp_screenshot,
                map_region_rgb_small, kp_gt_region,
                sample_matches[:20], None,  # Show only 20 matches for clarity
                flags=cv2.DRAW_MATCHES_FLAGS_NOT_DRAW_SINGLE_POINTS
            )
            ax6.imshow(match_img)
            ax6.set_title(f'Feature Matches (showing 20/{len(good_matches)})\nGreen lines = matched features')
            ax6.axis('off')
        else:
            ax6.axis('off')
            info_text = f"Match Result: Success\nBut matcher features not available for visualization"
            ax6.text(0.1, 0.5, info_text, transform=ax6.transAxes,
                    fontsize=12, verticalalignment='center',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                    family='monospace')
    else:
        ax6.axis('off')
        # Show matching info
        info_text = f"Match Result:\n"
        info_text += f"Success: {result['success']}\n\n"
        if result['success']:
            info_text += f"Confidence: {result['confidence']:.1%}\n"
            info_text += f"Inliers: {result['inliers']}\n"
            info_text += f"Predicted: ({result['map_x']}, {result['map_y']})\n"
            info_text += f"Ground Truth: ({x1}, {y1})\n"
            info_text += f"Error: {np.sqrt((result['map_x']-x1)**2 + (result['map_y']-y1)**2):.1f}px"
        else:
            info_text += f"Error: {result.get('error', 'Unknown')}\n\n"
            info_text += f"Screenshot features: {len(kp_screenshot) if kp_screenshot else 0}\n"
            info_text += f"GT region features: {len(kp_gt_region) if kp_gt_region else 0}\n"

        ax6.text(0.1, 0.5, info_text, transform=ax6.transAxes,
                fontsize=12, verticalalignment='center',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                family='monospace')

    # Row 3: Histograms
    ax7 = fig.add_subplot(gs[2, 0])
    ax7.hist(screenshot_preprocessed.ravel(), bins=50, alpha=0.7, color='blue')
    ax7.set_title('Screenshot Pixel Intensity Distribution')
    ax7.set_xlabel('Pixel Value')
    ax7.set_ylabel('Count')

    ax8 = fig.add_subplot(gs[2, 1])
    ax8.hist(gt_region.ravel(), bins=50, alpha=0.7, color='red')
    ax8.set_title('GT Region Pixel Intensity Distribution')
    ax8.set_xlabel('Pixel Value')
    ax8.set_ylabel('Count')

    ax9 = fig.add_subplot(gs[2, 2])
    if kp_screenshot and len(kp_screenshot) > 0:
        responses = [kp.response for kp in kp_screenshot]
        ax9.hist(responses, bins=30, alpha=0.7, color='green')
        ax9.set_title(f'Screenshot Keypoint Strengths\nMean: {np.mean(responses):.4f}')
        ax9.set_xlabel('Response (strength)')
        ax9.set_ylabel('Count')
    else:
        ax9.text(0.5, 0.5, 'No keypoints detected',
                transform=ax9.transAxes, ha='center', va='center')
        ax9.set_title('Keypoint Strengths')

    # Save
    output_path = output_dir / f"test_{test_num:03d}_{gt['zoom_level']}_FAIL.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return output_path


def main():
    """Generate debug visualizations"""
    print("="*80)
    print("AKAZE FEATURE DETECTION DEBUG VISUALIZATION")
    print("="*80)

    output_dir = Path("tests/data/generated/debug_visualizations")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load maps
    print("\nLoading maps...")
    original_map = MapLoader.load_map(use_preprocessing=False, posterize_before_gray=False)
    preprocessed_map = MapLoader.load_map(use_preprocessing=True, posterize_before_gray=False)

    # Resize to detection space
    detection_map = cv2.resize(preprocessed_map,
                               (int(preprocessed_map.shape[1] * MAP_DIMENSIONS.DETECTION_SCALE),
                                int(preprocessed_map.shape[0] * MAP_DIMENSIONS.DETECTION_SCALE)),
                               interpolation=cv2.INTER_AREA)

    # Initialize matcher and compute reference features
    print("Initializing matcher...")
    matcher = SimpleMatcher(
        max_features=0,  # Keep all features
        ratio_test_threshold=0.75,
        min_inliers=5,
        min_inlier_ratio=0.5,
        ransac_threshold=5.0,
        use_spatial_distribution=True,
        spatial_grid_size=50,
        max_screenshot_features=300
    )
    matcher.compute_reference_features(detection_map)

    # Visualize reference map keypoints
    visualize_reference_map_keypoints(
        detection_map, matcher,
        output_dir / "reference_map_keypoints.png"
    )

    # Generate test cases
    print("\nGenerating test cases...")
    generator = SyntheticTestGenerator(original_map)

    # Focus on failing zoom levels
    test_cases = []
    for zoom in ['medium', 'close', 'max_zoom_in']:
        print(f"  Generating tests for: {zoom}")
        for i in range(5):  # 5 tests per zoom level
            test_case = generator.generate_test_case(zoom)
            test_cases.append(test_case)

    # Visualize each test case
    print(f"\nVisualizing {len(test_cases)} test cases...")
    for i, test_case in enumerate(test_cases, 1):
        result = matcher.match(
            preprocess_for_matching(test_case['image'], posterize_before_gray=False)
        )

        # Visualize all tests (both passing and failing) to compare
        print(f"  Test {i}/{len(test_cases)}: {test_case['ground_truth']['zoom_level']} - "
              f"{'SUCCESS' if result['success'] else 'FAIL'}")

        output_path = visualize_failing_test(
            test_case, detection_map, matcher, i, output_dir
        )

    print("\n" + "="*80)
    print("DEBUG VISUALIZATIONS COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {output_dir}")
    print("\nGenerated files:")
    print("  - reference_map_keypoints.png: Full map with all AKAZE keypoints")
    print("  - reference_keypoint_density.png: Heatmap of keypoint density")
    print("  - test_XXX_ZOOM_FAIL.png: Individual test visualizations")
    print("\nAnalyze these images to understand:")
    print("  1. Where keypoints are concentrated on the map")
    print("  2. Why certain test regions have no features")
    print("  3. How preprocessing affects feature detection")


if __name__ == '__main__':
    main()
