"""Simple AKAZE matcher - baseline approach without pyramids or cascade"""

import cv2
import numpy as np
from typing import Dict, Optional, Tuple
from matching.spatial_feature_selector import SpatialFeatureSelector
from matching.spatial_keypoint_index import SpatialKeypointIndex


class SimpleMatcher:
    """
    Simple baseline matcher using AKAZE features.
    No pyramids, no cascade - just straightforward feature matching.
    """

    def __init__(self,
                 max_features: int = 10000,
                 ratio_test_threshold: float = 0.75,
                 min_inliers: int = 10,
                 min_inlier_ratio: float = 0.5,
                 ransac_threshold: float = 5.0,
                 use_spatial_distribution: bool = True,
                 spatial_grid_size: int = 50,
                 max_screenshot_features: int = 300,
                 use_flann: bool = True,
                 use_gpu: bool = True):
        """
        Initialize simple matcher.

        Args:
            max_features: Maximum number of AKAZE features to keep from map (default 10000)
            ratio_test_threshold: Lowe's ratio test threshold (0.7-0.8)
            min_inliers: Minimum absolute number of inliers (fallback for few matches)
            min_inlier_ratio: Minimum ratio of inliers to good matches (0.0-1.0, default 0.5)
            ransac_threshold: RANSAC reprojection error threshold
            use_spatial_distribution: Use spatial selection to preserve density distribution
            spatial_grid_size: Grid cell size for spatial distribution (pixels)
            max_screenshot_features: Maximum features to keep from screenshot (default 300)
            use_flann: Use FLANN matcher for 20-30% faster matching (default True)
            use_gpu: Try to use GPU acceleration if available (default True)
        """
        self.max_features = max_features
        self.max_screenshot_features = max_screenshot_features
        self.ratio_test_threshold = ratio_test_threshold
        self.min_inliers = min_inliers
        self.min_inlier_ratio = min_inlier_ratio
        self.ransac_threshold = ransac_threshold
        self.use_spatial_distribution = use_spatial_distribution
        self.use_flann = use_flann

        # Check GPU availability
        self.gpu_available = False
        self.use_gpu = use_gpu
        if use_gpu:
            try:
                # Check if CUDA is available
                cuda_count = cv2.cuda.getCudaEnabledDeviceCount()
                if cuda_count > 0:
                    self.gpu_available = True
                    print(f"GPU acceleration available: {cuda_count} CUDA device(s) detected")
            except:
                pass  # CUDA not available, will use CPU

        # Create AKAZE detector with tuned parameters for better distribution
        # Note: For scale-aware optimization, use create_scale_optimized_detector()
        self.detector = cv2.AKAZE_create(
            descriptor_type=cv2.AKAZE_DESCRIPTOR_MLDB,  # Most distinctive
            descriptor_size=0,  # Full size
            descriptor_channels=3,  # Multi-channel for robustness
            threshold=0.0008,  # Lower threshold for more features in sparse areas
            nOctaves=4,  # Standard octaves
            nOctaveLayers=4,  # More layers for better scale coverage
            diffusivity=cv2.KAZE_DIFF_PM_G2  # Edge-preserving diffusion
        )

        # Create GPU ORB detector if available (for fast coarse matching)
        # Note: AKAZE doesn't have CUDA support, so we use ORB for GPU acceleration
        self.gpu_orb = None
        if self.gpu_available:
            try:
                self.gpu_orb = cv2.cuda_ORB.create(
                    nfeatures=500,
                    scaleFactor=1.2,
                    nlevels=4,
                    edgeThreshold=15,
                    firstLevel=0,
                    WTA_K=2,
                    scoreType=cv2.ORB_HARRIS_SCORE,
                    patchSize=31,
                    fastThreshold=20
                )
                print("GPU ORB detector initialized for fast coarse matching")
            except Exception as e:
                print(f"GPU ORB initialization failed: {e}")
                self.gpu_orb = None

        # Cache for scale-optimized detectors
        self._optimized_detectors = {}

        # Create spatial selector if enabled
        if use_spatial_distribution:
            self.spatial_selector = SpatialFeatureSelector(
                target_features=max_features,
                grid_size=spatial_grid_size
            )

        # Create matcher (FLANN for speed or BFMatcher for accuracy)
        if use_flann:
            # FLANN with LSH index for binary descriptors (20-30% faster)
            FLANN_INDEX_LSH = 6
            index_params = dict(
                algorithm=FLANN_INDEX_LSH,
                table_number=12,  # 12 hash tables for good accuracy
                key_size=20,      # Hash key size
                multi_probe_level=2  # Multi-probe for better recall
            )
            search_params = dict(checks=50)  # Higher = more accurate but slower
            self.matcher = cv2.FlannBasedMatcher(index_params, search_params)
        else:
            # BFMatcher with Hamming distance (for binary descriptors)
            self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

    def create_scale_optimized_detector(self, scale: float):
        """
        Create detector optimized for specific scale.

        For small scales (<=0.25): Use GPU ORB if available (3-5x faster)
        For medium scales (0.5): Use optimized AKAZE (fewer octaves/layers)
        For large scales (>=0.7): Use standard AKAZE

        Args:
            scale: Screenshot scale (0.25, 0.5, 0.7, 1.0, etc.)

        Returns:
            Optimized detector (AKAZE or GPU ORB)
        """
        # Cache optimized detectors
        if scale in self._optimized_detectors:
            return self._optimized_detectors[scale]

        # For very small scales, use GPU ORB if available (much faster)
        if scale <= 0.25 and self.gpu_orb is not None:
            # Return marker for GPU ORB (handled specially in match())
            self._optimized_detectors[scale] = 'gpu_orb'
            return 'gpu_orb'

        if scale >= 0.5:
            # Optimized for speed at higher scales
            detector = cv2.AKAZE_create(
                descriptor_type=cv2.AKAZE_DESCRIPTOR_MLDB,
                descriptor_size=0,
                descriptor_channels=3,
                threshold=0.001,  # Higher threshold = fewer features
                nOctaves=3,  # Reduced from 4 (faster)
                nOctaveLayers=3,  # Reduced from 4 (faster)
                diffusivity=cv2.KAZE_DIFF_PM_G2
            )
        else:
            # Keep default parameters for small scales
            detector = self.detector

        self._optimized_detectors[scale] = detector
        return detector

    def compute_reference_features(self, reference_map: np.ndarray):
        """
        Pre-compute features for reference map (call once during initialization).

        Args:
            reference_map: Preprocessed reference map (detection space, grayscale)
        """
        print("Computing reference map features...")
        kp, desc = self.detector.detectAndCompute(reference_map, None)

        if desc is None or len(kp) == 0:
            raise ValueError("Failed to detect features in reference map")

        print(f"Detected {len(kp)} total features")

        # Select features based on strategy
        if self.max_features > 0 and len(kp) > self.max_features:
            if self.use_spatial_distribution:
                # Use spatial distribution to preserve density
                print("Applying spatial distribution selection...")
                self.kp_map, self.desc_map = self.spatial_selector.select_features(
                    kp, desc, reference_map.shape
                )
                print(f"Reference map features: {len(self.kp_map)} (spatially distributed from {len(kp)})")
            else:
                # Old method: Sort by response (strength) and keep top features
                indices = np.argsort([k.response for k in kp])[::-1][:self.max_features]
                self.kp_map = [kp[i] for i in indices]
                self.desc_map = desc[indices]
                print(f"Reference map features: {len(self.kp_map)} (top responses from {len(kp)})")
        else:
            self.kp_map = kp
            self.desc_map = desc
            print(f"Reference map features: {len(self.kp_map)}")

        # Build spatial index for ROI-based filtering
        print("Building spatial index for ROI filtering...")
        self.spatial_index = SpatialKeypointIndex(self.kp_map)
        print(f"Spatial index ready for {len(self.kp_map)} keypoints")

    def match(self, screenshot: np.ndarray, reference_map: np.ndarray = None,
              roi: Optional[Tuple[float, float, float, float]] = None,
              roi_expansion: float = 1.1) -> Dict:
        """
        Match screenshot against reference map.

        Args:
            screenshot: Preprocessed screenshot image (grayscale)
            reference_map: Preprocessed reference map (optional, used if features not pre-computed)
            roi: Optional ROI for filtering map features (center_x, center_y, viewport_w, viewport_h)
                 If provided, only matches against map keypoints within expanded region
            roi_expansion: ROI expansion factor (default 1.1 = 10% larger, 1.05 = 5% larger)

        Returns:
            Dictionary with match results:
                - success: bool
                - map_x, map_y, map_w, map_h: viewport position in map coordinates
                - confidence: match confidence (inlier ratio)
                - inliers: number of inlier matches
                - homography: 3x3 homography matrix (or None)
                - roi_filter_applied: bool (True if ROI filtering was used)
                - roi_keypoints: int (number of keypoints in ROI, if filtered)
        """
        # Detect features in screenshot
        kp, desc = self.detector.detectAndCompute(screenshot, None)

        if desc is None or len(kp) == 0:
            return self._failed_result("No features detected in screenshot")

        # Apply hybrid spatial-strength selection to screenshot features
        if self.max_screenshot_features > 0 and len(kp) > self.max_screenshot_features:
            # Adaptive ratio based on feature density
            feature_density = len(kp) / (screenshot.shape[0] * screenshot.shape[1] / 1000)
            if feature_density < 1.5:  # Sparse scene
                min_per_cell_ratio = 0.6  # More spatial distribution
            elif feature_density > 3.0:  # Dense scene
                min_per_cell_ratio = 0.3  # More strength-based
            else:  # Normal density
                min_per_cell_ratio = 0.4

            # Use hybrid selection: guarantee spatial coverage + preserve strong features
            selected_indices = self._select_features_hybrid(
                kp,
                screenshot.shape[:2],
                target_count=self.max_screenshot_features,
                min_per_cell_ratio=min_per_cell_ratio
            )
            kp_screenshot = [kp[i] for i in selected_indices]
            desc_screenshot = desc[selected_indices]
        else:
            kp_screenshot = kp
            desc_screenshot = desc

        # Use pre-computed map features if available, otherwise compute now
        if not hasattr(self, 'kp_map') or not hasattr(self, 'desc_map'):
            if reference_map is None:
                return self._failed_result("No reference map features available")
            kp_map, desc_map = self.detector.detectAndCompute(reference_map, None)
            roi_filter_applied = False
            roi_keypoints = len(kp_map)
        else:
            # Apply ROI filtering if provided
            if roi and hasattr(self, 'spatial_index'):
                center_x, center_y, viewport_w, viewport_h = roi

                # Query spatial index with configurable expansion
                roi_indices = self.spatial_index.query_viewport_expanded(
                    center_x, center_y, viewport_w, viewport_h, expansion=roi_expansion
                )

                if len(roi_indices) > 0:
                    # Filter keypoints and descriptors to ROI
                    kp_map = [self.kp_map[i] for i in roi_indices]
                    desc_map = self.desc_map[roi_indices]
                    roi_filter_applied = True
                    roi_keypoints = len(roi_indices)

                    print(f"[ROI Filter] Using {roi_keypoints}/{len(self.kp_map)} keypoints "
                          f"({100*roi_keypoints/len(self.kp_map):.1f}%)")
                else:
                    # ROI too restrictive, fall back to full search
                    print(f"[ROI Filter] No keypoints in ROI, falling back to full search")
                    kp_map, desc_map = self.kp_map, self.desc_map
                    roi_filter_applied = False
                    roi_keypoints = len(kp_map)
            else:
                kp_map, desc_map = self.kp_map, self.desc_map
                roi_filter_applied = False
                roi_keypoints = len(kp_map)

        if desc_map is None or len(kp_map) == 0:
            return self._failed_result("No features detected in reference map")

        # Match descriptors using k-nearest neighbors (k=2 for ratio test)
        if len(kp_map) < 2:
            return self._failed_result("Not enough map features for matching")

        matches = self.matcher.knnMatch(desc_screenshot, desc_map, k=2)

        # Apply Lowe's ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < self.ratio_test_threshold * n.distance:
                    good_matches.append(m)

        if len(good_matches) < self.min_inliers:
            return self._failed_result(f"Not enough good matches ({len(good_matches)} < {self.min_inliers})")

        # Extract matched keypoint locations
        src_pts = np.float32([kp_screenshot[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_map[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Find homography using RANSAC
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, self.ransac_threshold)

        if H is None:
            return self._failed_result("Homography estimation failed")

        # Count inliers
        inliers = np.sum(mask)
        confidence = inliers / len(good_matches)

        # Adaptive inlier threshold: use percentage of good matches, with absolute minimum
        required_inliers = max(self.min_inliers, int(len(good_matches) * self.min_inlier_ratio))
        if inliers < required_inliers:
            return self._failed_result(f"Not enough inliers ({inliers} < {required_inliers}, {confidence:.1%} of {len(good_matches)} matches)")

        # Calculate viewport position using homography
        h, w = screenshot.shape
        corners_screenshot = np.float32([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]
        ]).reshape(-1, 1, 2)

        corners_map = cv2.perspectiveTransform(corners_screenshot, H)

        # Calculate bounding box in map coordinates
        x_coords = corners_map[:, 0, 0]
        y_coords = corners_map[:, 0, 1]

        map_x = int(np.min(x_coords))
        map_y = int(np.min(y_coords))
        map_w = int(np.max(x_coords) - map_x)
        map_h = int(np.max(y_coords) - map_y)

        return {
            'success': True,
            'map_x': map_x,
            'map_y': map_y,
            'map_w': map_w,
            'map_h': map_h,
            'confidence': float(confidence),
            'inliers': int(inliers),
            'homography': H,
            'total_matches': len(good_matches),
            'roi_filter_applied': roi_filter_applied,
            'roi_keypoints': roi_keypoints
        }

    def _select_features_hybrid(self, keypoints, image_shape, target_count=300, min_per_cell_ratio=0.4):
        """
        Hybrid feature selection: spatial distribution + response strength.

        Args:
            keypoints: List of cv2.KeyPoint objects
            image_shape: (height, width) of the image
            target_count: Target number of features to select
            min_per_cell_ratio: Fraction of features reserved for spatial distribution

        Returns:
            Array of selected keypoint indices
        """
        if len(keypoints) <= target_count:
            return np.arange(len(keypoints))

        h, w = image_shape

        # Adaptive grid size based on target count (aiming for ~2-3 features per cell initially)
        grid_size = int(np.sqrt((h * w) / (target_count / 2.5)))
        grid_size = max(30, min(100, grid_size))  # Clamp between 30-100 pixels

        grid_h = (h + grid_size - 1) // grid_size
        grid_w = (w + grid_size - 1) // grid_size

        # Organize keypoints by grid cell
        grid_features = {}
        for idx, kp in enumerate(keypoints):
            grid_y = min(int(kp.pt[1] / grid_size), grid_h - 1)
            grid_x = min(int(kp.pt[0] / grid_size), grid_w - 1)
            cell_key = (grid_y, grid_x)

            if cell_key not in grid_features:
                grid_features[cell_key] = []
            grid_features[cell_key].append((idx, kp.response))

        # Phase 1: Spatial distribution (guarantee minimum coverage)
        spatial_count = int(target_count * min_per_cell_ratio)
        features_per_cell = max(1, spatial_count // len(grid_features)) if grid_features else 1

        selected_spatial = set()
        for cell_key, features in grid_features.items():
            # Sort by response strength within each cell
            features.sort(key=lambda x: x[1], reverse=True)
            # Take top N from this cell
            for idx, _ in features[:features_per_cell]:
                selected_spatial.add(idx)
                if len(selected_spatial) >= spatial_count:
                    break
            if len(selected_spatial) >= spatial_count:
                break

        # Phase 2: Response strength (fill remaining slots with strongest features)
        remaining_count = target_count - len(selected_spatial)
        if remaining_count > 0:
            # Get all indices sorted by response strength
            all_indices_by_strength = np.argsort([kp.response for kp in keypoints])[::-1]

            selected_strength = set()
            for idx in all_indices_by_strength:
                if idx not in selected_spatial:
                    selected_strength.add(idx)
                    if len(selected_strength) >= remaining_count:
                        break
        else:
            selected_strength = set()

        # Combine and return as sorted array
        selected_indices = np.array(sorted(selected_spatial | selected_strength))
        return selected_indices

    def _failed_result(self, error: str) -> Dict:
        """Return a failed match result"""
        return {
            'success': False,
            'error': error,
            'map_x': 0,
            'map_y': 0,
            'map_w': 0,
            'map_h': 0,
            'confidence': 0.0,
            'inliers': 0,
            'homography': None
        }
