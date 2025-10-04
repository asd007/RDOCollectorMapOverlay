"""
Spatial feature selector that preserves relative keypoint densities.

Key insight: Instead of taking top N features by response strength (which clusters
in high-density areas), we should:
1. Detect many keypoints (20k-50k)
2. Subdivide map into grid
3. Select proportionally from each cell based on local density
4. This ensures even sparse areas get representation
"""

import cv2
import numpy as np
from typing import List, Tuple


class SpatialFeatureSelector:
    """Select features while preserving spatial density distribution"""

    def __init__(self, target_features: int = 10000, grid_size: int = 50,
                 min_per_cell: int = 2):
        """
        Initialize selector.

        Args:
            target_features: Target number of features to keep
            grid_size: Grid cell size in pixels (smaller = finer distribution)
            min_per_cell: Minimum features to keep from each populated cell
        """
        self.target_features = target_features
        self.grid_size = grid_size
        self.min_per_cell = min_per_cell

    def select_features(self, keypoints: List, descriptors: np.ndarray,
                       map_shape: Tuple[int, int]) -> Tuple[List, np.ndarray]:
        """
        Select features while preserving spatial density distribution.

        Args:
            keypoints: All detected keypoints
            descriptors: All descriptors
            map_shape: (height, width) of map

        Returns:
            (selected_keypoints, selected_descriptors)
        """
        # If target is 0 or >= detected features, keep all
        if self.target_features == 0 or len(keypoints) <= self.target_features:
            print(f"Keeping all {len(keypoints)} features (target: {self.target_features})")
            return keypoints, descriptors

        h, w = map_shape

        # Create grid
        grid_h = (h + self.grid_size - 1) // self.grid_size
        grid_w = (w + self.grid_size - 1) // self.grid_size

        # Assign keypoints to grid cells
        grid_cells = {}  # (grid_y, grid_x) -> [(kp_idx, response), ...]

        for idx, kp in enumerate(keypoints):
            x, y = kp.pt
            grid_x = min(int(x / self.grid_size), grid_w - 1)
            grid_y = min(int(y / self.grid_size), grid_h - 1)
            cell_key = (grid_y, grid_x)

            if cell_key not in grid_cells:
                grid_cells[cell_key] = []
            grid_cells[cell_key].append((idx, kp.response))

        # Calculate how many features to take from each cell
        # Ensure minimum per cell, then distribute remaining proportionally
        total_features = len(keypoints)
        num_cells = len(grid_cells)

        # Reserve minimum features for all cells
        reserved = num_cells * self.min_per_cell
        if reserved > self.target_features:
            # If we can't meet minimum, take 1 from each cell
            print(f"  Warning: {num_cells} cells need {reserved} features, "
                  f"but target is {self.target_features}. Using 1 per cell.")
            features_per_cell = {cell_key: 1 for cell_key in grid_cells.keys()}
        else:
            # Distribute: min_per_cell to all, then remaining proportionally
            remaining = self.target_features - reserved
            features_per_cell = {}

            for cell_key, cell_kps in grid_cells.items():
                cell_count = len(cell_kps)
                cell_proportion = cell_count / total_features

                # Minimum + proportional share of remaining
                cell_target = self.min_per_cell + int(cell_proportion * remaining)
                # Don't exceed what's available in the cell
                cell_target = min(cell_target, cell_count)
                features_per_cell[cell_key] = cell_target

        # Select features from each cell
        selected_indices = []
        for cell_key, cell_kps in grid_cells.items():
            target_count = features_per_cell[cell_key]
            # Sort by response strength and take top N
            cell_kps_sorted = sorted(cell_kps, key=lambda x: x[1], reverse=True)
            cell_selected = [idx for idx, _ in cell_kps_sorted[:target_count]]
            selected_indices.extend(cell_selected)

        # If we exceeded target, trim by taking highest response globally
        if len(selected_indices) > self.target_features:
            # Get responses for selected
            selected_with_response = [(idx, keypoints[idx].response) for idx in selected_indices]
            selected_with_response.sort(key=lambda x: x[1], reverse=True)
            selected_indices = [idx for idx, _ in selected_with_response[:self.target_features]]

        # Extract selected keypoints and descriptors
        selected_kps = [keypoints[i] for i in selected_indices]
        selected_desc = descriptors[selected_indices]

        print(f"Spatial selection: {len(keypoints)} -> {len(selected_kps)} features")
        print(f"  Grid: {grid_h}x{grid_w} cells ({self.grid_size}px)")
        print(f"  Populated cells: {len(grid_cells)}")

        return selected_kps, selected_desc


class AdaptiveGridSelector(SpatialFeatureSelector):
    """
    More sophisticated selector with adaptive grid sizing.
    Uses finer grid in high-density areas, coarser in sparse areas.
    """

    def __init__(self, target_features: int = 10000, min_grid_size: int = 25,
                 max_grid_size: int = 100):
        """
        Initialize adaptive selector.

        Args:
            target_features: Target number of features to keep
            min_grid_size: Minimum grid size for dense areas
            max_grid_size: Maximum grid size for sparse areas
        """
        super().__init__(target_features, min_grid_size)
        self.min_grid_size = min_grid_size
        self.max_grid_size = max_grid_size

    # TODO: Implement adaptive grid sizing based on local density
    # For now, use uniform grid from parent class
