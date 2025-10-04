"""
Image preprocessing for enhanced feature matching.
Q10 Method: Posterize (16 bins) + CLAHE for flat bright areas and meaningful features.
"""

import cv2
import numpy as np
from typing import Optional


class ImagePreprocessor:
    """Preprocessor using Q10 + custom LUT for terrain edge enhancement"""

    def __init__(self, bins: int = 16, clahe_clip: float = 2.0, clahe_grid: tuple = (8, 8),
                 use_custom_lut: bool = True):
        """
        Initialize preprocessor.

        Args:
            bins: Number of gray level bins for initial posterization (default 16)
            clahe_clip: CLAHE clip limit (default 2.0)
            clahe_grid: CLAHE tile grid size (default 8x8)
            use_custom_lut: Use custom LUT to enhance terrain edges (default True)
        """
        self.bins = bins
        self.use_custom_lut = use_custom_lut
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=clahe_grid)

        # Create custom LUT for terrain edge enhancement
        if use_custom_lut:
            self.custom_lut = self._create_terrain_lut()

    def _create_terrain_lut(self) -> np.ndarray:
        """
        Create custom LUT to enhance terrain edges.

        Based on Q10 histogram analysis:
        - Lightest grays (200+): flat terrain  ->  push to white
        - 2nd lightest (180-199): level changes  ->  pull down to create hard edges
        - Mid-dark (100-179): text/roads  ->  mid-gray
        - Darkest (<100):  ->  black

        Returns:
            256-element LUT array
        """
        lut = np.zeros(256, dtype=np.uint8)

        # Darkest: 0-99  ->  0-10
        lut[0:100] = np.linspace(0, 10, 100).astype(np.uint8)

        # Mid-dark: 100-179  ->  11-50
        lut[100:180] = np.linspace(11, 50, 80).astype(np.uint8)

        # 2nd lightest: 180-199  ->  51-100 (create hard edge for level changes)
        lut[180:200] = np.linspace(51, 100, 20).astype(np.uint8)

        # Lightest (flat terrain): 200-255  ->  220-255 (push to white)
        lut[200:256] = np.linspace(220, 255, 56).astype(np.uint8)

        return lut

    def posterize(self, img: np.ndarray, bins: Optional[int] = None) -> np.ndarray:
        """
        Posterize image to reduce gray levels.

        Args:
            img: Grayscale image
            bins: Number of bins (uses self.bins if None)

        Returns:
            Posterized image with reduced gray levels
        """
        if bins is None:
            bins = self.bins

        # Posterize: (value // bin_size) * bin_size
        bin_size = 256 // bins
        posterized = (img // bin_size) * bin_size
        return posterized.astype(np.uint8)

    def preprocess_grayscale(self, img_gray: np.ndarray) -> np.ndarray:
        """
        Apply Q10 + custom LUT preprocessing to grayscale image.

        Args:
            img_gray: Grayscale image (1 channel)

        Returns:
            Preprocessed grayscale image
        """
        # Stage 1: Posterize to 16 bins
        posterized = self.posterize(img_gray, bins=self.bins)

        # Stage 2: CLAHE to enhance local contrast
        enhanced = self.clahe.apply(posterized)

        # Stage 3: Apply custom LUT to enhance terrain edges
        if self.use_custom_lut:
            final = cv2.LUT(enhanced, self.custom_lut)
            return final

        return enhanced

    def preprocess_color_then_gray(self, img_color: np.ndarray) -> np.ndarray:
        """
        Posterize in color space, then convert to grayscale + CLAHE.
        Tests if color posterization before grayscale helps.

        Args:
            img_color: Color image (BGR, 3 channels)

        Returns:
            Preprocessed grayscale image
        """
        # Posterize each color channel
        posterized_color = self.posterize(img_color)

        # Convert to grayscale
        gray = cv2.cvtColor(posterized_color, cv2.COLOR_BGR2GRAY)

        # Apply CLAHE
        enhanced = self.clahe.apply(gray)
        return enhanced

    def preprocess_color_image(self, img_color: np.ndarray, posterize_before_gray: bool = False) -> np.ndarray:
        """
        Main preprocessing for color images.

        Args:
            img_color: Color image (BGR, 3 channels)
            posterize_before_gray: If True, posterize in color then convert to gray.
                                   If False, convert to gray then posterize.

        Returns:
            Preprocessed grayscale image
        """
        if posterize_before_gray:
            # Test option: posterize color channels first
            return self.preprocess_color_then_gray(img_color)
        else:
            # Default: convert to gray first, then posterize + CLAHE
            gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
            return self.preprocess_grayscale(gray)

    def preprocess(self, img: np.ndarray, posterize_before_gray: bool = False) -> np.ndarray:
        """
        Main preprocessing function - handles both color and grayscale.

        Args:
            img: Input image (color or grayscale)
            posterize_before_gray: If True and color, posterize before grayscale conversion

        Returns:
            Preprocessed grayscale image
        """
        # Check if grayscale or color
        if len(img.shape) == 2:
            # Already grayscale
            return self.preprocess_grayscale(img)
        else:
            # Color image
            return self.preprocess_color_image(img, posterize_before_gray=posterize_before_gray)


# Create singleton instance with custom LUT enabled
PREPROCESSOR = ImagePreprocessor(bins=16, clahe_clip=2.0, clahe_grid=(8, 8), use_custom_lut=True)


def preprocess_for_matching(img: np.ndarray, posterize_before_gray: bool = False) -> np.ndarray:
    """
    Convenience function for preprocessing images for feature matching.

    Args:
        img: Input image (color or grayscale)
        posterize_before_gray: If True, posterize color before grayscale conversion

    Returns:
        Preprocessed grayscale image
    """
    return PREPROCESSOR.preprocess(img, posterize_before_gray=posterize_before_gray)


def preprocess_with_resize(img: np.ndarray, target_size: tuple = None, scale: float = None) -> np.ndarray:
    """
    Optimized preprocessing: Resize in grayscale BEFORE posterization.

    This order preserves quality because resize interpolation works better
    with 256 gray levels than with posterized discrete values.

    Args:
        img: Input image (color or grayscale)
        target_size: (width, height) tuple, or None
        scale: Scale factor (e.g. 0.5), or None

    Returns:
        Preprocessed and resized grayscale image
    """
    # Convert to grayscale (256 levels - good for resize interpolation)
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Resize in 256-level grayscale (optimal interpolation quality)
    if target_size is not None:
        resized = cv2.resize(gray, target_size, interpolation=cv2.INTER_AREA)
    elif scale is not None:
        h, w = gray.shape
        resized = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        resized = gray

    # Now apply posterization + CLAHE + LUT on the resized image
    return PREPROCESSOR.preprocess_grayscale(resized)
