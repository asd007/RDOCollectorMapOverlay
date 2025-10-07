"""
Fast map detection using color histogram analysis.
RDR2 map has distinctive brown/tan/beige colors.
Gameplay has green (grass) and blue (sky/water).
"""

import cv2
import numpy as np


class MapDetector:
    """
    Detects if RDR2 map is visible using color histogram.
    Much faster than feature matching (~2-3ms vs 80-100ms).
    """

    def __init__(self,
                 green_threshold: float = 0.15,
                 blue_threshold: float = 0.15,
                 min_brightness: int = 30):
        """
        Initialize map detector.

        Args:
            green_threshold: Max ratio of green pixels (0.0-1.0)
            blue_threshold: Max ratio of blue pixels (0.0-1.0)
            min_brightness: Minimum brightness to consider (ignore dark pixels)
        """
        self.green_threshold = green_threshold
        self.blue_threshold = blue_threshold
        self.min_brightness = min_brightness

    def is_map_visible(self, screenshot_bgr: np.ndarray) -> bool:
        """
        Fast check if RDR2 map is visible by detecting horizontally-aligned UI buttons.

        RDR2 map has 3 buttons ALIGNED HORIZONTALLY in bottom-right corner.
        Other screens have buttons too, but only map has them horizontally aligned.

        Args:
            screenshot_bgr: Raw screenshot in BGR format

        Returns:
            True if map detected, False if gameplay/menu
        """
        h, w = screenshot_bgr.shape[:2]

        # Look for 3 horizontally-aligned buttons in bottom-right corner
        # Extract bottom-right region (last 15% height, last 30% width for better coverage)
        bottom_right = screenshot_bgr[int(h * 0.85):, int(w * 0.70):]

        # Convert to grayscale for faster processing
        gray = cv2.cvtColor(bottom_right, cv2.COLOR_BGR2GRAY)

        # Look for bright UI elements (buttons have white/light text or icons)
        _, bright_ui = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        # Find contours (button regions)
        contours, _ = cv2.findContours(bright_ui, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter by size (buttons are reasonably sized, not tiny noise)
        min_button_area = 50  # pixels
        valid_buttons = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > min_button_area:
                # Get bounding box
                x, y, w_btn, h_btn = cv2.boundingRect(c)
                valid_buttons.append((x, y, w_btn, h_btn, y + h_btn // 2))  # Include center Y

        # Need at least 2-4 buttons (may detect 3 buttons or buttons + icons)
        if 2 <= len(valid_buttons) <= 6:
            # Check for HORIZONTAL ALIGNMENT
            # Sort by Y position (vertical position)
            valid_buttons.sort(key=lambda b: b[4])  # Sort by center Y

            # Check if multiple buttons share similar Y position (horizontally aligned)
            # Allow 20 pixel tolerance for alignment
            alignment_tolerance = 20

            for i in range(len(valid_buttons) - 1):
                aligned_group = [valid_buttons[i]]
                base_y = valid_buttons[i][4]

                # Find all buttons aligned with this one
                for j in range(i + 1, len(valid_buttons)):
                    if abs(valid_buttons[j][4] - base_y) <= alignment_tolerance:
                        aligned_group.append(valid_buttons[j])

                # If we found 2+ buttons aligned horizontally, it's likely the map
                if len(aligned_group) >= 2:
                    return True

        # No horizontally-aligned buttons found
        return False

    def get_map_confidence(self, screenshot_bgr: np.ndarray) -> dict:
        """
        Get detailed map detection metrics for debugging.

        Args:
            screenshot_bgr: Raw screenshot in BGR format

        Returns:
            Dict with confidence metrics
        """
        hsv = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        bright_mask = v > self.min_brightness
        total_bright_pixels = np.sum(bright_mask)

        if total_bright_pixels == 0:
            return {
                'is_map': False,
                'reason': 'Screen too dark',
                'green_ratio': 0.0,
                'blue_ratio': 0.0,
                'avg_saturation': 0
            }

        bright_hues = h[bright_mask]
        green_pixels = np.sum((bright_hues >= 35) & (bright_hues <= 85))
        blue_pixels = np.sum((bright_hues >= 90) & (bright_hues <= 130))

        green_ratio = green_pixels / total_bright_pixels
        blue_ratio = blue_pixels / total_bright_pixels

        bright_saturation = s[bright_mask]
        avg_saturation = int(np.mean(bright_saturation))

        is_map = True
        reason = "Map detected"

        if green_ratio > self.green_threshold:
            is_map = False
            reason = f"Too much green ({green_ratio:.1%})"
        elif blue_ratio > self.blue_threshold:
            is_map = False
            reason = f"Too much blue ({blue_ratio:.1%})"
        elif avg_saturation > 100:
            is_map = False
            reason = f"Too saturated ({avg_saturation}/255)"

        return {
            'is_map': is_map,
            'reason': reason,
            'green_ratio': float(green_ratio),
            'blue_ratio': float(blue_ratio),
            'avg_saturation': avg_saturation,
            'green_threshold': self.green_threshold,
            'blue_threshold': self.blue_threshold
        }


# Global detector instance
MAP_DETECTOR = MapDetector(
    green_threshold=0.15,  # Max 15% green
    blue_threshold=0.15,   # Max 15% blue
    min_brightness=30      # Ignore dark pixels
)


def is_map_visible(screenshot_bgr: np.ndarray) -> bool:
    """
    Convenience function to check if map is visible.

    Args:
        screenshot_bgr: Raw screenshot in BGR format

    Returns:
        True if map detected, False otherwise
    """
    return MAP_DETECTOR.is_map_visible(screenshot_bgr)
