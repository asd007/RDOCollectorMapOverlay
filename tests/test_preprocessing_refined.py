"""
Refined preprocessing test focusing on "Dark Filter + CLAHE" approach.
Goal: Make bright areas flatter/more continuous while preserving dark features.
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
print(f"Grayscale value distribution:")
print(f"  Min: {img_gray.min()}, Max: {img_gray.max()}, Mean: {img_gray.mean():.1f}")
print(f"  Std: {img_gray.std():.1f}, Median: {np.median(img_gray):.1f}")

# Analyze histogram
hist, bins = np.histogram(img_gray, bins=256, range=(0, 256))
print(f"\nValue distribution by range:")
print(f"  0-100 (dark):       {np.sum(hist[0:100])} pixels ({100*np.sum(hist[0:100])/img_gray.size:.1f}%)")
print(f"  100-150 (medium):   {np.sum(hist[100:150])} pixels ({100*np.sum(hist[100:150])/img_gray.size:.1f}%)")
print(f"  150-180 (light):    {np.sum(hist[150:180])} pixels ({100*np.sum(hist[150:180])/img_gray.size:.1f}%)")
print(f"  180-200 (lighter):  {np.sum(hist[180:200])} pixels ({100*np.sum(hist[180:200])/img_gray.size:.1f}%)")
print(f"  200+ (brightest):   {np.sum(hist[200:])} pixels ({100*np.sum(hist[200:])/img_gray.size:.1f}%)")

results = {}

# Baseline
results['Original'] = img_gray.copy()

# Original method 19
dark_filtered = np.where(img_gray > 200, 200, img_gray).astype(np.uint8)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
clahe_dark = clahe.apply(dark_filtered)
results['19. Original (>200→200)'] = clahe_dark

# VARIATION 1: Flatten bright areas to constant value
# Set all bright areas to a single middle gray
flat_190 = img_gray.copy()
flat_190[flat_190 > 190] = 160  # Flatten to constant
clahe_flat_190 = clahe.apply(flat_190)
results['V1. Flatten >190→160'] = clahe_flat_190

flat_180 = img_gray.copy()
flat_180[flat_180 > 180] = 150  # Flatten to constant
clahe_flat_180 = clahe.apply(flat_180)
results['V2. Flatten >180→150'] = clahe_flat_180

flat_170 = img_gray.copy()
flat_170[flat_170 > 170] = 140  # Flatten to constant
clahe_flat_170 = clahe.apply(flat_170)
results['V3. Flatten >170→140'] = clahe_flat_170

# VARIATION 2: Two-tier flattening (brightest two levels)
two_tier = img_gray.copy()
two_tier[two_tier > 200] = 170  # Brightest → level 1
two_tier[(two_tier > 180) & (two_tier <= 200)] = 160  # 2nd brightest → level 2
clahe_two_tier = clahe.apply(two_tier)
results['V4. Two-Tier (>200→170, 180-200→160)'] = clahe_two_tier

# VARIATION 3: Smooth compression of bright values
# Use logarithmic mapping to compress bright range
compressed = img_gray.copy().astype(np.float32)
mask = compressed > 180
compressed[mask] = 180 + (compressed[mask] - 180) * 0.3  # Compress top range by 70%
compressed = compressed.astype(np.uint8)
clahe_compressed = clahe.apply(compressed)
results['V5. Smooth Compression (>180)'] = clahe_compressed

# VARIATION 4: Gaussian blur bright areas before capping
# This makes bright areas more "continuous"
blurred_bright = img_gray.copy().astype(np.float32)
bright_mask = img_gray > 180
blurred_bright[bright_mask] = cv2.GaussianBlur(img_gray, (5, 5), 0)[bright_mask]
blurred_bright = np.clip(blurred_bright, 0, 170).astype(np.uint8)
clahe_blurred_bright = clahe.apply(blurred_bright)
results['V6. Blur+Cap Bright (>180)'] = clahe_blurred_bright

# VARIATION 5: Median filter bright areas (removes noise, makes continuous)
median_bright = img_gray.copy()
bright_mask = img_gray > 180
median_bright[bright_mask] = cv2.medianBlur(img_gray, 5)[bright_mask]
median_bright = np.clip(median_bright, 0, 170).astype(np.uint8)
clahe_median_bright = clahe.apply(median_bright)
results['V7. Median+Cap Bright (>180)'] = clahe_median_bright

# VARIATION 6: Sigmoid-based smooth suppression
# Gradually suppresses bright values with smooth transition
sigmoid = img_gray.copy().astype(np.float32)
# Apply sigmoid function to compress bright range smoothly
x = (sigmoid - 180) / 30  # Normalize around threshold
sigmoid = 180 + 30 * (1 / (1 + np.exp(-x)))  # Sigmoid
sigmoid = np.clip(sigmoid, 0, 180).astype(np.uint8)
clahe_sigmoid = clahe.apply(sigmoid)
results['V8. Sigmoid Suppression'] = clahe_sigmoid

# VARIATION 7: Morphological closing on bright areas (fills gaps, makes continuous)
morph_bright = img_gray.copy()
bright_mask = img_gray > 180
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
bright_closed = cv2.morphologyEx(img_gray, cv2.MORPH_CLOSE, kernel)
morph_bright[bright_mask] = bright_closed[bright_mask]
morph_bright = np.clip(morph_bright, 0, 170).astype(np.uint8)
clahe_morph_bright = clahe.apply(morph_bright)
results['V9. Morph Close Bright'] = clahe_morph_bright

# VARIATION 8: Bilateral filter (preserves edges, smooths flat areas)
bilateral = cv2.bilateralFilter(img_gray, 9, 50, 50)
bilateral_capped = np.where(bilateral > 180, 160, bilateral).astype(np.uint8)
clahe_bilateral = clahe.apply(bilateral_capped)
results['V10. Bilateral+Cap'] = clahe_bilateral

# VARIATION 9: Strong CLAHE clip limit for more uniformity
clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
flat_strong = img_gray.copy()
flat_strong[flat_strong > 180] = 150
clahe_flat_strong = clahe_strong.apply(flat_strong)
results['V11. Flatten+Strong CLAHE'] = clahe_flat_strong

# VARIATION 10: Histogram stretching of dark values, cap bright
stretched = img_gray.copy().astype(np.float32)
# Stretch dark values (0-180) to full range
mask_dark = stretched <= 180
stretched[mask_dark] = (stretched[mask_dark] / 180) * 255
stretched[~mask_dark] = 150  # Flatten bright
stretched = stretched.astype(np.uint8)
results['V12. Stretch Dark, Flatten Bright'] = stretched

# Display all results
n_results = len(results)
cols = 4
rows = (n_results + cols - 1) // cols

fig, axes = plt.subplots(rows, cols, figsize=(16, 4 * rows))
axes = axes.flatten()

for idx, (name, img) in enumerate(results.items()):
    axes[idx].imshow(img, cmap='gray')
    axes[idx].set_title(name, fontsize=9)
    axes[idx].axis('off')

for idx in range(n_results, len(axes)):
    axes[idx].axis('off')

plt.tight_layout()
output_path = Path(__file__).parent / "data" / "generated" / "preprocessing_refined.png"
output_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
print(f"\nSaved refined comparison to: {output_path}")

# Save individual images
output_dir = Path(__file__).parent / "data" / "generated" / "preprocessing_refined"
output_dir.mkdir(parents=True, exist_ok=True)

for name, img in results.items():
    filename = name.replace(' ', '_').replace('(', '').replace(')', '').replace(',', '').replace('.', '').replace('>', 'gt').replace('→', 'to')
    cv2.imwrite(str(output_dir / f"{filename}.png"), img)

print(f"Saved {len(results)} individual images to: {output_dir}/")

# Feature detection comparison
print("\n" + "="*80)
print("FEATURE DETECTION ON REFINED METHODS")
print("="*80)

akaze = cv2.AKAZE_create()

print(f"\n{'Method':<35} {'Keypoints':<12} {'Avg Response':<15}")
print("-" * 65)

for name, img in results.items():
    try:
        kp, desc = akaze.detectAndCompute(img, None)
        # Clean name for printing (remove unicode chars)
        clean_name = name.replace('→', 'to')
        if kp:
            avg_response = np.mean([k.response for k in kp])
            print(f"{clean_name:<35} {len(kp):<12} {avg_response:<15.4f}")
        else:
            print(f"{clean_name:<35} {'0':<12} {'N/A':<15}")
    except Exception as e:
        clean_name = name.replace('→', 'to')
        print(f"{clean_name:<35} ERROR")

print("\n" + "="*80)
print("ANALYSIS - MAKING BRIGHT AREAS FLATTER")
print("="*80)
print("""
The goal is to minimize keypoints while keeping them meaningful.
Method 19 was good, but bright areas need to be MORE continuous/flat.

Strategies tested:
1. V1-V3: Direct flattening (set bright pixels to constant)
   Creates uniform bright regions, reduces noise

2. V4: Two-tier flattening (separate the two brightest levels)
   Preserves some bright variation while simplifying

3. V5: Smooth compression (logarithmic mapping)
   Gradual transition, more natural looking

4. V6-V7: Blur/median filter bright areas
   Makes bright regions continuous by removing local variation

5. V8: Sigmoid suppression
   Smooth mathematical transition for bright values

6. V9: Morphological closing
   Fills gaps in bright areas, creates continuity

7. V10: Bilateral filter
   Preserves edges while smoothing flat areas

Look for methods with:
- Lower keypoint counts than method 19 but still meaningful features
- Visually "flat" and "continuous" bright areas
- Good contrast in dark features (roads, paths)
""")
