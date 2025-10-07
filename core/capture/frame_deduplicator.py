"""
Frame deduplication for continuous capture pipeline.
Detects duplicate frames to avoid redundant processing.
"""

import numpy as np
import xxhash
import cv2
from typing import Optional, Tuple
from dataclasses import dataclass
import time


@dataclass
class FrameStats:
    """Statistics for frame deduplication performance."""
    total_frames: int = 0
    duplicate_frames: int = 0
    hash_time_ms: float = 0.0
    last_frame_time: float = 0.0

    @property
    def duplicate_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.duplicate_frames / self.total_frames

    @property
    def avg_hash_time_ms(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.hash_time_ms / self.total_frames


class FrameDeduplicator:
    """
    High-performance frame deduplication using xxHash.

    Strategy:
    1. Downsample BGRA frame to reduce data (optional)
    2. Use xxHash64 for fast hashing
    3. Compare hash to detect exact duplicates
    4. Track statistics for monitoring
    """

    def __init__(self,
                 downsample_factor: int = 4,
                 use_stride: bool = True,
                 stride_factor: int = 4):
        """
        Initialize frame deduplicator.

        Args:
            downsample_factor: Factor to downsample frame before hashing (1=no downsampling)
            use_stride: Whether to use pixel stride for even faster hashing
            stride_factor: Skip every Nth pixel when stride is enabled
        """
        self.downsample_factor = downsample_factor
        self.use_stride = use_stride
        self.stride_factor = stride_factor

        self.last_hash = None
        self.stats = FrameStats()

        # Pre-allocate buffer for downsampled frame
        self.downsample_buffer = None

    def is_duplicate(self, frame: np.ndarray) -> Tuple[bool, str]:
        """
        Check if frame is duplicate of previous frame.

        Args:
            frame: BGRA frame buffer (1920x1080x4)

        Returns:
            Tuple of (is_duplicate, frame_hash)
        """
        start_time = time.perf_counter()

        # Prepare data for hashing
        if self.downsample_factor > 1:
            # Downsample for faster hashing
            # Use nearest neighbor for speed
            h, w = frame.shape[:2]
            new_h = h // self.downsample_factor
            new_w = w // self.downsample_factor

            # Use cv2.resize with INTER_NEAREST for maximum speed
            if self.downsample_buffer is None or self.downsample_buffer.shape != (new_h, new_w, 4):
                self.downsample_buffer = np.empty((new_h, new_w, 4), dtype=np.uint8)

            cv2.resize(frame, (new_w, new_h), dst=self.downsample_buffer, interpolation=cv2.INTER_NEAREST)
            hash_data = self.downsample_buffer
        else:
            hash_data = frame

        # Apply stride if enabled (sample every Nth pixel)
        if self.use_stride and self.stride_factor > 1:
            # Use numpy slicing for efficient striding
            hash_data = hash_data[::self.stride_factor, ::self.stride_factor]

        # Compute hash using xxHash64 (fastest non-cryptographic hash)
        # Convert to bytes view for hashing (no copy)
        frame_hash = xxhash.xxh64_hexdigest(hash_data.tobytes())

        # Update statistics
        hash_time = (time.perf_counter() - start_time) * 1000
        self.stats.total_frames += 1
        self.stats.hash_time_ms += hash_time
        self.stats.last_frame_time = hash_time

        # Check for duplicate
        is_duplicate = (frame_hash == self.last_hash)
        if is_duplicate:
            self.stats.duplicate_frames += 1

        self.last_hash = frame_hash
        return is_duplicate, frame_hash

    def reset(self):
        """Reset deduplicator state."""
        self.last_hash = None
        self.stats = FrameStats()
        self.downsample_buffer = None


class PerceptualDeduplicator:
    """
    Alternative deduplicator using perceptual hashing for near-duplicates.
    More tolerant to minor changes (UI updates, lighting).
    """

    def __init__(self, threshold: float = 0.95):
        """
        Initialize perceptual deduplicator.

        Args:
            threshold: Similarity threshold (0.0-1.0)
        """
        self.threshold = threshold
        self.last_dhash = None
        self.stats = FrameStats()

    def _compute_dhash(self, frame: np.ndarray, hash_size: int = 8) -> int:
        """
        Compute difference hash (dHash) for perceptual comparison.

        Args:
            frame: BGRA frame
            hash_size: Size of hash grid (8 = 64 bit hash)

        Returns:
            Integer hash value
        """
        # Convert BGRA to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

        # Resize to (hash_size+1) x hash_size
        resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)

        # Compute horizontal gradient
        diff = resized[:, 1:] > resized[:, :-1]

        # Convert to integer hash
        return sum([2**i for i, v in enumerate(diff.flatten()) if v])

    def is_duplicate(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Check if frame is perceptually similar to previous frame.

        Args:
            frame: BGRA frame buffer

        Returns:
            Tuple of (is_duplicate, similarity_score)
        """
        start_time = time.perf_counter()

        # Compute perceptual hash
        dhash = self._compute_dhash(frame)

        # Update statistics
        hash_time = (time.perf_counter() - start_time) * 1000
        self.stats.total_frames += 1
        self.stats.hash_time_ms += hash_time
        self.stats.last_frame_time = hash_time

        if self.last_dhash is None:
            self.last_dhash = dhash
            return False, 0.0

        # Calculate Hamming distance
        hamming_distance = bin(dhash ^ self.last_dhash).count('1')
        similarity = 1.0 - (hamming_distance / 64.0)

        is_duplicate = similarity >= self.threshold
        if is_duplicate:
            self.stats.duplicate_frames += 1

        self.last_dhash = dhash
        return is_duplicate, similarity

    def reset(self):
        """Reset deduplicator state."""
        self.last_dhash = None
        self.stats = FrameStats()


class FastPixelComparator:
    """
    Ultra-fast pixel comparison using sparse sampling.
    Best for detecting any change quickly.
    """

    def __init__(self, sample_points: int = 100):
        """
        Initialize pixel comparator.

        Args:
            sample_points: Number of pixels to sample
        """
        self.sample_points = sample_points
        self.sample_indices = None
        self.last_samples = None
        self.stats = FrameStats()

    def _generate_sample_indices(self, shape: Tuple[int, int, int]):
        """Generate random sample indices for consistent comparison."""
        h, w, c = shape
        # Use deterministic random for consistency
        rng = np.random.RandomState(42)

        # Generate sample points
        y_indices = rng.randint(0, h, self.sample_points)
        x_indices = rng.randint(0, w, self.sample_points)

        return y_indices, x_indices

    def is_duplicate(self, frame: np.ndarray) -> Tuple[bool, int]:
        """
        Check if frame is duplicate using sparse pixel sampling.

        Args:
            frame: BGRA frame buffer

        Returns:
            Tuple of (is_duplicate, changed_pixels)
        """
        start_time = time.perf_counter()

        # Generate sample indices on first run
        if self.sample_indices is None:
            self.sample_indices = self._generate_sample_indices(frame.shape)

        # Sample pixels
        y_idx, x_idx = self.sample_indices
        samples = frame[y_idx, x_idx].flatten()

        # Update statistics
        hash_time = (time.perf_counter() - start_time) * 1000
        self.stats.total_frames += 1
        self.stats.hash_time_ms += hash_time
        self.stats.last_frame_time = hash_time

        if self.last_samples is None:
            self.last_samples = samples
            return False, 0

        # Compare samples
        changed_pixels = np.sum(samples != self.last_samples)
        is_duplicate = (changed_pixels == 0)

        if is_duplicate:
            self.stats.duplicate_frames += 1

        self.last_samples = samples
        return is_duplicate, changed_pixels

    def reset(self):
        """Reset comparator state."""
        self.sample_indices = None
        self.last_samples = None
        self.stats = FrameStats()