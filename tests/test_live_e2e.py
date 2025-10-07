#!/usr/bin/env python3
"""
E2E Live Screenshot Test Tool

Interactive tool to test the current game screenshot in real-time.
Captures ONE frame from the game window, runs through the full matching pipeline, and displays results.

Usage:
    python tests/test_live_e2e.py                    # Single frame capture and test
    python tests/test_live_e2e.py --save-results     # Save screenshots and results
    python tests/test_live_e2e.py --visualize        # Draw collectibles on screenshot
    python tests/test_live_e2e.py --show             # Display annotated image in window
    python tests/test_live_e2e.py --verbose          # Detailed logging
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import win32gui
from windows_capture import WindowsCapture, Frame, InternalCaptureControl

from config import MAP_DIMENSIONS
from config.paths import CachePaths
from core.matching.image_preprocessing import preprocess_with_resize
from core.collectibles.collectibles_repository import CollectiblesRepository
from core.collectibles.collectibles_filter import filter_visible_collectibles
from core.map.coordinate_transform import CoordinateTransform
from matching.cascade_scale_matcher import CascadeScaleMatcher, ScaleConfig
from matching.simple_matcher import SimpleMatcher


class LiveE2ETest:
    """End-to-end test tool for live game screenshots."""

    # Color mapping for different collectible types (BGR format)
    COLLECTIBLE_COLORS = {
        'card_tarot': (255, 100, 100),      # Light blue
        'card_set': (255, 150, 50),         # Cyan
        'coin': (0, 215, 255),              # Gold
        'arrowhead': (100, 100, 255),       # Light red
        'jewelry': (255, 0, 255),           # Magenta
        'bottle': (50, 200, 50),            # Green
        'egg': (200, 200, 200),             # Light gray
        'flower': (150, 100, 255),          # Pink
        'heirlooms': (0, 165, 255),         # Orange
        'default': (0, 255, 0)              # Green (fallback)
    }

    def __init__(self, verbose: bool = False, save_results: bool = False,
                 visualize: bool = False, show_window: bool = False):
        """Initialize the E2E test tool."""
        self.verbose = verbose
        self.save_results = save_results
        self.visualize = visualize
        self.show_window = show_window
        self.output_dir = Path("tests/e2e_results")
        self.rdr2_window_title = None

        # Windows Capture API state
        self.game_capture = None
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.frame_count = 0

        if save_results or visualize:
            self.output_dir.mkdir(exist_ok=True)

        # Find RDR2 window
        self.rdr2_window_title = self._find_rdr2_window()
        if self.rdr2_window_title:
            print(f"[Windows Capture] Found RDR2 window: {self.rdr2_window_title}")
        else:
            raise RuntimeError("RDR2 window not found! Make sure the game is running and the map is open.")

        print("Initializing E2E test tool...")
        self._initialize_capture()
        self._initialize_matcher()
        self._initialize_collectibles()
        print("Initialization complete!\n")

    def _find_rdr2_window(self) -> Optional[str]:
        """Find Red Dead Redemption 2 window by title."""
        windows = []

        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append({'hwnd': hwnd, 'title': title})

        win32gui.EnumWindows(enum_handler, None)

        # Look for RDR2 window
        for window in windows:
            if "Red Dead Redemption" in window['title']:
                return window['title']

        return None

    def _initialize_capture(self):
        """Initialize Windows Capture API (continuous capture like app_qml.py)."""
        print("Starting Windows Capture API...")

        self.game_capture = WindowsCapture(
            window_name=self.rdr2_window_title,
            cursor_capture=False,
            minimum_update_interval=16
        )

        @self.game_capture.event
        def on_frame_arrived(frame, capture_control):
            with self.frame_lock:
                self.latest_frame = frame.frame_buffer.copy()
                self.frame_count += 1
                if self.frame_count == 1:
                    print(f"  [SUCCESS] First frame received ({frame.frame_buffer.shape})")

        @self.game_capture.event
        def on_closed():
            print("  [WARN] Game window closed")

        self.game_capture.start_free_threaded()
        print("  Windows Capture started, waiting for first frame...")

        # Wait for first frame
        max_wait = 2.0
        wait_interval = 0.01
        elapsed = 0

        while self.latest_frame is None and elapsed < max_wait:
            time.sleep(wait_interval)
            elapsed += wait_interval

        if self.latest_frame is None:
            raise RuntimeError(f"No frame captured after {max_wait}s. Make sure game window is visible.")

    def _initialize_matcher(self):
        """Initialize the cascade matcher using same cache as application."""
        print("Loading map and initializing matcher...")

        # Load HQ map
        hq_source = CachePaths.find_hq_map_source()
        if not hq_source or not hq_source.exists():
            raise FileNotFoundError("HQ map not found!")

        # Use feature cache (same as app_qml.py)
        from core.map.feature_cache import FeatureCache

        cache_params = {
            'scale': MAP_DIMENSIONS.DETECTION_SCALE,
            'max_features': 0,
            'use_spatial_distribution': True,
            'spatial_grid_size': 50
        }

        cache_paths = CachePaths()
        feature_cache = FeatureCache(cache_paths.CACHE_DIR)
        cached_data = feature_cache.load(hq_source, cache_params)

        if cached_data:
            print("  [CACHE] Loading preprocessed map and features from cache...")
            self.detection_map, keypoint_data, descriptors = cached_data
            keypoints = FeatureCache.keypoints_from_data(keypoint_data)
            print(f"  [CACHE] Loaded {len(keypoints)} features from cache")
            print(f"  Detection map: {self.detection_map.shape[1]}x{self.detection_map.shape[0]}")
        else:
            print("  [CACHE] No valid cache found, computing features...")
            hq_map = cv2.imread(str(hq_source))
            self.detection_map = preprocess_with_resize(hq_map, scale=MAP_DIMENSIONS.DETECTION_SCALE)
            print(f"  Detection map: {self.detection_map.shape[1]}x{self.detection_map.shape[0]}")

            # Compute features
            detector = cv2.AKAZE_create()
            keypoints, descriptors = detector.detectAndCompute(self.detection_map, None)
            print(f"  Detected {len(keypoints)} features")

            # Save to cache
            feature_cache.save(hq_source, cache_params, self.detection_map, keypoints, descriptors)

        # Initialize base matcher
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

        # Set features directly from cache (same as app_qml.py)
        from matching.spatial_keypoint_index import SpatialKeypointIndex
        base_matcher.kp_map = keypoints
        base_matcher.desc_map = descriptors
        print(f"  Map features: {len(base_matcher.kp_map)}")

        # Build spatial index
        print("  Building spatial index for ROI filtering...")
        base_matcher.spatial_index = SpatialKeypointIndex(base_matcher.kp_map)
        print(f"  Spatial index ready")

        # Create cascade configuration (production config)
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

        self.matcher = CascadeScaleMatcher(
            base_matcher,
            cascade_levels,
            use_scale_prediction=False,
            verbose=self.verbose,
            enable_roi_tracking=True
        )
        print("  Matcher initialized")

    def _initialize_collectibles(self):
        """Load collectibles data."""
        print("Loading collectibles...")
        self.coord_transform = CoordinateTransform()

        try:
            self.collectibles = CollectiblesRepository.load(self.coord_transform)
            print(f"  Loaded {len(self.collectibles)} collectibles")
        except Exception as e:
            print(f"  Warning: Could not load collectibles: {e}")
            self.collectibles = []

    def capture_screenshot(self) -> Optional[np.ndarray]:
        """Get current game screenshot from continuous capture."""
        try:
            with self.frame_lock:
                if self.latest_frame is None:
                    print(f"[ERROR] No frame available")
                    return None

                # Convert BGRA to BGR
                img = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGRA2BGR)
                return img

        except Exception as e:
            print(f"[ERROR] Screenshot capture failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def draw_collectibles(self, screenshot: np.ndarray, visible_collectibles: list) -> np.ndarray:
        """
        Draw collectible markers on the screenshot.

        Args:
            screenshot: Original screenshot image
            visible_collectibles: List of visible collectibles with screen coordinates

        Returns:
            Annotated image with collectible markers
        """
        # Create a copy to avoid modifying original
        annotated = screenshot.copy()

        # Draw each collectible
        for collectible in visible_collectibles:
            x = int(collectible['screen_x'])
            y = int(collectible['screen_y'])
            ctype = collectible.get('type', 'default')
            name = collectible.get('name', 'Unknown')

            # Get color for this type
            color = self.COLLECTIBLE_COLORS.get(ctype, self.COLLECTIBLE_COLORS['default'])

            # Draw circle marker
            cv2.circle(annotated, (x, y), 8, color, 2)
            cv2.circle(annotated, (x, y), 2, color, -1)

            # Draw type abbreviation (first 3 chars)
            type_abbr = ctype[:3].upper() if ctype != 'default' else '???'
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            font_thickness = 1

            # Get text size for background
            (text_w, text_h), baseline = cv2.getTextSize(type_abbr, font, font_scale, font_thickness)

            # Draw text background (semi-transparent black)
            text_x = x + 10
            text_y = y - 5
            cv2.rectangle(annotated, (text_x - 2, text_y - text_h - 2),
                         (text_x + text_w + 2, text_y + baseline), (0, 0, 0), -1)

            # Draw text
            cv2.putText(annotated, type_abbr, (text_x, text_y),
                       font, font_scale, color, font_thickness, cv2.LINE_AA)

        # Add summary text at top
        summary = f"Collectibles: {len(visible_collectibles)}"
        cv2.rectangle(annotated, (10, 10), (250, 40), (0, 0, 0), -1)
        cv2.putText(annotated, summary, (20, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        # Add legend in bottom-left
        legend_y = screenshot.shape[0] - 20
        legend_x = 10
        legend_text = "Legend: TAR=Tarot SET=Card COI=Coin ARR=Arrowhead JEW=Jewelry"
        cv2.rectangle(annotated, (legend_x - 5, legend_y - 20),
                     (legend_x + 800, legend_y + 5), (0, 0, 0), -1)
        cv2.putText(annotated, legend_text, (legend_x, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)

        return annotated

    def _print_cascade_details(self, cascade_info: Dict):
        """Print detailed cascade information."""
        if not cascade_info:
            return

        print(f"\n  Cascade Details:")
        print(f"  ----------------")
        print(f"  Final level: {cascade_info.get('final_level', 'unknown')}")
        print(f"  Match type: {cascade_info.get('match_type', 'unknown')}")
        print(f"  ROI used: {cascade_info.get('roi_used', False)}")
        print(f"  Prediction used: {cascade_info.get('prediction_used', False)}")

        levels_tried = cascade_info.get('levels_tried', [])
        if levels_tried:
            print(f"\n  Cascade Levels Tried ({len(levels_tried)}):")
            for level in levels_tried:
                scale = level.get('scale', 0)
                confidence = level.get('confidence', 0)
                inliers = level.get('inliers', 0)
                total_matches = level.get('total_matches', 0)
                time_ms = level.get('time_ms', 0)
                accepted = level.get('accepted', False)
                success = level.get('success', False)
                error = level.get('error', '')

                status = "[ACCEPTED]" if accepted else "[REJECTED]" if success else "[FAILED]"
                line = f"    {status} Scale {scale:.0%}: conf={confidence:.2%}, inliers={inliers}, matches={total_matches}, time={time_ms:.1f}ms"

                # Add error reason for failed matches
                if not success and error:
                    line += f" - {error}"

                print(line)

    def run_test(self) -> Dict:
        """Run a single E2E test on the current game screenshot."""
        timestamp = datetime.now()
        print(f"\n{'='*70}")
        print(f"E2E Test - {timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"{'='*70}")

        # Determine total steps
        total_steps = 4 if (self.visualize or self.save_results or self.show_window) else 3

        # Step 1: Capture screenshot
        print(f"\n[1/{total_steps}] Capturing screenshot...")
        start_capture = time.time()
        screenshot = self.capture_screenshot()
        capture_time = (time.time() - start_capture) * 1000

        if screenshot is None:
            return {'success': False, 'error': 'Screenshot capture failed'}

        print(f"  Captured: {screenshot.shape[1]}x{screenshot.shape[0]} ({capture_time:.1f}ms)")

        # Step 2: Run matching
        print(f"\n[2/{total_steps}] Running matcher...")
        start_match = time.time()
        result = self.matcher.match(screenshot)
        match_time = (time.time() - start_match) * 1000

        if not result or not result.get('success'):
            error = result.get('error', 'Unknown error') if result else 'Matcher returned None'
            print(f"  [FAIL] Matching failed: {error}")
            print(f"  Match time: {match_time:.1f}ms")

            # Show cascade details even for failed matches
            cascade_info = result.get('cascade_info', {}) if result else {}
            self._print_cascade_details(cascade_info)

            # Save screenshot for failed matches if requested
            if self.save_results:
                timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]
                screenshot_path = self.output_dir / f"failed_screenshot_{timestamp_str}.png"
                cv2.imwrite(str(screenshot_path), screenshot)

                result_path = self.output_dir / f"failed_result_{timestamp_str}.json"
                with open(result_path, 'w') as f:
                    json.dump({
                        'success': False,
                        'error': error,
                        'capture_time_ms': capture_time,
                        'match_time_ms': match_time,
                        'cascade_info': cascade_info,
                        'timestamp': timestamp.isoformat()
                    }, f, indent=2)

                print(f"\nFailed match saved:")
                print(f"  Screenshot: {screenshot_path}")
                print(f"  Details:    {result_path}")

            return {
                'success': False,
                'error': error,
                'capture_time_ms': capture_time,
                'match_time_ms': match_time,
                'cascade_info': cascade_info
            }

        print(f"  [SUCCESS] Match time: {match_time:.1f}ms")
        print(f"  Confidence: {result['confidence']:.2%}")
        print(f"  Inliers: {result['inliers']}")

        # Show cascade details
        cascade_info = result.get('cascade_info', {})
        self._print_cascade_details(cascade_info)

        # Step 3: Filter collectibles
        print(f"\n[3/{total_steps}] Filtering collectibles...")
        start_filter = time.time()

        viewport = {
            'map_x': result['map_x'],
            'map_y': result['map_y'],
            'map_width': result['map_width'],
            'map_height': result['map_height']
        }

        visible = filter_visible_collectibles(
            self.collectibles,
            viewport,
            screenshot.shape[1],
            screenshot.shape[0]
        )
        filter_time = (time.time() - start_filter) * 1000

        print(f"  Found {len(visible)} visible collectibles ({filter_time:.1f}ms)")

        # Display collectible breakdown by type
        if visible:
            type_counts = {}
            for c in visible:
                ctype = c.get('type', 'unknown')
                type_counts[ctype] = type_counts.get(ctype, 0) + 1

            print("\n  Collectibles by type:")
            for ctype, count in sorted(type_counts.items()):
                print(f"    {ctype}: {count}")

        # Calculate total time
        total_time = capture_time + match_time + filter_time

        # Summary
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"Total time:     {total_time:.1f}ms")
        print(f"  Capture:      {capture_time:.1f}ms")
        print(f"  Match:        {match_time:.1f}ms")
        print(f"  Filter:       {filter_time:.1f}ms")
        print(f"Viewport:       ({result['map_x']:.0f}, {result['map_y']:.0f})")
        print(f"Collectibles:   {len(visible)}")
        print(f"Success:        YES")

        # Build result
        test_result = {
            'success': True,
            'timestamp': timestamp.isoformat(),
            'timing': {
                'capture_ms': capture_time,
                'match_ms': match_time,
                'filter_ms': filter_time,
                'total_ms': total_time
            },
            'viewport': viewport,
            'match_info': {
                'confidence': result['confidence'],
                'inliers': result['inliers'],
                'match_type': cascade_info.get('match_type', 'unknown'),
                'cascade_level': cascade_info.get('final_level', 'unknown'),
                'roi_used': cascade_info.get('roi_used', False),
                'prediction_used': cascade_info.get('prediction_used', False),
                'levels_tried': cascade_info.get('levels_tried', [])
            },
            'collectibles': {
                'total': len(visible),
                'by_type': {ctype: sum(1 for c in visible if c.get('type') == ctype)
                           for ctype in set(c.get('type', 'unknown') for c in visible)}
            }
        }

        # Generate annotated image if visualization requested
        annotated_img = None
        if self.visualize or self.save_results or self.show_window:
            print("\n[4/4] Generating visualization...")
            annotated_img = self.draw_collectibles(screenshot, visible)

            if self.show_window:
                # Display in window
                cv2.imshow('E2E Test - Collectibles Overlay', annotated_img)
                print("\nPress any key in the image window to continue...")
                cv2.waitKey(0)
                cv2.destroyAllWindows()

        # Save results if requested
        if self.save_results:
            self._save_test_result(screenshot, test_result, annotated_img)

        return test_result

    def _save_test_result(self, screenshot: np.ndarray, result: Dict,
                          annotated_img: Optional[np.ndarray] = None):
        """Save screenshot and test result to disk."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

        # Save screenshot
        screenshot_path = self.output_dir / f"screenshot_{timestamp_str}.png"
        cv2.imwrite(str(screenshot_path), screenshot)

        # Save annotated image if provided
        annotated_path = None
        if annotated_img is not None:
            annotated_path = self.output_dir / f"annotated_{timestamp_str}.png"
            cv2.imwrite(str(annotated_path), annotated_img)

        # Save result JSON
        result_path = self.output_dir / f"result_{timestamp_str}.json"
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"\nSaved results:")
        print(f"  Screenshot: {screenshot_path}")
        if annotated_path:
            print(f"  Annotated:  {annotated_path}")
        print(f"  Results:    {result_path}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='E2E Live Screenshot Test Tool - Captures ONE frame from RDR2 window',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_live_e2e.py                    # Single frame test
  python tests/test_live_e2e.py --save-results     # Save screenshots and results
  python tests/test_live_e2e.py --visualize        # Generate annotated images
  python tests/test_live_e2e.py --show             # Display annotated image in window
  python tests/test_live_e2e.py --save-results --visualize  # Save both versions
  python tests/test_live_e2e.py --verbose          # Detailed matching logs
        """
    )

    parser.add_argument('--save-results', action='store_true',
                       help='Save screenshots and results to tests/e2e_results/')
    parser.add_argument('--visualize', action='store_true',
                       help='Generate annotated images with collectible markers')
    parser.add_argument('--show', action='store_true',
                       help='Display annotated image in a window (requires --visualize)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose matching output')

    args = parser.parse_args()

    # Create test tool
    test_tool = LiveE2ETest(
        verbose=args.verbose,
        save_results=args.save_results,
        visualize=args.visualize,
        show_window=args.show
    )

    # Run single frame test
    result = test_tool.run_test()
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
