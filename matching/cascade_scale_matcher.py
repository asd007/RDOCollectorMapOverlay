#!/usr/bin/env python3
"""
Cascading Scale Matcher - Flexible multi-scale matching with quality-based fallback.

Strategy:
- Try scales in order from fastest to most accurate
- Each scale has quality thresholds (min_confidence, min_inliers)
- Return first match that meets quality requirements
- Fall through to next scale if quality is insufficient

Example cascade chain:
1. 0.125× scale (ultra-fast, ~5ms) - quality threshold 0.9
2. 0.25× scale (fast, ~8ms) - quality threshold 0.8
3. 0.5× scale (reliable, ~42ms) - always accept

This allows balancing speed vs accuracy based on content complexity.
"""

import cv2
import numpy as np
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from matching.simple_matcher import SimpleMatcher
from matching.translation_tracker import TranslationTracker


@dataclass
class ScaleConfig:
    """Configuration for a single scale level in the cascade."""
    scale: float  # Screenshot scale (e.g., 0.25 for 25%)
    max_features: int  # Proportional to scale (e.g., 150 for 0.5×, 75 for 0.25×)
    min_confidence: float  # Minimum inlier ratio (inliers/total_matches) to accept (0.0-1.0)
    min_inliers: int  # Minimum absolute inlier count required for valid match
    min_matches: int = 10  # Minimum good matches required (default: 10)
    name: str = "Unnamed"  # Human-readable name for logging

    def __repr__(self):
        return f"{self.name} ({self.scale}x, {self.max_features} features, inlier_ratio>={self.min_confidence}, min_matches>={self.min_matches})"


class CascadeScaleMatcher:
    """
    Multi-scale cascade matcher with quality-based fallback.

    Tries scales in order, accepting first match that meets quality threshold.
    """

    def __init__(self,
                 base_matcher: SimpleMatcher,
                 cascade_levels: List[ScaleConfig],
                 use_scale_prediction: bool = False,
                 verbose: bool = False,
                 enable_roi_tracking: bool = True):
        """
        Initialize cascade matcher.

        Args:
            base_matcher: SimpleMatcher instance with pre-computed map features
            cascade_levels: List of scale configurations (tried in order)
            use_scale_prediction: Deprecated (kept for backward compatibility)
            verbose: Print detailed timing and fallback info
            enable_roi_tracking: Enable ROI-based filtering when tracking (default True)
        """
        self.base_matcher = base_matcher
        self.cascade_levels = cascade_levels
        self.verbose = verbose
        self.enable_roi_tracking = enable_roi_tracking

        # Tracking state
        self.last_viewport = None  # (center_x, center_y, width, height) in detection space
        self.last_confidence = 0.0

        # Motion prediction using TranslationTracker (fast inter-frame tracking)
        # Use 0.25× scale for speed (3ms faster than 0.5×, ~12ms total vs 15ms)
        # Accuracy trade-off: ±1px instead of ±0.5px (acceptable for smooth tracking)
        self.translation_tracker = TranslationTracker(scale=0.25, min_confidence=0.1, verbose=False)

        # Validate cascade levels
        if not cascade_levels:
            raise ValueError("At least one cascade level required")

        # Default ordering (smallest/fastest first)
        self.default_cascade_levels = sorted(cascade_levels, key=lambda x: x.scale)

        # Create lookup for reordering based on prediction
        self.scale_lookup = {level.scale: level for level in cascade_levels}

        if self.verbose:
            print(f"CascadeScaleMatcher initialized with {len(self.cascade_levels)} levels:")
            for i, level in enumerate(self.default_cascade_levels, 1):
                print(f"  {i}. {level}")
            if enable_roi_tracking:
                print("  ROI tracking: ENABLED (10% expanded viewport)")

    def match(self, screenshot_preprocessed: np.ndarray) -> Optional[Dict]:
        """
        Match screenshot using cascading scales.

        Args:
            screenshot_preprocessed: Preprocessed screenshot (grayscale)

        Returns:
            Match result dict with additional 'cascade_info' field containing:
            - On success: 'success': True, viewport coords, cascade details
            - On failure: 'success': False, 'error': reason, cascade details showing why each level failed
        """
        total_start = time.time()

        # Validate input
        if screenshot_preprocessed is None:
            print("[CascadeScaleMatcher] ERROR: Input screenshot is None")
            return {
                'success': False,
                'error': 'Input screenshot is None',
                'confidence': 0.0,
                'inliers': 0,
                'cascade_info': {}
            }

        cascade_info = {
            'levels_tried': [],
            'final_level': None,
            'total_time_ms': 0,
            'skipped_levels': 0,
            'prediction_used': False,
            'prediction_ms': 0,
            'roi_used': False,
            'motion_prediction': None
        }

        # Motion prediction using TranslationTracker
        motion_predicted_center = None
        if (self.enable_roi_tracking and
            self.last_viewport is not None and
            self.last_confidence > 0.5):

            # Track translation using optimized phase correlation
            translation, phase_confidence, debug_info = self.translation_tracker.track(screenshot_preprocessed)

            cascade_info['prediction_ms'] = debug_info.get('total_ms', 0.0)

            # Only use prediction if confidence is high enough and translation was detected
            if translation is not None and phase_confidence > 0.7:
                dx, dy = translation

                # Transform screen pixel offset to detection space offset
                # dx, dy are in screenshot pixels (1920×1080 if game runs at native res)
                # Need to convert to detection space based on viewport scale
                # If viewport shows 2000 detection pixels across 1920 screen pixels,
                # then 100 screen pixels = 100 * (2000/1920) = 104.2 detection pixels
                last_center_x, last_center_y, last_w, last_h = self.last_viewport

                # Assume screenshot is 1920×1080 (TODO: get actual screenshot dimensions)
                screenshot_width = screenshot_preprocessed.shape[1]
                screenshot_height = screenshot_preprocessed.shape[0]

                # Scale screen movement to detection space movement
                map_dx = dx * (last_w / screenshot_width)
                map_dy = dy * (last_h / screenshot_height)

                # Update predicted center with translation
                predicted_center_x = last_center_x + map_dx
                predicted_center_y = last_center_y + map_dy
                predicted_w = last_w
                predicted_h = last_h

                motion_predicted_center = (predicted_center_x, predicted_center_y, predicted_w, predicted_h)

                cascade_info['prediction_used'] = True
                cascade_info['motion_prediction'] = {
                    'offset_px': (float(dx), float(dy)),
                    'offset_map': (float(map_dx), float(map_dy)),
                    'phase_confidence': float(phase_confidence),
                    'predicted_center': (float(predicted_center_x), float(predicted_center_y)),
                    'predicted_size': (float(predicted_w), float(predicted_h)),
                    'tracker_scale': self.translation_tracker.scale
                }

                if self.verbose:
                    print(f"[Motion Prediction] {debug_info['total_ms']:.1f}ms, "
                          f"offset=({dx:.1f}, {dy:.1f})px, "
                          f"phase_conf={phase_confidence:.3f}")
            else:
                if self.verbose and translation is not None:
                    print(f"[Motion Prediction] Low phase confidence ({phase_confidence:.3f}), skipping")

        # OPTIMIZATION: Use AKAZE only for initial alignment, then pure motion tracking
        # Phase correlation is extremely accurate for translation detection
        # This reduces latency from ~30ms (10ms prediction + 20ms AKAZE) to ~5ms

        # Check if we should bypass AKAZE
        should_bypass = False
        bypass_reason = None

        if motion_predicted_center is not None and translation is not None:
            dx, dy = translation
            movement_magnitude = np.sqrt(dx**2 + dy**2)

            # Trust phase correlation if we have tracking history AND good confidence
            # Use higher threshold (0.7) to reduce drift - fallback to AKAZE more often
            if self.last_viewport is not None and phase_confidence > 0.7:
                should_bypass = True
                bypass_reason = f"motion_only (phase={phase_confidence:.3f}, movement={movement_magnitude:.1f}px)"
            elif self.last_viewport is not None and phase_confidence > 0.5 and self.last_confidence > 0.8:
                # Allow lower phase confidence if recent AKAZE was very confident
                should_bypass = True
                bypass_reason = f"motion_only (phase={phase_confidence:.3f}, prev_conf={self.last_confidence:.3f})"

        if should_bypass:
            # Trust prediction completely - bypass all feature matching
            predicted_center_x, predicted_center_y, predicted_w, predicted_h = motion_predicted_center

            # Calculate viewport bounds
            map_x = predicted_center_x - predicted_w / 2
            map_y = predicted_center_y - predicted_h / 2

            # Return prediction-only result
            result = {
                'success': True,
                'match_type': 'motion_only',  # High-level categorization for stats
                'map_x': map_x,
                'map_y': map_y,
                'map_w': predicted_w,
                'map_h': predicted_h,
                'confidence': max(phase_confidence, self.last_confidence * 0.95),  # Slight decay for static
                'inliers': 0,  # No feature matching performed
                'method': 'motion_prediction_only',
                'cascade_info': {
                    **cascade_info,
                    'match_type': 'motion_only',  # Also in cascade_info for consistency
                    'final_level': 0.0,  # 0.0 = motion-only (no scale)
                    'levels_tried': [],
                    'bypass_reason': bypass_reason
                }
            }

            # Update tracking state (with slight confidence decay for static frames)
            self.last_viewport = (predicted_center_x, predicted_center_y, predicted_w, predicted_h)
            if movement_magnitude < 2.0:
                # Static screen - decay confidence slightly to trigger AKAZE after extended static period
                self.last_confidence = max(0.7, self.last_confidence * 0.98)
            else:
                self.last_confidence = phase_confidence

            if self.verbose:
                print(f"[Motion-Only] {bypass_reason}, offset=({dx:.1f},{dy:.1f})px")

            return result

        # Determine if we should use ROI tracking
        roi = None
        roi_expansion = 1.1  # Default 10% expansion

        if self.enable_roi_tracking and self.last_viewport is not None and self.last_confidence > 0.5:
            # Use motion-predicted center if available, otherwise last viewport
            if motion_predicted_center is not None:
                roi = motion_predicted_center
                roi_expansion = 1.05  # Tighter 5% expansion when using motion prediction
                cascade_info['roi_used'] = True
                if self.verbose:
                    print(f"[ROI Tracking] Using motion-predicted ROI (5% expansion)")
            else:
                roi = self.last_viewport
                cascade_info['roi_used'] = True
                if self.verbose:
                    print(f"[ROI Tracking] Using last viewport ROI (10% expansion, conf={self.last_confidence:.3f})")

        # Use default scale ordering (smallest/fastest first)
        ordered_levels = self.default_cascade_levels

        for i, level in enumerate(ordered_levels):
            level_start = time.time()

            # Optimized: Resize in grayscale BEFORE preprocessing
            # screenshot_preprocessed is actually RAW screenshot (not preprocessed yet)
            # This function does: grayscale  ->  resize  ->  posterize+CLAHE+LUT
            from core.matching.image_preprocessing import preprocess_with_resize

            screenshot_scaled = preprocess_with_resize(
                screenshot_preprocessed,  # Raw screenshot
                scale=level.scale
            )

            # Update matcher's max screenshot features and use scale-optimized detector
            old_max = self.base_matcher.max_screenshot_features
            old_detector = self.base_matcher.detector
            self.base_matcher.max_screenshot_features = level.max_features

            # Use scale-optimized detector for better performance
            if hasattr(self.base_matcher, 'create_scale_optimized_detector'):
                self.base_matcher.detector = self.base_matcher.create_scale_optimized_detector(level.scale)

            # Match (pass ROI and expansion if tracking)
            # Nuclear option: 1.0 scale level should search entire map (no ROI restriction)
            use_roi = roi if level.scale != 1.0 else None
            result = self.base_matcher.match(screenshot_scaled, roi=use_roi, roi_expansion=roi_expansion)

            # Restore max features and detector
            self.base_matcher.max_screenshot_features = old_max
            self.base_matcher.detector = old_detector

            level_time = (time.time() - level_start) * 1000

            # Record attempt
            level_info = {
                'level': i,
                'scale': level.scale,
                'time_ms': level_time,
                'success': result is not None and result.get('success', False)
            }

            if result and result.get('success', False):
                level_info['confidence'] = result['confidence']
                level_info['inliers'] = result['inliers']
                level_info['total_matches'] = result.get('total_matches', 0)
                level_info['accepted'] = False

                # Check quality thresholds
                # 1. Minimum good matches (after ratio test)
                # 2. Minimum inlier ratio (inliers/total_matches)
                # 3. Minimum absolute inlier count
                has_enough_matches = result.get('total_matches', 0) >= level.min_matches
                has_good_inlier_ratio = result['confidence'] >= level.min_confidence
                has_enough_inliers = result['inliers'] >= level.min_inliers

                if has_enough_matches and has_good_inlier_ratio and has_enough_inliers:
                    # Quality sufficient, accept this result
                    level_info['accepted'] = True
                    cascade_info['levels_tried'].append(level_info)
                    cascade_info['final_level'] = level.scale
                    cascade_info['total_time_ms'] = (time.time() - total_start) * 1000
                    cascade_info['match_type'] = 'akaze'  # Mark as AKAZE feature matching

                    # Add cascade info and match_type to result
                    result['match_type'] = 'akaze'  # High-level categorization for stats
                    result['cascade_info'] = cascade_info

                    # Update tracking state for ROI filtering
                    if self.enable_roi_tracking and result.get('success'):
                        # Extract viewport from result (in detection space)
                        map_x, map_y = result.get('map_x', 0), result.get('map_y', 0)
                        map_w, map_h = result.get('map_w', 0), result.get('map_h', 0)
                        center_x = map_x + map_w / 2
                        center_y = map_y + map_h / 2
                        self.last_viewport = (center_x, center_y, map_w, map_h)
                        self.last_confidence = result['confidence']

                        # TranslationTracker handles storing previous frame internally

                        if self.verbose:
                            print(f"  [ROI Tracking] Updated viewport: center=({center_x:.0f}, {center_y:.0f}), "
                                  f"size=({map_w:.0f}x{map_h:.0f}), conf={self.last_confidence:.3f}")

                    if self.verbose:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} (scale={level.scale}): "
                              f"{level_time:.2f}ms, conf={result['confidence']:.3f}, "
                              f"inliers={result['inliers']} - ACCEPTED")

                    return result
                else:
                    # Quality insufficient, try next level
                    cascade_info['levels_tried'].append(level_info)

                    if self.verbose:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} (scale={level.scale}): "
                              f"{level_time:.2f}ms, conf={result['confidence']:.3f}, "
                              f"inliers={result['inliers']} - REJECTED (quality too low)")
            else:
                # Match failed - but extract ACTUAL AKAZE numbers if available
                if result:
                    # Matcher returned a result dict, extract real values
                    level_info['confidence'] = result.get('confidence', 0.0)
                    level_info['inliers'] = result.get('inliers', 0)
                    level_info['total_matches'] = result.get('total_matches', 0)
                    level_info['error'] = result.get('error', 'Unknown')
                else:
                    # Matcher returned None
                    level_info['confidence'] = 0.0
                    level_info['inliers'] = 0
                    level_info['total_matches'] = 0
                    level_info['error'] = 'Matcher returned None'

                level_info['accepted'] = False
                cascade_info['levels_tried'].append(level_info)

                if self.verbose:
                    if result:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} ({level.name}): "
                              f"{level_time:.2f}ms, conf={level_info['confidence']:.3f}, "
                              f"inliers={level_info['inliers']} - FAILED ({level_info['error']})")
                    else:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} ({level.name}): "
                              f"{level_time:.2f}ms - FAILED (None result)")

        # All levels tried, none accepted
        cascade_info['total_time_ms'] = (time.time() - total_start) * 1000
        cascade_info['final_level'] = None

        if self.verbose:
            print(f"  All {len(self.cascade_levels)} levels tried, no match found")

        # Return failure dict with cascade info for debugging
        return {
            'success': False,
            'error': 'All cascade levels failed quality thresholds',
            'confidence': 0.0,
            'inliers': 0,
            'cascade_info': cascade_info
        }

    @classmethod
    def create_default_cascade(cls, base_matcher: SimpleMatcher, verbose: bool = False):
        """
        Create cascade matcher with default scale levels.

        Default cascade:
        1. 25% scale (fast) - requires high confidence (0.8)
        2. 50% scale (reliable) - always accept

        Args:
            base_matcher: SimpleMatcher with pre-computed map features
            verbose: Print detailed info

        Returns:
            CascadeScaleMatcher instance
        """
        cascade_levels = [
            ScaleConfig(
                scale=0.25,
                max_features=75,
                min_confidence=0.8,
                min_inliers=10
            ),
            ScaleConfig(
                scale=0.5,
                max_features=150,
                min_confidence=0.5,
                min_inliers=8
            ),
            ScaleConfig(
                scale=1.0,
                max_features=300,
                min_confidence=0.6,  # Higher confidence for full res
                min_inliers=5
            )
        ]

        return cls(base_matcher, cascade_levels, verbose)

    @classmethod
    def create_aggressive_cascade(cls, base_matcher: SimpleMatcher, verbose: bool = False):
        """
        Create aggressive 3-level cascade for maximum speed.

        Cascade:
        1. 12.5% scale (ultra-fast) - requires very high confidence (0.9)
        2. 25% scale (fast) - requires high confidence (0.8)
        3. 50% scale (reliable) - always accept

        Args:
            base_matcher: SimpleMatcher with pre-computed map features
            verbose: Print detailed info

        Returns:
            CascadeScaleMatcher instance
        """
        cascade_levels = [
            ScaleConfig(
                scale=0.125,
                max_features=38,  # Proportional to 0.125 × 300
                min_confidence=0.9,
                min_inliers=10
            ),
            ScaleConfig(
                scale=0.25,
                max_features=75,
                min_confidence=0.8,
                min_inliers=10
            ),
            ScaleConfig(
                scale=0.5,
                max_features=150,
                min_confidence=0.5,
                min_inliers=8
            ),
            ScaleConfig(
                scale=1.0,
                max_features=300,
                min_confidence=0.6,  # Higher confidence for full res
                min_inliers=5
            )
        ]

        return cls(base_matcher, cascade_levels, verbose)

    @classmethod
    def create_custom_cascade(cls,
                             base_matcher: SimpleMatcher,
                             scales: List[Tuple[float, int, float, int, str]],
                             verbose: bool = False):
        """
        Create cascade matcher with custom scale levels.

        Args:
            base_matcher: SimpleMatcher with pre-computed map features
            scales: List of (scale, max_features, min_confidence, min_inliers, name)
            verbose: Print detailed info

        Returns:
            CascadeScaleMatcher instance

        Example:
            matcher = CascadeScaleMatcher.create_custom_cascade(
                base_matcher,
                [
                    (0.125, 38, 0.95, 15, "Ultra-fast"),
                    (0.25, 75, 0.85, 10, "Fast"),
                    (0.5, 150, 0.7, 8, "Medium"),
                    (1.0, 300, 0.0, 5, "Full (fallback)")
                ]
            )
        """
        cascade_levels = [
            ScaleConfig(scale=s, max_features=f, min_confidence=c, min_inliers=i, name=n)
            for s, f, c, i, n in scales
        ]

        return cls(base_matcher, cascade_levels, verbose)


# Convenience function for quick integration
def create_cascade_matcher(detection_map: np.ndarray,
                           cascade_type: str = 'default',
                           verbose: bool = False) -> CascadeScaleMatcher:
    """
    Convenience function to create a cascade matcher.

    Args:
        detection_map: Preprocessed detection map
        cascade_type: 'default' (2 levels) or 'aggressive' (3 levels)
        verbose: Print detailed info

    Returns:
        CascadeScaleMatcher instance
    """
    # Create base matcher
    base_matcher = SimpleMatcher(
        max_features=0,
        ratio_test_threshold=0.75,
        min_inliers=5,
        min_inlier_ratio=0.5,
        ransac_threshold=5.0,
        use_spatial_distribution=True,
        spatial_grid_size=50,
        max_screenshot_features=300
    )
    base_matcher.compute_reference_features(detection_map)

    # Create cascade
    if cascade_type == 'aggressive':
        return CascadeScaleMatcher.create_aggressive_cascade(base_matcher, verbose)
    else:
        return CascadeScaleMatcher.create_default_cascade(base_matcher, verbose)
