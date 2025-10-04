"""
Test data collector - captures real gameplay screenshots with metadata.
Used to build accurate test cases from actual gameplay.
"""

import cv2
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class TestDataCollector:
    """Collects real gameplay screenshots with matching metadata for testing."""

    def __init__(self, output_dir: str = "tests/data", max_per_zoom: int = 3):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.screenshots_dir = self.output_dir / "screenshots"
        self.metadata_dir = self.output_dir / "metadata"
        self.screenshots_dir.mkdir(exist_ok=True)
        self.metadata_dir.mkdir(exist_ok=True)

        self.capture_count = 0
        self.max_per_zoom = max_per_zoom
        self.zoom_counts = {}  # Track samples per zoom level

        # Track zoom range (viewport size)
        self.min_viewport_w = float('inf')
        self.max_viewport_w = 0
        self.min_viewport_h = float('inf')
        self.max_viewport_h = 0

    def save_test_case(self,
                       screenshot: 'np.ndarray',
                       match_result: Dict,
                       timing: Dict,
                       cascade_level: str = None) -> Optional[str]:
        """
        Save a test case with screenshot and metadata.

        Args:
            screenshot: Raw BGR screenshot from game
            match_result: Matching result dict (viewport position, confidence, etc.)
            timing: Timing breakdown (capture_ms, match_ms, etc.)
            cascade_level: Which cascade level was used (25%, 50%, 70%)

        Returns:
            Test case ID (timestamp-based filename) or None if skipped (quota reached)
        """
        # Calculate zoom level from viewport size
        viewport_w = match_result.get('map_w', 0)
        viewport_h = match_result.get('map_h', 0)
        zoom_level = self._estimate_zoom_level(viewport_w, viewport_h)

        # Update viewport size tracking (for min/max zoom stats)
        # Only track valid viewports (>100px to avoid invalid/tiny matches)
        if viewport_w > 100:
            self.min_viewport_w = min(self.min_viewport_w, viewport_w)
            self.max_viewport_w = max(self.max_viewport_w, viewport_w)
        if viewport_h > 100:
            self.min_viewport_h = min(self.min_viewport_h, viewport_h)
            self.max_viewport_h = max(self.max_viewport_h, viewport_h)

        # Check if we already have enough samples for this zoom level
        current_count = self.zoom_counts.get(zoom_level, 0)
        if current_count >= self.max_per_zoom:
            return None  # Skip - already have enough samples for this zoom

        # Generate unique ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        test_id = f"test_{timestamp}_{self.capture_count:04d}"
        self.capture_count += 1

        # Update zoom count
        self.zoom_counts[zoom_level] = current_count + 1

        # Save screenshot
        screenshot_path = self.screenshots_dir / f"{test_id}.png"
        cv2.imwrite(str(screenshot_path), screenshot)

        # Build metadata
        metadata = {
            'test_id': test_id,
            'timestamp': timestamp,
            'screenshot_file': f"screenshots/{test_id}.png",
            'viewport': {
                'map_x': match_result.get('map_x', 0),
                'map_y': match_result.get('map_y', 0),
                'map_w': viewport_w,
                'map_h': viewport_h,
                'center_x': match_result.get('map_x', 0) + viewport_w / 2,
                'center_y': match_result.get('map_y', 0) + viewport_h / 2
            },
            'zoom': {
                'level': zoom_level,
                'viewport_width': viewport_w,
                'viewport_height': viewport_h
            },
            'matching': {
                'cascade_level': cascade_level or 'unknown',
                'confidence': match_result.get('confidence', 0),
                'inliers': match_result.get('inliers', 0),
                'total_matches': match_result.get('total_matches', 0)
            },
            'timing': {
                'capture_ms': timing.get('capture_ms', 0),
                'match_ms': timing.get('match_ms', 0),
                'overlay_ms': timing.get('overlay_ms', 0),
                'total_ms': timing.get('total_ms', 0)
            },
            'screenshot_resolution': {
                'width': screenshot.shape[1],
                'height': screenshot.shape[0]
            }
        }

        # Save metadata
        metadata_path = self.metadata_dir / f"{test_id}.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return test_id

    def _estimate_zoom_level(self, viewport_w: int, viewport_h: int) -> str:
        """
        Estimate zoom level category from viewport size.

        Note: Actual zoom ranges may vary - these are approximate buckets.
        Detection space is 10808×8392.
        """
        # Use broader categories to account for varying zoom ranges
        # Large viewport = zoomed out, small viewport = zoomed in

        if viewport_w > 4000:
            # Zoomed out: Large area visible (>4000px width)
            return "zoomed_out"
        elif viewport_w > 1800:
            # Medium zoom: Mid-range area (1800-4000px width)
            return "medium_zoom"
        else:
            # Zoomed in: Small area visible (<1800px width)
            return "zoomed_in"

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        metadata_files = list(self.metadata_dir.glob("*.json"))

        # Analyze zoom levels
        zoom_counts = {}
        cascade_counts = {}
        total_match_time = 0

        for meta_file in metadata_files:
            with open(meta_file) as f:
                data = json.load(f)

            zoom = data['zoom']['level']
            zoom_counts[zoom] = zoom_counts.get(zoom, 0) + 1

            cascade = data['matching']['cascade_level']
            cascade_counts[cascade] = cascade_counts.get(cascade, 0) + 1

            total_match_time += data['timing']['match_ms']

        # Check which zoom levels are complete
        zoom_status = {}
        for zoom_level in ['zoomed_out', 'medium_zoom', 'zoomed_in']:
            current = self.zoom_counts.get(zoom_level, 0)
            zoom_status[zoom_level] = {
                'count': current,
                'max': self.max_per_zoom,
                'complete': current >= self.max_per_zoom
            }

        # Viewport size range (min/max zoom observed)
        viewport_range = {
            'min_width': self.min_viewport_w if self.min_viewport_w != float('inf') else 0,
            'max_width': self.max_viewport_w,
            'min_height': self.min_viewport_h if self.min_viewport_h != float('inf') else 0,
            'max_height': self.max_viewport_h
        }

        return {
            'total_cases': len(metadata_files),
            'max_per_zoom': self.max_per_zoom,
            'zoom_distribution': zoom_counts,
            'zoom_status': zoom_status,
            'viewport_range': viewport_range,
            'cascade_distribution': cascade_counts,
            'avg_match_time_ms': total_match_time / max(1, len(metadata_files))
        }

    def export_test_manifest(self, output_file: str = None):
        """
        Export manifest of all test cases for automated testing.

        Creates a JSON file listing all test cases with their expected results.
        """
        if output_file is None:
            output_file = self.output_dir / "test_manifest.json"

        metadata_files = sorted(self.metadata_dir.glob("*.json"))

        manifest = {
            'test_suite': 'real_gameplay_tests',
            'created_at': datetime.now().isoformat(),
            'total_cases': len(metadata_files),
            'test_cases': []
        }

        for meta_file in metadata_files:
            with open(meta_file) as f:
                data = json.load(f)

            manifest['test_cases'].append({
                'test_id': data['test_id'],
                'screenshot': data['screenshot_file'],
                'expected_viewport': data['viewport'],
                'zoom_level': data['zoom']['level'],
                'cascade_level': data['matching']['cascade_level'],
                'reference_timing': data['timing']
            })

        with open(output_file, 'w') as f:
            json.dump(manifest, f, indent=2)

        return str(output_file)
