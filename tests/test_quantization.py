"""
Test 16-level (4-bit) gray quantization with adaptive contrast.
Goal: Further flatten bright areas while maintaining feature detectability.
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

results = {}

# Baseline - Method 19 (user's favorite)
dark_filtered = np.where(img_gray > 200, 200, img_gray).astype(np.uint8)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
clahe_dark = clahe.apply(dark_filtered)
results['Method 19 (baseline)'] = clahe_dark

# QUANTIZATION TESTS

# Test 1: Direct 16-level quantization (4-bit)
def quantize_to_levels(img, n_levels):
    """Quantize image to n discrete levels"""
    # Map 0-255 to 0-(n_levels-1) and back to 0-255 range
    factor = 255.0 / (n_levels - 1)
    quantized = np.round(img / factor) * factor
    return quantized.astype(np.uint8)

quant_16 = quantize_to_levels(img_gray, 16)
results['Q1. Direct 16-level'] = quant_16

# Test 2: 16-level + CLAHE
quant_16_clahe = clahe.apply(quant_16)
results['Q2. 16-level + CLAHE'] = quant_16_clahe

# Test 3: 16-level + stronger CLAHE
clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
quant_16_clahe_strong = clahe_strong.apply(quant_16)
results['Q3. 16-level + Strong CLAHE'] = quant_16_clahe_strong

# Test 4: Method 19 approach + 16-level quantization
dark_filtered_16 = np.where(img_gray > 200, 200, img_gray).astype(np.uint8)
dark_filtered_16 = quantize_to_levels(dark_filtered_16, 16)
dark_filtered_16_clahe = clahe.apply(dark_filtered_16)
results['Q4. Method19 + 16-level'] = dark_filtered_16_clahe

# Test 5: 32-level (5-bit) for comparison
quant_32 = quantize_to_levels(img_gray, 32)
quant_32_clahe = clahe.apply(quant_32)
results['Q5. 32-level + CLAHE'] = quant_32_clahe

# Test 6: 24-level (between 16 and 32)
quant_24 = quantize_to_levels(img_gray, 24)
quant_24_clahe = clahe.apply(quant_24)
results['Q6. 24-level + CLAHE'] = quant_24_clahe

# Test 7: 16-level with pre-brightening of dark features
# Stretch dark features before quantization
stretched = img_gray.copy().astype(np.float32)
stretched = np.clip((stretched - 50) * 1.2 + 50, 0, 255).astype(np.uint8)
stretched_16 = quantize_to_levels(stretched, 16)
stretched_16_clahe = clahe.apply(stretched_16)
results['Q7. Stretch + 16-level + CLAHE'] = stretched_16_clahe

# Test 8: Adaptive quantization - different levels for dark vs bright
# More levels for dark (features), fewer for bright (background)
adaptive_quant = img_gray.copy().astype(np.float32)
dark_mask = img_gray < 150
# Dark areas: 32 levels, Bright areas: 8 levels
adaptive_quant[dark_mask] = quantize_to_levels(img_gray[dark_mask], 32)
adaptive_quant[~dark_mask] = quantize_to_levels(img_gray[~dark_mask], 8)
adaptive_quant = adaptive_quant.astype(np.uint8)
adaptive_quant_clahe = clahe.apply(adaptive_quant)
results['Q8. Adaptive Quant (32dark/8bright)'] = adaptive_quant_clahe

# Test 9: 16-level after Method 19 approach
method19_then_quant = quantize_to_levels(clahe_dark, 16)
results['Q9. Method19 then 16-level'] = method19_then_quant

# Test 10: Posterize effect (simpler than quantization)
posterized = (img_gray // 16) * 16
posterized_clahe = clahe.apply(posterized)
results['Q10. Posterize (16 bins) + CLAHE'] = posterized_clahe

# Test 11: 16-level with bilateral pre-smoothing
bilateral = cv2.bilateralFilter(img_gray, 9, 50, 50)
bilateral_16 = quantize_to_levels(bilateral, 16)
bilateral_16_clahe = clahe.apply(bilateral_16)
results['Q11. Bilateral + 16-level + CLAHE'] = bilateral_16_clahe

# Test 12: Very aggressive - 12 levels
quant_12 = quantize_to_levels(img_gray, 12)
quant_12_clahe = clahe.apply(quant_12)
results['Q12. 12-level + CLAHE'] = quant_12_clahe

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
output_path = Path(__file__).parent / "data" / "generated" / "quantization_comparison.png"
output_path.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
print(f"\nSaved comparison to: {output_path}")

# Save individual images
output_dir = Path(__file__).parent / "data" / "generated" / "quantization_tests"
output_dir.mkdir(parents=True, exist_ok=True)

for name, img in results.items():
    filename = name.replace(' ', '_').replace('(', '').replace(')', '').replace(',', '').replace('.', '').replace('/', '_')
    cv2.imwrite(str(output_dir / f"{filename}.png"), img)

print(f"Saved {len(results)} individual images to: {output_dir}/")

# Feature detection comparison
print("\n" + "="*80)
print("FEATURE DETECTION WITH QUANTIZATION")
print("="*80)

akaze = cv2.AKAZE_create()

print(f"\n{'Method':<40} {'Keypoints':<12} {'Avg Response':<15} {'Unique Values':<15}")
print("-" * 80)

for name, img in results.items():
    try:
        kp, desc = akaze.detectAndCompute(img, None)
        unique_vals = len(np.unique(img))
        if kp:
            avg_response = np.mean([k.response for k in kp])
            print(f"{name:<40} {len(kp):<12} {avg_response:<15.4f} {unique_vals:<15}")
        else:
            print(f"{name:<40} {'0':<12} {'N/A':<15} {unique_vals:<15}")
    except Exception as e:
        print(f"{name:<40} ERROR")

print("\n" + "="*80)
print("ANALYSIS - QUANTIZATION FOR FLATTENING")
print("="*80)
print("""
Quantization reduces the number of gray levels, which naturally creates
flatter regions. Combined with CLAHE, it can maintain local contrast while
reducing overall variation.

Key considerations:
1. AKAZE typically works well even with reduced bit depth
2. 16 levels (4-bit) is aggressive but may preserve enough edge information
3. The algorithm needs gradient information - edges must remain distinct
4. Too few levels can destroy subtle features needed for matching

Look for:
- Methods with reasonable keypoint counts (>20 for meaningful matching)
- High average response (strong, confident features)
- Visually flat bright areas
- Distinct dark features (roads, paths, boundaries)

Method 19 has 76 keypoints with 0.0044 response.
Can we achieve similar or better with fewer gray levels?
""")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
Based on the results:

If keypoint count stays above ~30-40 with good response values,
quantization could work for this algorithm.

AKAZE is robust because it:
- Uses binary descriptors (already quantized internally)
- Focuses on edge/gradient information
- Works on scale-space (multi-resolution)

The real test: Does it improve matching accuracy on the full map?
Reduced gray levels = less noise = potentially better matching stability.

Next step: Integrate the best quantization method into the matching pipeline
and test against the full synthetic dataset.
""")
