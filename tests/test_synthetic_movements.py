"""
Synthetic test for realistic map movements.

Simulates realistic mouse drag patterns (smooth, fast, zoom) to validate:
1. Backend matching performance (should hit 60 FPS easily)
2. Frontend rendering smoothness
3. Collectible positioning accuracy

Test scenarios:
- Slow smooth pan (simulates careful map browsing)
- Fast pan (simulates quick navigation)
- Zoom in/out (separate from pan, PC-typical)
- Deceleration (mouse drag release)
"""

import cv2
import numpy as np
import time
import json
from pathlib import Path
from typing import List, Tuple, Dict
from dataclasses import dataclass, asdict

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAP_DIMENSIONS
from core import MapLoader, CoordinateTransform
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching import SimpleMatcher
from core.image_preprocessing import preprocess_with_resize


@dataclass
class MouseMovement:
    """Represents a realistic mouse movement pattern"""
    name: str
    duration_ms: int  # Total duration
    start_pos: Tuple[int, int]  # Map position (detection space)
    movement_type: str  # 'pan' or 'zoom'
    # For pan
    end_pos: Tuple[int, int] = None
    easing: str = 'linear'  # 'linear', 'ease_out', 'ease_in_out'
    # For zoom
    zoom_start: float = None  # Viewport width in detection space
    zoom_end: float = None
    zoom_center: Tuple[int, int] = None  # Zoom focal point


def generate_mouse_trajectory(movement: MouseMovement, fps: int = 60) -> List[Dict]:
    """
    Generate realistic frame-by-frame mouse positions.

    Args:
        movement: Movement pattern definition
        fps: Target framerate for trajectory

    Returns:
        List of viewport states (one per frame)
    """
    num_frames = int((movement.duration_ms / 1000) * fps)
    frames = []

    if movement.movement_type == 'pan':
        start_x, start_y = movement.start_pos
        end_x, end_y = movement.end_pos

        for i in range(num_frames):
            t = i / max(num_frames - 1, 1)  # 0 to 1

            # Apply easing function
            if movement.easing == 'ease_out':
                # Deceleration (fast start, slow end)
                t = 1 - (1 - t) ** 2
            elif movement.easing == 'ease_in_out':
                # Smooth S-curve
                t = t * t * (3 - 2 * t)
            # else: linear (t unchanged)

            # Interpolate position
            current_x = start_x + (end_x - start_x) * t
            current_y = start_y + (end_y - start_y) * t

            # Fixed viewport size for pan (no zoom)
            viewport_w = 3000  # Typical viewport width in detection space
            viewport_h = 2250  # 3:4 aspect ratio (matches 1920x1080 with 0.5 scale)

            frames.append({
                'viewport_x': current_x,
                'viewport_y': current_y,
                'viewport_w': viewport_w,
                'viewport_h': viewport_h,
                'frame_idx': i,
                'time_ms': (i / fps) * 1000
            })

    elif movement.movement_type == 'zoom':
        center_x, center_y = movement.zoom_center

        for i in range(num_frames):
            t = i / max(num_frames - 1, 1)

            # Apply easing
            if movement.easing == 'ease_in_out':
                t = t * t * (3 - 2 * t)

            # Interpolate zoom level
            current_w = movement.zoom_start + (movement.zoom_end - movement.zoom_start) * t
            current_h = current_w * 0.75  # Maintain aspect ratio

            # Keep zoom centered on focal point
            frames.append({
                'viewport_x': center_x - current_w / 2,
                'viewport_y': center_y - current_h / 2,
                'viewport_w': current_w,
                'viewport_h': current_h,
                'frame_idx': i,
                'time_ms': (i / fps) * 1000
            })

    return frames


def create_synthetic_screenshot(map_img: np.ndarray, viewport: Dict) -> np.ndarray:
    """
    Extract viewport from map to simulate screenshot.

    Args:
        map_img: Full detection-scale map
        viewport: Viewport dict with x, y, width, height

    Returns:
        Synthetic screenshot (1920x1080)
    """
    # Extract viewport region from map
    x = int(viewport['viewport_x'])
    y = int(viewport['viewport_y'])
    w = int(viewport['viewport_w'])
    h = int(viewport['viewport_h'])

    # Clamp to map bounds
    map_h, map_w = map_img.shape[:2]
    x = max(0, min(x, map_w - w))
    y = max(0, min(y, map_h - h))

    # Extract region
    viewport_img = map_img[y:y+h, x:x+w].copy()

    # Resize to 1920x1080 (screen resolution)
    screenshot = cv2.resize(viewport_img, (1920, 1080), interpolation=cv2.INTER_LINEAR)

    # Convert to BGR if grayscale
    if len(screenshot.shape) == 2:
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_GRAY2BGR)

    return screenshot


def run_movement_test(
    matcher: CascadeScaleMatcher,
    map_img: np.ndarray,
    movement: MouseMovement,
    output_dir: Path
) -> Dict:
    """
    Run synthetic test for a movement pattern.

    Returns:
        Performance metrics
    """
    print(f"\n{'='*60}")
    print(f"Testing: {movement.name}")
    print(f"{'='*60}")

    trajectory = generate_mouse_trajectory(movement, fps=60)
    print(f"Generated {len(trajectory)} frames ({movement.duration_ms}ms @ 60 FPS)")

    results = []
    match_times = []

    for frame_data in trajectory:
        # Create synthetic screenshot
        screenshot = create_synthetic_screenshot(map_img, frame_data)

        # Perform matching
        start_time = time.time()
        result = matcher.match(screenshot)
        match_time = (time.time() - start_time) * 1000

        match_times.append(match_time)

        # Validate result
        if result and result.get('success'):
            # Calculate error (detected vs expected)
            expected_x = frame_data['viewport_x']
            expected_y = frame_data['viewport_y']
            detected_x = result['map_x']
            detected_y = result['map_y']

            error_x = abs(detected_x - expected_x)
            error_y = abs(detected_y - expected_y)
            error_total = np.sqrt(error_x**2 + error_y**2)

            cascade_info = result.get('cascade_info', {})

            results.append({
                'frame_idx': frame_data['frame_idx'],
                'time_ms': frame_data['time_ms'],
                'match_time_ms': match_time,
                'success': True,
                'error_x': error_x,
                'error_y': error_y,
                'error_total': error_total,
                'confidence': result['confidence'],
                'cascade_level': cascade_info.get('final_level', 'unknown'),
                'prediction_used': cascade_info.get('prediction_used', False),
                'roi_used': cascade_info.get('roi_used', False)
            })
        else:
            results.append({
                'frame_idx': frame_data['frame_idx'],
                'time_ms': frame_data['time_ms'],
                'match_time_ms': match_time,
                'success': False,
                'error': result.get('error', 'Unknown') if result else 'Matcher returned None'
            })

    # Calculate statistics
    successful_results = [r for r in results if r.get('success')]

    if successful_results:
        match_times_success = [r['match_time_ms'] for r in successful_results]
        errors = [r['error_total'] for r in successful_results]

        stats = {
            'movement_name': movement.name,
            'total_frames': len(trajectory),
            'successful_frames': len(successful_results),
            'success_rate': len(successful_results) / len(trajectory),
            'match_time_mean': np.mean(match_times_success),
            'match_time_median': np.median(match_times_success),
            'match_time_p95': np.percentile(match_times_success, 95),
            'match_time_max': np.max(match_times_success),
            'achieved_fps': 1000 / np.mean(match_times_success) if match_times_success else 0,
            'error_mean': np.mean(errors),
            'error_median': np.median(errors),
            'error_p95': np.percentile(errors, 95),
            'error_max': np.max(errors),
            'prediction_used_count': sum(1 for r in successful_results if r.get('prediction_used')),
            'roi_used_count': sum(1 for r in successful_results if r.get('roi_used'))
        }

        print(f"\n{'='*60}")
        print(f"Results: {movement.name}")
        print(f"{'='*60}")
        print(f"Success Rate:  {stats['success_rate']*100:.1f}%")
        print(f"Match Time:    {stats['match_time_mean']:.1f}ms avg, "
              f"{stats['match_time_median']:.1f}ms median, "
              f"{stats['match_time_p95']:.1f}ms P95, "
              f"{stats['match_time_max']:.1f}ms max")
        print(f"Achieved FPS:  {stats['achieved_fps']:.1f}")
        print(f"Position Error: {stats['error_mean']:.1f}px avg, "
              f"{stats['error_median']:.1f}px median, "
              f"{stats['error_p95']:.1f}px P95")
        print(f"Prediction:    {stats['prediction_used_count']}/{len(successful_results)} frames")
        print(f"ROI Tracking:  {stats['roi_used_count']}/{len(successful_results)} frames")

        # Save detailed results
        output_file = output_dir / f"{movement.name.replace(' ', '_')}_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                'stats': stats,
                'frames': results
            }, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")

        return stats
    else:
        print(f"\nERROR: All frames failed matching!")
        return None


def main():
    """Run synthetic movement tests"""
    print("Initializing synthetic movement test...")

    # Load map
    from config.paths import CachePaths
    hq_source = CachePaths.find_hq_map_source()
    if not hq_source or not hq_source.exists():
        print("ERROR: HQ map not found!")
        return

    hq_map = cv2.imread(str(hq_source))
    detection_map = preprocess_with_resize(hq_map, scale=MAP_DIMENSIONS.DETECTION_SCALE)
    print(f"Map loaded: {detection_map.shape[1]}x{detection_map.shape[0]}")

    # Initialize matcher
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
        ScaleConfig(scale=0.25, max_features=100, min_confidence=0.50, min_inliers=6, min_matches=12, name="Fast (25%)"),
        ScaleConfig(scale=0.5, max_features=150, min_confidence=0.45, min_inliers=5, min_matches=10, name="Reliable (50%)"),
        ScaleConfig(scale=1.0, max_features=300, min_confidence=0.0, min_inliers=5, min_matches=8, name="Full Resolution (100%)")
    ]

    matcher = CascadeScaleMatcher(
        base_matcher,
        cascade_levels,
        use_scale_prediction=False,
        verbose=False,
        enable_roi_tracking=True
    )

    # Create output directory
    output_dir = Path(__file__).parent / 'synthetic_movement_results'
    output_dir.mkdir(exist_ok=True)

    # Define realistic movement patterns
    map_center = (detection_map.shape[1] // 2, detection_map.shape[0] // 2)

    movements = [
        # 1. Slow smooth pan (browsing map)
        MouseMovement(
            name="slow_smooth_pan",
            duration_ms=2000,
            start_pos=(3000, 3000),
            end_pos=(5000, 4000),
            movement_type='pan',
            easing='linear'
        ),

        # 2. Fast pan (quick navigation)
        MouseMovement(
            name="fast_pan",
            duration_ms=800,
            start_pos=(2000, 2000),
            end_pos=(7000, 5000),
            movement_type='pan',
            easing='linear'
        ),

        # 3. Pan with deceleration (mouse release)
        MouseMovement(
            name="pan_deceleration",
            duration_ms=1500,
            start_pos=(4000, 3000),
            end_pos=(6500, 4500),
            movement_type='pan',
            easing='ease_out'
        ),

        # 4. Smooth pan (S-curve easing)
        MouseMovement(
            name="smooth_pan_ease",
            duration_ms=1200,
            start_pos=(3500, 4000),
            end_pos=(5500, 3000),
            movement_type='pan',
            easing='ease_in_out'
        ),

        # 5. Zoom in (scroll wheel)
        MouseMovement(
            name="zoom_in",
            duration_ms=800,
            start_pos=None,
            movement_type='zoom',
            zoom_start=3000,
            zoom_end=1500,
            zoom_center=map_center,
            easing='ease_in_out'
        ),

        # 6. Zoom out
        MouseMovement(
            name="zoom_out",
            duration_ms=800,
            start_pos=None,
            movement_type='zoom',
            zoom_start=1500,
            zoom_end=3500,
            zoom_center=map_center,
            easing='ease_in_out'
        )
    ]

    # Run tests
    all_stats = []
    for movement in movements:
        stats = run_movement_test(matcher, detection_map, movement, output_dir)
        if stats:
            all_stats.append(stats)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for stats in all_stats:
        print(f"{stats['movement_name']:20s}: {stats['achieved_fps']:5.1f} FPS, "
              f"{stats['error_mean']:5.1f}px error, "
              f"{stats['success_rate']*100:5.1f}% success")


if __name__ == '__main__':
    main()
