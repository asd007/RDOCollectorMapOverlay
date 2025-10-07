"""Spatial index for fast ROI-based keypoint filtering"""

import numpy as np


class SpatialKeypointIndex:
    """
    Spatial index for efficiently querying keypoints within rectangular regions.
    Uses numpy boolean indexing for fast filtering.
    """

    def __init__(self, keypoints):
        """
        Build spatial index from keypoints

        Args:
            keypoints: List of cv2.KeyPoint objects
        """
        self.keypoints = keypoints

        # Extract positions as numpy array for fast queries
        self.positions = np.array([kp.pt for kp in keypoints], dtype=np.float32)

        print(f"[SpatialIndex] Built index for {len(keypoints)} keypoints")

    def query_rect(self, x_min, x_max, y_min, y_max):
        """
        Get indices of keypoints within rectangular region

        Args:
            x_min, x_max: Horizontal bounds
            y_min, y_max: Vertical bounds

        Returns:
            numpy array of indices into original keypoint list
        """
        mask = (
            (self.positions[:, 0] >= x_min) &
            (self.positions[:, 0] <= x_max) &
            (self.positions[:, 1] >= y_min) &
            (self.positions[:, 1] <= y_max)
        )

        indices = np.where(mask)[0]

        return indices

    def query_viewport_expanded(self, center_x, center_y, viewport_width, viewport_height, expansion=1.1):
        """
        Get keypoints within expanded viewport region

        Args:
            center_x, center_y: Viewport center position
            viewport_width, viewport_height: Viewport dimensions
            expansion: Expansion factor (1.1 = 10% larger)

        Returns:
            numpy array of indices
        """
        half_w = (viewport_width * expansion) / 2
        half_h = (viewport_height * expansion) / 2

        x_min = center_x - half_w
        x_max = center_x + half_w
        y_min = center_y - half_h
        y_max = center_y + half_h

        return self.query_rect(x_min, x_max, y_min, y_max)
