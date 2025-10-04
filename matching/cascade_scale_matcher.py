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
                 verbose: bool = False):
        """
        Initialize cascade matcher.

        Args:
            base_matcher: SimpleMatcher instance with pre-computed map features
            cascade_levels: List of scale configurations (tried in order)
            use_scale_prediction: Deprecated (kept for backward compatibility)
            verbose: Print detailed timing and fallback info
        """
        self.base_matcher = base_matcher
        self.cascade_levels = cascade_levels
        self.verbose = verbose

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

    def match(self, screenshot_preprocessed: np.ndarray) -> Optional[Dict]:
        """
        Match screenshot using cascading scales.

        Args:
            screenshot_preprocessed: Preprocessed screenshot (grayscale)

        Returns:
            Match result dict with additional 'cascade_info' field, or None
        """
        total_start = time.time()

        cascade_info = {
            'levels_tried': [],
            'final_level': None,
            'total_time_ms': 0,
            'skipped_levels': 0,
            'prediction_used': False,
            'prediction_ms': 0
        }

        # Use default scale ordering (smallest/fastest first)
        ordered_levels = self.default_cascade_levels

        for i, level in enumerate(ordered_levels):
            level_start = time.time()

            # Optimized: Resize in grayscale BEFORE preprocessing
            # screenshot_preprocessed is actually RAW screenshot (not preprocessed yet)
            # This function does: grayscale  ->  resize  ->  posterize+CLAHE+LUT
            from core.image_preprocessing import preprocess_with_resize

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

            # Match
            result = self.base_matcher.match(screenshot_scaled)

            # Restore max features and detector
            self.base_matcher.max_screenshot_features = old_max
            self.base_matcher.detector = old_detector

            level_time = (time.time() - level_start) * 1000

            # Record attempt
            level_info = {
                'level': i,
                'name': level.name,
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
                    cascade_info['final_level'] = level.name
                    cascade_info['total_time_ms'] = (time.time() - total_start) * 1000

                    # Add cascade info to result
                    result['cascade_info'] = cascade_info

                    if self.verbose:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} ({level.name}): "
                              f"{level_time:.2f}ms, conf={result['confidence']:.3f}, "
                              f"inliers={result['inliers']} - ACCEPTED")

                    return result
                else:
                    # Quality insufficient, try next level
                    cascade_info['levels_tried'].append(level_info)

                    if self.verbose:
                        print(f"  Level {i+1}/{len(self.cascade_levels)} ({level.name}): "
                              f"{level_time:.2f}ms, conf={result['confidence']:.3f}, "
                              f"inliers={result['inliers']} - REJECTED (quality too low)")
            else:
                # Match failed
                level_info['confidence'] = 0.0
                level_info['inliers'] = 0
                level_info['accepted'] = False
                cascade_info['levels_tried'].append(level_info)

                if self.verbose:
                    print(f"  Level {i+1}/{len(self.cascade_levels)} ({level.name}): "
                          f"{level_time:.2f}ms - FAILED")

        # All levels tried, none accepted
        cascade_info['total_time_ms'] = (time.time() - total_start) * 1000

        if self.verbose:
            print(f"  All {len(self.cascade_levels)} levels tried, no match found")

        return None

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
                min_inliers=10,
                name="Fast (25%)"
            ),
            ScaleConfig(
                scale=0.5,
                max_features=150,
                min_confidence=0.0,  # Always accept (fallback level)
                min_inliers=5,
                name="Reliable (50%)"
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
                min_inliers=10,
                name="Ultra-fast (12.5%)"
            ),
            ScaleConfig(
                scale=0.25,
                max_features=75,
                min_confidence=0.8,
                min_inliers=10,
                name="Fast (25%)"
            ),
            ScaleConfig(
                scale=0.5,
                max_features=150,
                min_confidence=0.0,  # Always accept (fallback level)
                min_inliers=5,
                name="Reliable (50%)"
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
