"""
Test various preprocessing strategies for RDO map overlay.
Tests different methods on test.png to find optimal preprocessing.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Load test image (from tests/data/)
test_image_path = Path(__file__).parent / "data" / "test.png"
img_color = cv2.imread(str(test_image_path))
img_gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

print(f"Test image shape: {img_color.shape}")
print(f"Image dtype: {img_color.dtype}")
print(f"Value range: {img_color.min()} to {img_color.max()}")

# Store all preprocessing results
results = {}

# 1. BASELINE - No preprocessing
results['1. Original Grayscale'] = img_gray.copy()

# 2. ADAPTIVE THRESHOLDING - Various methods
# Adaptive Mean
adaptive_mean = cv2.adaptiveThreshold(
    img_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2
)
results['2. Adaptive Mean (11,2)'] = adaptive_mean

adaptive_mean_inv = cv2.adaptiveThreshold(
    img_gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 11, 2
)
results['3. Adaptive Mean INV (11,2)'] = adaptive_mean_inv

# Adaptive Gaussian
adaptive_gauss = cv2.adaptiveThreshold(
    img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
)
results['4. Adaptive Gauss (11,2)'] = adaptive_gauss

adaptive_gauss_inv = cv2.adaptiveThreshold(
    img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
)
results['5. Adaptive Gauss INV (11,2)'] = adaptive_gauss_inv

# Try different block sizes and constants
adaptive_gauss_large = cv2.adaptiveThreshold(
    img_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5
)
results['6. Adaptive Gauss INV (21,5)'] = adaptive_gauss_large

# 3. CLAHE - Contrast Limited Adaptive Histogram Equalization
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
clahe_img = clahe.apply(img_gray)
results['7. CLAHE (clip=2.0)'] = clahe_img

clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
clahe_strong_img = clahe_strong.apply(img_gray)
results['8. CLAHE (clip=4.0)'] = clahe_strong_img

# 4. GLOBAL THRESHOLDING - Otsu's method
_, otsu = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
results['9. Otsu Threshold'] = otsu

_, otsu_inv = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
results['10. Otsu Threshold INV'] = otsu_inv

# 5. MANUAL THRESHOLDING - Remove lighter colors
# Keep only darker values (roads, features)
_, dark_only_200 = cv2.threshold(img_gray, 200, 255, cv2.THRESH_TOZERO_INV)
results['11. Dark Only (<200)'] = dark_only_200

_, dark_only_180 = cv2.threshold(img_gray, 180, 255, cv2.THRESH_TOZERO_INV)
results['12. Dark Only (<180)'] = dark_only_180

_, dark_only_160 = cv2.threshold(img_gray, 160, 255, cv2.THRESH_TOZERO_INV)
results['13. Dark Only (<160)'] = dark_only_160

# 6. MORPHOLOGICAL OPERATIONS
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
morph_close = cv2.morphologyEx(img_gray, cv2.MORPH_CLOSE, kernel)
results['14. Morph Close'] = morph_close

morph_blackhat = cv2.morphologyEx(img_gray, cv2.MORPH_BLACKHAT, kernel)
results['15. Morph Blackhat'] = morph_blackhat

# 7. EDGE ENHANCEMENT
edges_canny = cv2.Canny(img_gray, 50, 150)
results['16. Canny Edges (50,150)'] = edges_canny

# Sobel gradient
sobelx = cv2.Sobel(img_gray, cv2.CV_64F, 1, 0, ksize=3)
sobely = cv2.Sobel(img_gray, cv2.CV_64F, 0, 1, ksize=3)
sobel_mag = np.sqrt(sobelx**2 + sobely**2)
sobel_mag = np.uint8(255 * sobel_mag / np.max(sobel_mag))
results['17. Sobel Magnitude'] = sobel_mag

# 8. COMBINATION APPROACHES
# CLAHE + Adaptive threshold
clahe_then_adaptive = cv2.adaptiveThreshold(
    clahe_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
)
results['18. CLAHE + Adaptive'] = clahe_then_adaptive

# Dark filter + CLAHE
dark_filtered = np.where(img_gray > 200, 200, img_gray).astype(np.uint8)
clahe_dark = clahe.apply(dark_filtered)
results['19. Dark Filter + CLAHE'] = clahe_dark

# Inverted intensity (light becomes dark)
inverted = 255 - img_gray
results['20. Inverted'] = inverted

# 9. BILATERAL FILTER (preserves edges while smoothing)
bilateral = cv2.bilateralFilter(img_gray, 9, 75, 75)
results['21. Bilateral Filter'] = bilateral

# 10. NORMALIZED CONTRAST
normalized = cv2.normalize(img_gray, None, 0, 255, cv2.NORM_MINMAX)
results['22. Normalized Contrast'] = normalized

# 11. HISTOGRAM EQUALIZATION
hist_eq = cv2.equalizeHist(img_gray)
results['23. Histogram Equalization'] = hist_eq

# 12. ADVANCED: Suppress light colors, enhance dark
# Map values: light (>180) -> medium gray, dark -> enhanced
enhanced = img_gray.copy().astype(np.float32)
enhanced[enhanced > 180] = 180  # Cap light values
enhanced = cv2.normalize(enhanced, None, 0, 255, cv2.NORM_MINMAX)
enhanced = enhanced.astype(np.uint8)
results['24. Light Suppression'] = enhanced


# Display all results in a grid
n_results = len(results)
cols = 5
rows = (n_results + cols - 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(20, 4 * rows))
axes = axes.flatten()

for idx, (name, img) in enumerate(results.items()):
    axes[idx].imshow(img, cmap='gray')
    axes[idx].set_title(name, fontsize=10)
    axes[idx].axis('off')

# Hide unused subplots
for idx in range(n_results, len(axes)):
    axes[idx].axis('off')

plt.tight_layout()
output_path = Path(__file__).parent / "data" / "generated" / "preprocessing_comparison.png"
output_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
print(f"\nSaved comparison image to: {output_path}")

# Also save individual processed images for detailed inspection
output_dir = Path(__file__).parent / "data" / "generated" / "preprocessing_tests"
output_dir.mkdir(parents=True, exist_ok=True)

for name, img in results.items():
    # Clean filename
    filename = name.replace(' ', '_').replace('(', '').replace(')', '').replace(',', '').replace('.', '')
    cv2.imwrite(str(output_dir / f"{filename}.png"), img)

print(f"\nSaved {len(results)} individual test images to: {output_dir}/")

# Feature detection comparison
print("\n" + "="*80)
print("FEATURE DETECTION COMPARISON")
print("="*80)

# Test AKAZE feature detection on top candidates
akaze = cv2.AKAZE_create()

test_candidates = {
    'Original': img_gray,
    'CLAHE': clahe_img,
    'Dark Only (<180)': dark_only_180,
    'Adaptive Gauss INV': adaptive_gauss_inv,
    'Light Suppression': enhanced,
    'CLAHE + Adaptive': clahe_then_adaptive,
}

print(f"\n{'Method':<25} {'Keypoints':<12} {'Avg Response':<15}")
print("-" * 55)

for name, img in test_candidates.items():
    try:
        kp, desc = akaze.detectAndCompute(img, None)
        if kp:
            avg_response = np.mean([k.response for k in kp])
            print(f"{name:<25} {len(kp):<12} {avg_response:<15.4f}")
        else:
            print(f"{name:<25} {'0':<12} {'N/A':<15}")
    except Exception as e:
        print(f"{name:<25} ERROR: {e}")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)
print("""
Based on the results above:

1. For FEATURE MATCHING (AKAZE):
   - Look for methods with HIGH keypoint counts and good response values
   - Methods that enhance contrast while preserving structure work best
   - CLAHE (7,8) typically performs well for feature detection

2. For REMOVING LIGHT COLORS:
   - Dark Only thresholds (11-13) directly remove light values
   - Light Suppression (24) caps light values while preserving dark features
   - Adaptive thresholding (2-6) works well for variable lighting

3. For OVERALL ROBUSTNESS:
   - CLAHE (7) is a good baseline - enhances contrast adaptively
   - Light Suppression (24) specifically addresses your light color issue
   - CLAHE + Adaptive (18) combines contrast enhancement with thresholding

Next steps:
1. Visually inspect data/preprocessing_comparison.png
2. Review keypoint counts above
3. Choose 2-3 best methods to integrate into the matching pipeline
""")
