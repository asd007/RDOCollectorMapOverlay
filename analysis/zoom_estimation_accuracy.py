"""
Test zoom amount estimation accuracy for gradual changes
"""
import numpy as np
import cv2
from scipy import stats

def create_test_image(size=(1920, 864)):
    """Create realistic game-like test image"""
    img = np.zeros(size, dtype=np.uint8)

    # Add varied frequency content
    x = np.linspace(0, 8*np.pi, size[1])
    y = np.linspace(0, 8*np.pi, size[0])
    X, Y = np.meshgrid(x, y)

    # Multiple frequencies
    img += (30 * np.sin(X) * np.cos(Y)).astype(np.uint8)
    img += (20 * np.sin(3*X) * np.cos(3*Y)).astype(np.uint8)
    img += (15 * np.sin(7*X) * np.cos(7*Y)).astype(np.uint8)

    # Add structured elements
    for i in range(50, size[1], 150):
        cv2.rectangle(img, (i, 100), (i+60, 300), 200, -1)
        cv2.circle(img, (i+30, 400), 25, 150, -1)

    return img

def gradient_histogram_method(img1, img2):
    """Gradient histogram chi-square distance"""
    gx1 = cv2.Sobel(img1, cv2.CV_32F, 1, 0, ksize=3)
    gy1 = cv2.Sobel(img1, cv2.CV_32F, 0, 1, ksize=3)
    mag1 = np.sqrt(gx1**2 + gy1**2)

    gx2 = cv2.Sobel(img2, cv2.CV_32F, 1, 0, ksize=3)
    gy2 = cv2.Sobel(img2, cv2.CV_32F, 0, 1, ksize=3)
    mag2 = np.sqrt(gx2**2 + gy2**2)

    hist1, _ = np.histogram(mag1.ravel(), bins=32, range=(0, 255))
    hist2, _ = np.histogram(mag2.ravel(), bins=32, range=(0, 255))

    hist1 = hist1.astype(np.float32) / (np.sum(hist1) + 1e-10)
    hist2 = hist2.astype(np.float32) / (np.sum(hist2) + 1e-10)

    return np.sum((hist1 - hist2)**2 / (hist1 + hist2 + 1e-10))

def laplacian_variance_ratio(img1, img2):
    """Ratio of Laplacian variances"""
    lap1 = cv2.Laplacian(img1, cv2.CV_32F)
    lap2 = cv2.Laplacian(img2, cv2.CV_32F)

    var1 = np.var(lap1)
    var2 = np.var(lap2)

    return var2 / (var1 + 1e-10)

def simulate_zoom(img, zoom_factor):
    """Simulate zoom by center crop and resize"""
    h, w = img.shape
    new_h = int(h * zoom_factor)
    new_w = int(w * zoom_factor)

    y1 = (h - new_h) // 2
    x1 = (w - new_w) // 2
    cropped = img[y1:y1+new_h, x1:x1+new_w]

    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

def test_zoom_estimation():
    """Test if we can estimate zoom amount accurately"""
    img_original = create_test_image()
    img_small = cv2.resize(img_original, (240, 108), interpolation=cv2.INTER_AREA)

    # Build calibration curve (training data)
    print("Building calibration curves...")
    print("-" * 50)

    zoom_levels_train = np.linspace(1.0, 0.95, 51)  # 0.1% steps, 5% range
    gradient_scores_train = []
    laplacian_ratios_train = []

    for zoom in zoom_levels_train[1:]:  # Skip 100%
        img_zoomed = simulate_zoom(img_small, zoom)
        gradient_scores_train.append(gradient_histogram_method(img_small, img_zoomed))
        laplacian_ratios_train.append(laplacian_variance_ratio(img_small, img_zoomed))

    zoom_percent_train = (1.0 - zoom_levels_train[1:]) * 100

    # Fit models
    # Gradient: polynomial fit
    grad_poly = np.polyfit(gradient_scores_train, zoom_percent_train, deg=2)
    grad_model = np.poly1d(grad_poly)

    # Laplacian: linear fit (it's more linear)
    lap_slope, lap_intercept, lap_r, _, _ = stats.linregress(laplacian_ratios_train, zoom_percent_train)

    print(f"Gradient model: quadratic fit, R² = {np.corrcoef(zoom_percent_train, grad_model(gradient_scores_train))[0,1]**2:.3f}")
    print(f"Laplacian model: linear fit, R² = {lap_r**2:.3f}")

    # Test on new zoom values (not in training)
    print("\nTesting zoom estimation accuracy:")
    print("-" * 50)

    test_zooms = [0.995, 0.992, 0.988, 0.985, 0.98, 0.975, 0.97, 0.96]  # Various test points
    errors_gradient = []
    errors_laplacian = []

    print(f"{'Actual':<10} {'Gradient Est':<15} {'Lap Est':<15} {'Grad Error':<12} {'Lap Error':<12}")
    print("-" * 70)

    for zoom in test_zooms:
        actual_percent = (1.0 - zoom) * 100
        img_zoomed = simulate_zoom(img_small, zoom)

        # Gradient estimate
        grad_score = gradient_histogram_method(img_small, img_zoomed)
        grad_estimate = grad_model(grad_score)
        grad_error = abs(grad_estimate - actual_percent)
        errors_gradient.append(grad_error)

        # Laplacian estimate
        lap_ratio = laplacian_variance_ratio(img_small, img_zoomed)
        lap_estimate = lap_slope * lap_ratio + lap_intercept
        lap_error = abs(lap_estimate - actual_percent)
        errors_laplacian.append(lap_error)

        print(f"{actual_percent:<10.2f} {grad_estimate:<15.3f} {lap_estimate:<15.3f} "
              f"{grad_error:<12.3f} {lap_error:<12.3f}")

    print("\n" + "=" * 70)
    print("ESTIMATION ACCURACY SUMMARY:")
    print("-" * 70)

    print(f"\nGradient Histogram Method:")
    print(f"  Mean absolute error: {np.mean(errors_gradient):.3f}%")
    print(f"  Max error: {np.max(errors_gradient):.3f}%")
    print(f"  Std dev: {np.std(errors_gradient):.3f}%")

    print(f"\nLaplacian Variance Method:")
    print(f"  Mean absolute error: {np.mean(errors_laplacian):.3f}%")
    print(f"  Max error: {np.max(errors_laplacian):.3f}%")
    print(f"  Std dev: {np.std(errors_laplacian):.3f}%")

    # Test sub-1% accuracy specifically
    print("\n" + "=" * 70)
    print("SUB-1% ZOOM DETECTION:")
    print("-" * 70)

    sub1_zooms = np.linspace(1.0, 0.99, 11)[1:]  # 0.1% to 1.0%
    sub1_errors_grad = []
    sub1_errors_lap = []

    for zoom in sub1_zooms:
        actual = (1.0 - zoom) * 100
        img_zoomed = simulate_zoom(img_small, zoom)

        grad_score = gradient_histogram_method(img_small, img_zoomed)
        grad_est = grad_model(grad_score)
        sub1_errors_grad.append(abs(grad_est - actual))

        lap_ratio = laplacian_variance_ratio(img_small, img_zoomed)
        lap_est = lap_slope * lap_ratio + lap_intercept
        sub1_errors_lap.append(abs(lap_est - actual))

    print(f"Gradient method for 0.1-1.0% zooms:")
    print(f"  Mean error: {np.mean(sub1_errors_grad):.3f}%")
    print(f"  Can distinguish 0.5% from 0.8%: {abs(sub1_errors_grad[4] - sub1_errors_grad[7]) > 0.2}")

    print(f"\nLaplacian method for 0.1-1.0% zooms:")
    print(f"  Mean error: {np.mean(sub1_errors_lap):.3f}%")
    print(f"  Can distinguish 0.5% from 0.8%: {abs(sub1_errors_lap[4] - sub1_errors_lap[7]) > 0.2}")

    # Noise robustness test
    print("\n" + "=" * 70)
    print("NOISE ROBUSTNESS:")
    print("-" * 70)

    zoom_test = 0.995  # 0.5% zoom
    actual = 0.5
    estimates_with_noise = []

    for _ in range(20):
        img_noise = img_small + np.random.normal(0, 3, img_small.shape).astype(np.uint8)
        img_zoomed_noise = simulate_zoom(img_noise, zoom_test)

        grad_score = gradient_histogram_method(img_noise, img_zoomed_noise)
        estimate = grad_model(grad_score)
        estimates_with_noise.append(estimate)

    print(f"Testing 0.5% zoom with noise (20 samples):")
    print(f"  Mean estimate: {np.mean(estimates_with_noise):.3f}%")
    print(f"  Std dev: {np.std(estimates_with_noise):.3f}%")
    print(f"  95% confidence: {np.mean(estimates_with_noise):.3f} +/- {1.96*np.std(estimates_with_noise):.3f}%")

test_zoom_estimation()