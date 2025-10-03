#!/usr/bin/env python3
"""
Benchmark screenshot capture: dxcam vs mss

Key benefits of dxcam:
1. GPU-level capture (DirectX Desktop Duplication API)
2. Faster than CPU-based methods
3. Captures directly from frame buffer, EXCLUDING overlay windows
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import numpy as np
import cv2

# Test imports
try:
    import dxcam
    DXCAM_AVAILABLE = True
except ImportError:
    DXCAM_AVAILABLE = False
    print("Warning: dxcam not available")

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    print("Warning: mss not available")

from config import SCREENSHOT


def benchmark_dxcam(iterations=50):
    """Benchmark dxcam capture performance"""
    if not DXCAM_AVAILABLE:
        return None

    print(f"\nBenchmarking dxcam ({iterations} iterations)...")

    # Create camera (output_idx=0 for primary monitor, BGR output for OpenCV)
    camera = dxcam.create(output_idx=SCREENSHOT.MONITOR_INDEX - 1, output_color="BGR")

    # Warmup
    for _ in range(5):
        frame = camera.grab()

    # Benchmark
    times = []
    for i in range(iterations):
        start = time.time()

        # Capture frame
        frame = camera.grab()

        # Crop to top 80%
        if frame is not None:
            crop_height = int(frame.shape[0] * SCREENSHOT.CROP_TOP_PERCENTAGE)
            frame_cropped = frame[:crop_height, :, :]

        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    del camera  # Clean up

    return times


def benchmark_mss(iterations=50):
    """Benchmark mss capture performance"""
    if not MSS_AVAILABLE:
        return None

    print(f"\nBenchmarking mss ({iterations} iterations)...")

    # Warmup
    with mss.mss() as sct:
        monitor = sct.monitors[SCREENSHOT.MONITOR_INDEX]
        for _ in range(5):
            screenshot = sct.grab(monitor)

    # Benchmark
    times = []
    for i in range(iterations):
        start = time.time()

        with mss.mss() as sct:
            monitor = sct.monitors[SCREENSHOT.MONITOR_INDEX]

            # Crop to top 80%
            monitor_cropped = {
                'left': monitor['left'],
                'top': monitor['top'],
                'width': monitor['width'],
                'height': int(monitor['height'] * SCREENSHOT.CROP_TOP_PERCENTAGE)
            }

            screenshot = sct.grab(monitor_cropped)
            img = np.array(screenshot)

            # Convert BGRA to BGR
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    return times


def main():
    print("=" * 80)
    print("SCREENSHOT CAPTURE BENCHMARK")
    print("=" * 80)
    print(f"\nMonitor: {SCREENSHOT.MONITOR_INDEX}")
    print(f"Crop: Top {int(SCREENSHOT.CROP_TOP_PERCENTAGE * 100)}%")

    results = {}

    # Benchmark dxcam
    if DXCAM_AVAILABLE:
        dxcam_times = benchmark_dxcam()
        if dxcam_times:
            results['dxcam'] = dxcam_times
            print(f"  Mean: {np.mean(dxcam_times):.2f}ms")
            print(f"  Median: {np.median(dxcam_times):.2f}ms")
            print(f"  Min: {np.min(dxcam_times):.2f}ms")
            print(f"  Max: {np.max(dxcam_times):.2f}ms")
            print(f"  Std: {np.std(dxcam_times):.2f}ms")

    # Benchmark mss
    if MSS_AVAILABLE:
        mss_times = benchmark_mss()
        if mss_times:
            results['mss'] = mss_times
            print(f"  Mean: {np.mean(mss_times):.2f}ms")
            print(f"  Median: {np.median(mss_times):.2f}ms")
            print(f"  Min: {np.min(mss_times):.2f}ms")
            print(f"  Max: {np.max(mss_times):.2f}ms")
            print(f"  Std: {np.std(mss_times):.2f}ms")

    # Comparison
    if 'dxcam' in results and 'mss' in results:
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)

        dxcam_mean = np.mean(results['dxcam'])
        mss_mean = np.mean(results['mss'])

        speedup = mss_mean / dxcam_mean
        time_saved = mss_mean - dxcam_mean

        print(f"\ndxcam:  {dxcam_mean:.2f}ms")
        print(f"mss:    {mss_mean:.2f}ms")
        print(f"\nSpeedup: {speedup:.2f}x")
        print(f"Time saved: {time_saved:.2f}ms per capture")

        if speedup > 1.0:
            print(f"\n[SUCCESS] dxcam is {speedup:.2f}x FASTER")
        else:
            print(f"\n[WARNING] dxcam is {1/speedup:.2f}x slower")

        print("\nKey benefits of dxcam:")
        print("  1. GPU-level capture (DirectX Desktop Duplication API)")
        print("  2. Captures from frame buffer BEFORE overlay compositing")
        print("  3. Overlay windows are NOT included in captured frames")
        print("  4. Lower CPU usage")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
