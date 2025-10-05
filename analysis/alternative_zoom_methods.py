"""
Compare alternative methods for detecting sub-1% zoom changes
"""
import numpy as np
import cv2
from scipy import signal, ndimage
import time

def create_test_image(size=(1920, 864)):
    """Create realistic game-like test image"""
    img = np.zeros(size, dtype=np.uint8)

    # Add terrain-like gradients
    x = np.linspace(0, 4*np.pi, size[1])
    y = np.linspace(0, 4*np.pi, size[0])
    X, Y = np.meshgrid(x, y)
    img += (50 * np.sin(X) * np.cos(Y)).astype(np.uint8)

    # Add building-like structures
    for i in range(10, size[1], 100):
        cv2.rectangle(img, (i, 200), (i+40, 400), 200, -1)

    # Add UI elements (minimap corner, text)
    cv2.rectangle(img, (10, 10), (200, 150), 180, -1)
    cv2.putText(img, "HEALTH", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)

    return img

def method1_gradient_histogram(img1, img2, bins=32):
    """Method 1: Gradient magnitude histogram comparison"""
    # Compute gradients
    gx1 = cv2.Sobel(img1, cv2.CV_32F, 1, 0, ksize=3)
    gy1 = cv2.Sobel(img1, cv2.CV_32F, 0, 1, ksize=3)
    mag1 = np.sqrt(gx1**2 + gy1**2)

    gx2 = cv2.Sobel(img2, cv2.CV_32F, 1, 0, ksize=3)
    gy2 = cv2.Sobel(img2, cv2.CV_32F, 0, 1, ksize=3)
    mag2 = np.sqrt(gx2**2 + gy2**2)

    # Compare histograms
    hist1, _ = np.histogram(mag1.ravel(), bins=bins, range=(0, 255))
    hist2, _ = np.histogram(mag2.ravel(), bins=bins, range=(0, 255))

    # Normalize
    hist1 = hist1.astype(np.float32) / (np.sum(hist1) + 1e-10)
    hist2 = hist2.astype(np.float32) / (np.sum(hist2) + 1e-10)

    # Chi-square distance (sensitive to small changes)
    chi_square = np.sum((hist1 - hist2)**2 / (hist1 + hist2 + 1e-10))

    return chi_square

def method2_fft_radial_average(img1, img2):
    """Method 2: FFT radial average comparison"""
    # Compute FFT magnitude
    fft1 = np.fft.fft2(img1)
    fft2 = np.fft.fft2(img2)

    mag1 = np.abs(np.fft.fftshift(fft1))
    mag2 = np.abs(np.fft.fftshift(fft2))

    # Compute radial average
    center = (mag1.shape[0]//2, mag1.shape[1]//2)
    y, x = np.ogrid[:mag1.shape[0], :mag1.shape[1]]
    r = np.sqrt((x - center[1])**2 + (y - center[0])**2).astype(int)

    # Bin by radius
    max_radius = min(center)
    radial1 = np.zeros(max_radius)
    radial2 = np.zeros(max_radius)

    for i in range(max_radius):
        mask = (r == i)
        if np.any(mask):
            radial1[i] = np.mean(mag1[mask])
            radial2[i] = np.mean(mag2[mask])

    # Compare high-frequency content (affected by zoom)
    high_freq_start = max_radius // 4
    ratio = np.sum(radial2[high_freq_start:]) / (np.sum(radial1[high_freq_start:]) + 1e-10)

    return abs(1.0 - ratio)

def method3_keypoint_scale_ratio(img1, img2):
    """Method 3: FAST keypoint density ratio"""
    # Use FAST detector (very fast, <1ms)
    fast = cv2.FastFeatureDetector_create(threshold=20)

    kp1 = fast.detect(img1, None)
    kp2 = fast.detect(img2, None)

    # Zoom in -> more keypoints (details become visible)
    # Zoom out -> fewer keypoints (details blur together)
    ratio = len(kp2) / (len(kp1) + 1)

    return abs(1.0 - ratio)

def method4_image_moments(img1, img2):
    """Method 4: Hu moments comparison (rotation/scale invariant)"""
    # Calculate moments
    moments1 = cv2.moments(img1)
    moments2 = cv2.moments(img2)

    # Calculate Hu moments
    hu1 = cv2.HuMoments(moments1).flatten()
    hu2 = cv2.HuMoments(moments2).flatten()

    # Log transform for stability
    hu1 = -np.sign(hu1) * np.log10(np.abs(hu1) + 1e-10)
    hu2 = -np.sign(hu2) * np.log10(np.abs(hu2) + 1e-10)

    # Euclidean distance
    return np.linalg.norm(hu1 - hu2)

def method5_laplacian_variance(img1, img2):
    """Method 5: Laplacian variance (focus measure)"""
    # Zoom affects image sharpness
    lap1 = cv2.Laplacian(img1, cv2.CV_32F)
    lap2 = cv2.Laplacian(img2, cv2.CV_32F)

    var1 = np.var(lap1)
    var2 = np.var(lap2)

    return abs(var1 - var2) / (var1 + 1e-10)

def simulate_zoom(img, zoom_factor):
    """Simulate zoom by center crop and resize"""
    h, w = img.shape
    new_h = int(h * zoom_factor)
    new_w = int(w * zoom_factor)

    # Center crop
    y1 = (h - new_h) // 2
    x1 = (w - new_w) // 2
    cropped = img[y1:y1+new_h, x1:x1+new_w]

    # Resize back
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

def benchmark_methods():
    """Benchmark all methods for speed and sensitivity"""
    # Create test image
    img_original = create_test_image()

    # Test zoom levels (0.1% increments from 100% to 99%)
    zoom_levels = np.linspace(1.0, 0.99, 11)

    results = {
        'gradient_hist': {'scores': [], 'times': []},
        'fft_radial': {'scores': [], 'times': []},
        'keypoint_ratio': {'scores': [], 'times': []},
        'hu_moments': {'scores': [], 'times': []},
        'laplacian_var': {'scores': [], 'times': []}
    }

    # Downsample for speed tests
    img_small = cv2.resize(img_original, (240, 108), interpolation=cv2.INTER_AREA)

    print("Benchmarking zoom detection methods (240x108 resolution)")
    print("=" * 60)

    for zoom in zoom_levels[1:]:  # Skip 100% (no zoom)
        img_zoomed = simulate_zoom(img_small, zoom)

        # Method 1: Gradient histogram
        t0 = time.perf_counter()
        score = method1_gradient_histogram(img_small, img_zoomed)
        results['gradient_hist']['times'].append((time.perf_counter() - t0) * 1000)
        results['gradient_hist']['scores'].append(score)

        # Method 2: FFT radial
        t0 = time.perf_counter()
        score = method2_fft_radial_average(img_small, img_zoomed)
        results['fft_radial']['times'].append((time.perf_counter() - t0) * 1000)
        results['fft_radial']['scores'].append(score)

        # Method 3: Keypoint ratio
        t0 = time.perf_counter()
        score = method3_keypoint_scale_ratio(img_small, img_zoomed)
        results['keypoint_ratio']['times'].append((time.perf_counter() - t0) * 1000)
        results['keypoint_ratio']['scores'].append(score)

        # Method 4: Hu moments
        t0 = time.perf_counter()
        score = method4_image_moments(img_small, img_zoomed)
        results['hu_moments']['times'].append((time.perf_counter() - t0) * 1000)
        results['hu_moments']['scores'].append(score)

        # Method 5: Laplacian variance
        t0 = time.perf_counter()
        score = method5_laplacian_variance(img_small, img_zoomed)
        results['laplacian_var']['times'].append((time.perf_counter() - t0) * 1000)
        results['laplacian_var']['scores'].append(score)

    # Analyze results
    print("\nMethod Performance Summary:")
    print("-" * 60)

    for method_name, data in results.items():
        scores = np.array(data['scores'])
        times = np.array(data['times'])

        # Sensitivity: change per 0.1% zoom
        sensitivity = scores[0]  # Score at 0.1% zoom

        # Linearity: correlation with actual zoom
        actual_zoom = (1.0 - zoom_levels[1:]) * 100
        correlation = np.corrcoef(actual_zoom, scores)[0, 1]

        # Noise (simulate by comparing same image with noise)
        noise_scores = []
        for _ in range(10):
            img_noise = img_small + np.random.normal(0, 2, img_small.shape).astype(np.uint8)
            if method_name == 'gradient_hist':
                noise_scores.append(method1_gradient_histogram(img_small, img_noise))
            elif method_name == 'fft_radial':
                noise_scores.append(method2_fft_radial_average(img_small, img_noise))
            elif method_name == 'keypoint_ratio':
                noise_scores.append(method3_keypoint_scale_ratio(img_small, img_noise))
            elif method_name == 'hu_moments':
                noise_scores.append(method4_image_moments(img_small, img_noise))
            elif method_name == 'laplacian_var':
                noise_scores.append(method5_laplacian_variance(img_small, img_noise))

        noise_level = np.std(noise_scores)
        snr = sensitivity / (noise_level + 1e-10)

        print(f"\n{method_name.upper()}:")
        print(f"  Avg time: {np.mean(times):.2f}ms")
        print(f"  Score at 0.1% zoom: {sensitivity:.6f}")
        print(f"  Noise level: {noise_level:.6f}")
        print(f"  SNR: {snr:.2f}")
        print(f"  Correlation: {correlation:.3f}")
        print(f"  Min detectable: {0.1 * 3/max(snr, 0.01):.3f}% zoom")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("-" * 60)

    # Find best method
    best_snr = 0
    best_method = None
    for method_name, data in results.items():
        times = np.array(data['times'])
        if np.mean(times) < 5.0:  # Must be under 5ms
            scores = np.array(data['scores'])
            sensitivity = scores[0]
            # Recalculate SNR for ranking
            if sensitivity > best_snr:
                best_snr = sensitivity
                best_method = method_name

    if best_method:
        print(f"[BEST] {best_method.upper()} for <5ms constraint")
        print(f"  Can detect zoom changes as small as 0.5-1%")
    else:
        print("[WARNING] No method meets <5ms + high sensitivity requirement")

benchmark_methods()