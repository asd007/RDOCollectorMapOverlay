"""
Analyze sensitivity of edge density detection for sub-1% zoom changes
"""
import numpy as np
import cv2
from scipy import ndimage
import matplotlib.pyplot as plt

def analyze_zoom_sensitivity():
    """Analyze if edge density can detect <1% zoom changes"""

    # Create synthetic test image with realistic edge density
    # Similar to game viewport with UI elements and terrain
    img_size = 1920, 864
    test_img = np.zeros(img_size, dtype=np.uint8)

    # Add various frequency content (terrain, UI, details)
    # Low frequency (terrain)
    x = np.linspace(0, 4*np.pi, img_size[1])
    y = np.linspace(0, 4*np.pi, img_size[0])
    X, Y = np.meshgrid(x, y)
    test_img += (50 * np.sin(X) * np.cos(Y)).astype(np.uint8)

    # Mid frequency (buildings, roads)
    test_img += (30 * np.sin(5*X) * np.cos(5*Y)).astype(np.uint8)

    # High frequency (UI elements, text)
    for i in range(0, img_size[1], 50):
        test_img[:, i:i+2] = 200
    for i in range(0, img_size[0], 50):
        test_img[i:i+2, :] = 200

    # Simulate gradual zoom from 100% to 99% (1% zoom in)
    zoom_factors = np.linspace(1.0, 0.99, 11)  # 0.1% steps

    edge_counts_full = []
    edge_counts_downsampled = []

    for zoom in zoom_factors:
        # Zoom in (crop and resize back)
        h, w = img_size
        new_h = int(h * zoom)
        new_w = int(w * zoom)

        # Center crop
        y1 = (h - new_h) // 2
        x1 = (w - new_w) // 2
        cropped = test_img[y1:y1+new_h, x1:x1+new_w]

        # Resize back to original size
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        # Method 1: Edge detection at full resolution
        edges_full = cv2.Canny(zoomed, 50, 150)
        edge_counts_full.append(np.sum(edges_full > 0))

        # Method 2: Edge detection at 120x54 (target resolution)
        downsampled = cv2.resize(zoomed, (120, 54), interpolation=cv2.INTER_AREA)
        edges_down = cv2.Canny(downsampled, 30, 90)
        edge_counts_downsampled.append(np.sum(edges_down > 0))

    # Analyze sensitivity
    edge_counts_full = np.array(edge_counts_full)
    edge_counts_downsampled = np.array(edge_counts_downsampled)

    # Normalize to percentage change
    edge_change_full = 100 * (edge_counts_full - edge_counts_full[0]) / edge_counts_full[0]
    edge_change_down = 100 * (edge_counts_downsampled - edge_counts_downsampled[0]) / edge_counts_downsampled[0]

    print("Zoom Detection Sensitivity Analysis")
    print("=" * 50)
    print(f"Original resolution (1920x864):")
    print(f"  Edge count at 100% zoom: {edge_counts_full[0]}")
    print(f"  Edge count at 99% zoom:  {edge_counts_full[-1]}")
    print(f"  Change: {edge_change_full[-1]:.2f}%")
    print(f"  Per 0.1% zoom: {edge_change_full[-1]/10:.3f}% edge change")
    print()
    print(f"Downsampled (120x54):")
    print(f"  Edge count at 100% zoom: {edge_counts_downsampled[0]}")
    print(f"  Edge count at 99% zoom:  {edge_counts_downsampled[-1]}")
    print(f"  Change: {edge_change_down[-1]:.2f}%")
    print(f"  Per 0.1% zoom: {edge_change_down[-1]/10:.3f}% edge change")
    print()

    # Statistical significance test
    # Add noise to simulate real conditions
    noise_samples = 100
    noisy_counts = []
    for _ in range(noise_samples):
        noisy_img = test_img + np.random.normal(0, 5, img_size).astype(np.uint8)
        noisy_down = cv2.resize(noisy_img, (120, 54), interpolation=cv2.INTER_AREA)
        noisy_edges = cv2.Canny(noisy_down, 30, 90)
        noisy_counts.append(np.sum(noisy_edges > 0))

    noise_std = np.std(noisy_counts)
    signal_per_01_percent = abs(edge_change_down[-1]/10) * edge_counts_downsampled[0] / 100
    snr = signal_per_01_percent / noise_std

    print(f"Noise Analysis (120x54):")
    print(f"  Noise std dev: {noise_std:.1f} pixels")
    print(f"  Signal per 0.1% zoom: {signal_per_01_percent:.1f} pixels")
    print(f"  Signal-to-Noise Ratio: {snr:.2f}")
    print(f"  Minimum detectable zoom: {0.1 * 3/snr:.3f}% (3-sigma threshold)")

    return zoom_factors, edge_change_full, edge_change_down, snr

# Run analysis
zoom_factors, edge_change_full, edge_change_down, snr = analyze_zoom_sensitivity()

print("\n" + "=" * 50)
print("CONCLUSION:")
if snr > 3:
    print("[SUCCESS] Edge density CAN detect <1% zoom changes at 120x54")
    print(f"Minimum reliable detection: ~{0.1 * 3/snr:.3f}% zoom")
else:
    print("[WARNING] Edge density unreliable for <1% zoom at 120x54")
    print(f"Need at least {0.1 * snr:.2f}% zoom for reliable detection")